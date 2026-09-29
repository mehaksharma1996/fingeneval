"""Retrieval strategies for FinGenEval.

The module supports vector, BM25, hybrid, and optional reranked hybrid search
while preserving evidence metadata needed for governance-style evaluation.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from .chunking import DocumentChunk, chunk_documents
from .document_loader import load_documents
from .settings import settings


@dataclass(frozen=True)
class RetrievalResult:
    """A retrieved evidence chunk with score and provenance metadata."""

    text: str
    source: str
    section: str
    heading: str
    score: float
    retrieval_method: str


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 with a simple auditable regex.

    # DESIGN: Regex tokenization keeps the MVP deterministic and easy to inspect.
    # PRODUCTION: Use domain-aware normalization for financial acronyms, numeric
    # thresholds, and policy identifiers to improve keyword retrieval at scale.
    """
    return re.findall(r"[a-zA-Z0-9%+<>\-]+", text.lower())


def min_max_normalize(values: np.ndarray) -> np.ndarray:
    """Normalize scores within a single query, returning zeros for ties."""
    if values.size == 0:
        return values
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if maximum == minimum:
        return np.zeros_like(values, dtype=float)
    return (values - minimum) / (maximum - minimum)


def chunk_to_result(
    chunk: DocumentChunk,
    score: float,
    method: str,
) -> RetrievalResult:
    """Convert an internal chunk to the public retrieval result shape."""
    return RetrievalResult(
        text=chunk.text,
        source=chunk.source,
        section=chunk.section,
        heading=chunk.heading,
        score=float(score),
        retrieval_method=method,
    )


class BM25Retriever:
    """BM25 keyword retriever for exact policy terms and thresholds."""

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        """Build the BM25 index over already-created chunks."""
        self.chunks = chunks
        self.corpus_tokens = [tokenize(chunk.text) for chunk in chunks]
        self.index = BM25Okapi(self.corpus_tokens)

    def score_all(self, query: str) -> np.ndarray:
        """Return min-max normalized BM25 scores for one query."""
        raw_scores = np.array(self.index.get_scores(tokenize(query)), dtype=float)
        return min_max_normalize(raw_scores)

    def search(self, query: str, top_k: int = settings.top_k) -> list[RetrievalResult]:
        """Retrieve top chunks using normalized BM25 relevance scores."""
        scores = self.score_all(query)
        ranked = np.argsort(scores)[::-1][:top_k]
        return [chunk_to_result(self.chunks[i], scores[i], "bm25") for i in ranked]


class VectorRetriever:
    """SentenceTransformer plus exact FAISS IndexFlatL2 retriever."""

    def __init__(self, chunks: list[DocumentChunk], model_name: str | None = None) -> None:
        """Embed chunks and build an exact L2 FAISS index."""
        import faiss  # type: ignore[import-not-found]
        from sentence_transformers import SentenceTransformer

        self.chunks = chunks
        self.model = SentenceTransformer(model_name or settings.embedding_model_name)
        embeddings = self.model.encode([chunk.text for chunk in chunks], normalize_embeddings=True)
        self.embeddings = np.asarray(embeddings, dtype="float32")
        self.index = faiss.IndexFlatL2(self.embeddings.shape[1])
        self.index.add(self.embeddings)

    def score_all(self, query: str) -> np.ndarray:
        """Return normalized vector similarity scores for every chunk."""
        query_embedding = self.model.encode([query], normalize_embeddings=True)
        query_vector = np.asarray(query_embedding, dtype="float32")
        distances, indices = self.index.search(query_vector, len(self.chunks))
        scores = np.zeros(len(self.chunks), dtype=float)
        scores[indices[0]] = 1.0 / (1.0 + distances[0])
        return min_max_normalize(scores)

    def search(self, query: str, top_k: int = settings.top_k) -> list[RetrievalResult]:
        """Retrieve top chunks using exact vector search over all chunks."""
        scores = self.score_all(query)
        ranked = np.argsort(scores)[::-1][:top_k]
        return [chunk_to_result(self.chunks[i], scores[i], "vector") for i in ranked]


