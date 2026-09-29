"""Small shared helpers for FinGenEval modules."""

from __future__ import annotations


def preview_text(text: str, max_chars: int = 240) -> str:
    """Return a compact preview string for logs and future UI expanders."""
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
