"""Small shared helpers for FinGenEval modules."""

from __future__ import annotations

import hashlib
from pathlib import Path


def text_fingerprint(path: Path, length: int = 12) -> str:
    """Hash UTF-8 text with canonical newlines for cross-platform evidence IDs."""
    canonical = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:length]


def preview_text(text: str, max_chars: int = 240) -> str:
    """Return a compact preview string for logs and future UI expanders."""
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
