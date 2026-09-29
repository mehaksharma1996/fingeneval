"""Document loading utilities for the synthetic financial corpus."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .settings import settings


@dataclass(frozen=True)
class FinancialDocument:
    """A markdown source document with metadata needed by downstream retrieval."""

    title: str
    source: str
    path: Path
    text: str


def extract_title(markdown_text: str, fallback: str) -> str:
    """Return the first H1 title, falling back to the filename stem.

    The MVP assumes each synthetic document has a clear H1. Production ingestion
    would validate document schemas and reject ambiguous sources before indexing.
    """
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return fallback


def load_markdown_document(path: Path) -> FinancialDocument:
    """Load one markdown file and attach source metadata for auditability."""
    text = path.read_text(encoding="utf-8")
    title = extract_title(text, path.stem.replace("_", " ").title())
    return FinancialDocument(title=title, source=path.name, path=path, text=text)


def load_documents(docs_dir: Path | None = None) -> list[FinancialDocument]:
    """Load all markdown policy documents in deterministic filename order."""
    directory = docs_dir or settings.docs_dir
    if not directory.exists():
        raise FileNotFoundError(f"Document directory does not exist: {directory}")
    paths = sorted(directory.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"No markdown documents found in: {directory}")
    return [load_markdown_document(path) for path in paths]
