"""Section-aware chunking for financial policy documents."""

from __future__ import annotations

from dataclasses import dataclass

from .document_loader import FinancialDocument, load_documents
from .settings import settings


@dataclass(frozen=True)
class DocumentChunk:
    """A retrievable text unit with provenance metadata."""

    text: str
    source: str
    section: str
    heading: str


def estimate_tokens(text: str) -> list[str]:
    """Estimate tokens with whitespace splitting for a dependency-light MVP.

    # DESIGN: Whitespace tokenization is transparent and sufficient for a small
    # synthetic corpus in a one-day validation MVP.
    # PRODUCTION: Use the embedding model tokenizer to align chunk boundaries
    # with actual model tokens and reduce truncation or retrieval artifacts.
    """
    return text.split()


def parse_sections(document: FinancialDocument) -> list[tuple[str, str]]:
    """Split markdown into H2 sections while keeping headings with their body."""
    sections: list[tuple[str, list[str]]] = []
    current_heading = document.title
    current_lines: list[str] = []
    for line in document.text.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.removeprefix("## ").strip()
            current_lines = [line]
        elif line.strip() or current_lines:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))
    return [(heading, "\n".join(lines).strip()) for heading, lines in sections]


def format_chunk_text(title: str, heading: str, chunk_text: str) -> str:
    """Prepend document and section context before embedding or retrieval."""
    clean_text = " ".join(chunk_text.split())
    return f"{title}: {heading} - {clean_text}"


def split_section_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split a section into overlapping token windows without losing headings."""
    tokens = estimate_tokens(text)
    if len(tokens) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(" ".join(tokens[start:end]))
        if end == len(tokens):
            break
        start += step
    return chunks


def chunk_document(
    document: FinancialDocument,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[DocumentChunk]:
    """Create section-aware chunks for one document with source metadata."""
    size = chunk_size if chunk_size is not None else settings.chunk_size_tokens
    overlap_tokens = overlap if overlap is not None else settings.chunk_overlap_tokens
    chunks: list[DocumentChunk] = []
    for heading, section_text in parse_sections(document):
        for chunk_text in split_section_text(section_text, size, overlap_tokens):
            chunks.append(
                DocumentChunk(
                    text=format_chunk_text(document.title, heading, chunk_text),
                    source=document.source,
                    section=heading,
                    heading=heading,
                )
            )
    return chunks


def chunk_documents(documents: list[FinancialDocument]) -> list[DocumentChunk]:
    """Chunk every loaded document into a flat list for indexing."""
    return [chunk for document in documents for chunk in chunk_document(document)]


def smoke_test() -> dict[str, int]:
    """Load and chunk the corpus, returning simple counts for validation."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    if not chunks:
        raise RuntimeError("Chunking produced zero chunks.")
    return {"documents": len(documents), "chunks": len(chunks)}


if __name__ == "__main__":
    result = smoke_test()
    print(f"Loaded {result['documents']} documents into {result['chunks']} chunks.")
