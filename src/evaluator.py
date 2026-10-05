"""Benchmark runner for FinGenEval retrieval and answer quality."""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import llm, metrics
from .llm import MODE_LLM, answer_question
from .retrievers import BM25Retriever, HybridRetriever, RetrievalResult, VectorRetriever, build_chunks
from .settings import settings
from .utils import text_fingerprint

DEFAULT_METHODS = ["vector", "bm25", "hybrid", "hybrid_reranker"]
DEFAULT_PROMPTS = ["strict_governance"]
REQUIRED_COLUMNS = {
    "question",
    "expected_sources",
    "relevant_sections",
    "evidence_keywords",
    "reference_answer",
    "question_type",
}
WARMUP_QUERY = "warm up retrieval models"


class RetrievalEngine:
    """Reusable retrieval engine for benchmark runs without repeated indexing."""

    def __init__(self) -> None:
        """Build chunks and cheap indexes immediately, with model-backed paths lazy."""
        self.chunks = build_chunks()
        self.bm25 = BM25Retriever(self.chunks)
        self.vector: VectorRetriever | None = None
        self.hybrid = HybridRetriever(self.chunks, bm25=self.bm25)

    def search(
        self,
        query: str,
        method: str,
        top_k: int,
        vector_weight: float = settings.hybrid_vector_weight,
        bm25_weight: float = settings.hybrid_bm25_weight,
    ) -> list[RetrievalResult]:
        """Run one retrieval method against shared indexes."""
        if method == "bm25":
            return self.bm25.search(query, top_k)
        if method == "vector":
            return self._vector().search(query, top_k)
        if method == "hybrid":
            self.hybrid.vector = self._vector()
            return self.hybrid.search(query, top_k, vector_weight, bm25_weight)
        if method == "hybrid_reranker":
            self.hybrid.vector = self._vector()
            return self.hybrid.search_with_reranker(query, top_k, vector_weight, bm25_weight)
        raise ValueError(f"Unsupported retrieval method: {method}")

    def warmup(self, methods: list[str]) -> None:
        """Load models and run one query per method so timings exclude cold starts."""
        for method in methods:
            self.search(WARMUP_QUERY, method, 1)

    def _vector(self) -> VectorRetriever:
        """Create the vector index once for all vector-backed benchmark rows."""
        if self.vector is None:
            self.vector = VectorRetriever(self.chunks)
        return self.vector


def load_questions(path: Path = settings.eval_path) -> pd.DataFrame:
    """Load the evaluation CSV and validate required columns."""
    data = pd.read_csv(path, keep_default_na=False)
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"Evaluation dataset is missing columns: {sorted(missing)}")
    data["answerable"] = data["expected_sources"].str.strip() != "none"
    return data


def dataset_fingerprint(path: Path = settings.eval_path) -> str:
    """Return a short content hash so reports identify the exact dataset used."""
    return text_fingerprint(Path(path))


def evaluate_row(
    row: pd.Series,
    method: str,
    prompt_style: str,
    engine: RetrievalEngine,
    top_k: int,
) -> dict[str, object]:
    """Evaluate one question, method, and prompt into a metric dictionary."""
    start = time.perf_counter()
    results = engine.search(row["question"], method, top_k)
    retrieval_latency = time.perf_counter() - start
    answer = answer_question(row["question"], results, prompt_style)
    return build_metrics(row, method, prompt_style, results, answer, retrieval_latency)


def build_metrics(
    row: pd.Series,
    method: str,
    prompt_style: str,
    results: list[RetrievalResult],
    answer,
    retrieval_latency: float,
) -> dict[str, object]:
    """Build retrieval metrics always and answer metrics only for real LLM answers."""
    answerable = bool(row["answerable"])
    relevant_sections = metrics.split_labels(row["relevant_sections"])
    evidence = metrics.split_labels(row["evidence_keywords"])
    flags = metrics.relevance_flags(results, relevant_sections)
    nan = math.nan
    record: dict[str, object] = {
        "question": row["question"],
        "question_type": row["question_type"],
        "answerable": int(answerable),
        "retrieval_method": method,
        "prompt_style": prompt_style,
        "top_k": len(results),
        "retrieved_sections": "; ".join(metrics.section_key(item) for item in results),
        "hit_at_k": metrics.hit_at_k(flags) if answerable else nan,
        "reciprocal_rank": metrics.reciprocal_rank(flags) if answerable else nan,
        "contextual_precision": metrics.contextual_precision(flags) if answerable else nan,
        "contextual_recall": metrics.contextual_recall(results, evidence) if answerable else nan,
        "section_recall": metrics.section_recall(results, relevant_sections) if answerable else nan,
        "retrieval_latency_seconds": retrieval_latency,
        "generation_mode": answer.mode,
        "generation_latency_seconds": answer.latency_seconds if answer.latency_seconds is not None else nan,
        "answer": answer.answer,
    }
    if answer.mode == MODE_LLM:
        record.update(
            metrics.answer_metrics(
                answer.answer, row["question"], results, answerable, row["reference_answer"]
            )
        )
    else:
        record.update({column: nan for column in metrics.ANSWER_METRIC_COLUMNS})
    return record