class HybridRetriever:
    """Hybrid retriever combining per-query normalized vector and BM25 scores."""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        vector: VectorRetriever | None = None,
        bm25: BM25Retriever | None = None,
    ) -> None:
        """Create BM25 immediately (or reuse one) and vector retrieval lazily."""
        self.chunks = chunks
        self.bm25 = bm25 or BM25Retriever(chunks)
        self.vector = vector
        self._reranker = None

    def ensure_vector(self) -> VectorRetriever:
        """Initialize the vector retriever only when a vector path is requested."""
        if self.vector is None:
            self.vector = VectorRetriever(self.chunks)
        return self.vector

    def hybrid_scores(self, query: str, vector_weight: float, bm25_weight: float) -> np.ndarray:
        """Combine vector and BM25 scores after per-query normalization."""
        vector_scores = self.ensure_vector().score_all(query)
        bm25_scores = self.bm25.score_all(query)
        total = max(vector_weight + bm25_weight, 1e-9)
        return (vector_scores * vector_weight + bm25_scores * bm25_weight) / total

    def search(
        self,
        query: str,
        top_k: int = settings.top_k,
        vector_weight: float = settings.hybrid_vector_weight,
        bm25_weight: float = settings.hybrid_bm25_weight,
    ) -> list[RetrievalResult]:
        """Retrieve top chunks using weighted hybrid relevance."""
        scores = self.hybrid_scores(query, vector_weight, bm25_weight)
        ranked = np.argsort(scores)[::-1][:top_k]
        return [chunk_to_result(self.chunks[i], scores[i], "hybrid") for i in ranked]

    def search_with_reranker(
        self,
        query: str,
        top_k: int = settings.top_k,
        vector_weight: float = settings.hybrid_vector_weight,
        bm25_weight: float = settings.hybrid_bm25_weight,
    ) -> list[RetrievalResult]:
        """Retrieve hybrid candidates and optionally rerank with a cross-encoder."""
        candidates = self.search(query, max(top_k * 3, top_k), vector_weight, bm25_weight)
        reranker = self._load_reranker()
        pairs = [(query, candidate.text) for candidate in candidates]
        scores = np.asarray(reranker.predict(pairs), dtype=float)
        ranked = np.argsort(scores)[::-1][:top_k]
        return [self._replace_score(candidates[i], scores[i]) for i in ranked]

    def _load_reranker(self):
        """Load the optional cross-encoder only when the toggle requests it."""
        if self._reranker is None:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(settings.reranker_model_name)
        return self._reranker

    @staticmethod
    def _replace_score(result: RetrievalResult, score: float) -> RetrievalResult:
        """Return a reranked result while preserving evidence metadata."""
        return RetrievalResult(
            result.text, result.source, result.section, result.heading, float(score), "hybrid_reranker"
        )


def build_chunks() -> list[DocumentChunk]:
    """Load and chunk documents for retrieval smoke tests and future app startup."""
    return chunk_documents(load_documents())


def search(query: str, method: str, top_k: int = settings.top_k) -> list[RetrievalResult]:
    """Convenience search entrypoint used by smoke tests and later Streamlit code."""
    chunks = build_chunks()
    if method == "bm25":
        return BM25Retriever(chunks).search(query, top_k)
    hybrid = HybridRetriever(chunks)
    if method == "vector":
        return hybrid.ensure_vector().search(query, top_k)
    if method == "hybrid":
        return hybrid.search(query, top_k)
    if method == "hybrid_reranker":
        return hybrid.search_with_reranker(query, top_k)
    raise ValueError(f"Unsupported retrieval method: {method}")


def smoke_test(method: str = "bm25") -> list[RetrievalResult]:
    """Run a small retrieval test; BM25 default avoids model downloads."""
    query = "What is the AML SAR filing deadline?"
    results = search(query, method=method, top_k=3)
    if not results:
        raise RuntimeError("Retrieval produced no results.")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a FinGenEval retrieval smoke test.")
    parser.add_argument("--method", default="bm25", choices=["bm25", "vector", "hybrid", "hybrid_reranker"])
    args = parser.parse_args()
    for item in smoke_test(args.method):
        print(f"{item.retrieval_method} | {item.score:.3f} | {item.source} | {item.section}")