def run_evaluation(
    methods: list[str] | None = None,
    prompt_styles: list[str] | None = None,
    top_k: int = settings.top_k,
    engine: RetrievalEngine | None = None,
    resume_from: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Run the benchmark and return per-row results plus run metadata.

    With resume_from, successful LLM rows from an earlier run of the same dataset
    and top_k are reused, so only failed or missing rows call the API again.
    """
    methods = methods or DEFAULT_METHODS
    prompt_styles = prompt_styles or DEFAULT_PROMPTS
    questions = load_questions()
    engine = engine or RetrievalEngine()
    engine.warmup(methods)
    reusable = reusable_rows(resume_from, top_k)
    llm.reset_daily_quota_flag()
    reused = 0
    rows = []
    for _, row in questions.iterrows():
        for method in methods:
            for prompt_style in prompt_styles:
                previous = reusable.get((row["question"], method, prompt_style))
                reused += previous is not None
                rows.append(
                    previous
                    if previous is not None
                    else evaluate_row(row, method, prompt_style, engine, top_k)
                )
    frame = pd.DataFrame(rows)
    metadata = {
        "run_timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset_path": settings.eval_path.relative_to(settings.project_root).as_posix(),
        "dataset_sha256_12": dataset_fingerprint(),
        "questions": int(len(questions)),
        "answerable_questions": int(questions["answerable"].sum()),
        "unanswerable_questions": int((~questions["answerable"]).sum()),
        "indexed_chunks": len(engine.chunks),
        "methods": methods,
        "prompt_styles": prompt_styles,
        "top_k": top_k,
        "generation_modes": frame["generation_mode"].value_counts().to_dict(),
        "resumed_from": str(resume_from) if resume_from else None,
        "reused_llm_rows": reused,
        "generation_model": settings.gemini_model if settings.gemini_api_key else None,
        "embedding_model": settings.embedding_model_name,
        "reranker_model": settings.reranker_model_name,
        "hybrid_weights": {"vector": settings.hybrid_vector_weight, "bm25": settings.hybrid_bm25_weight},
    }
    from .run_integrity import validate_run

    integrity = validate_run(frame, metadata)
    metadata.update(integrity.metadata_fields())
    return frame, metadata


def reusable_rows(path: Path | None, top_k: int) -> dict[tuple[str, str, str], dict[str, object]]:
    """Load successful LLM rows from a previous results CSV, keyed by configuration."""
    if path is None:
        return {}
    previous = pd.read_csv(path, keep_default_na=False, na_values=[""])
    keep = previous[(previous["generation_mode"] == MODE_LLM) & (previous["top_k"] == top_k)]
    return {
        (record["question"], record["retrieval_method"], record["prompt_style"]): record
        for record in keep.to_dict("records")
    }


def save_run(frame: pd.DataFrame, metadata: dict[str, object], output_dir: Path) -> Path:
    """Write the evaluation CSV, governance report, and metadata to one folder."""
    from .report_generator import generate_governance_report
    from .run_integrity import validate_run

    integrity = validate_run(frame, metadata)
    metadata.update(integrity.metadata_fields())

    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "evaluation_results.csv", index=False)
    (output_dir / "governance_report.md").write_text(
        generate_governance_report(frame, metadata), encoding="utf-8"
    )
    (output_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output_dir


def parse_csv_arg(value: str) -> list[str]:
    """Parse a comma-delimited CLI argument into cleaned values."""
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the FinGenEval benchmark.")
    parser.add_argument("--methods", default="bm25", help="Comma-separated: " + ",".join(DEFAULT_METHODS))
    parser.add_argument("--prompt-styles", default="strict_governance")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=None, help="Folder for CSV, report, and metadata.")
    parser.add_argument(
        "--resume-from",
        type=Path,
        default=None,
        help="Earlier evaluation_results.csv whose successful LLM rows are reused.",
    )
    args = parser.parse_args()
    frame, metadata = run_evaluation(
        parse_csv_arg(args.methods),
        parse_csv_arg(args.prompt_styles),
        args.top_k,
        resume_from=args.resume_from,
    )
    summary_columns = ["hit_at_k", "reciprocal_rank", "contextual_precision", "contextual_recall"]
    print(frame.groupby("retrieval_method")[summary_columns].mean().round(3).to_string())
    print(f"rows={len(frame)} columns={len(frame.columns)} modes={metadata['generation_modes']}")
    if args.output_dir:
        print(f"saved to {save_run(frame, metadata, args.output_dir)}")
