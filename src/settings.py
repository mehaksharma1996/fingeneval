"""Application settings for FinGenEval.

Centralizing paths and knobs here keeps later retrieval, evaluation, and UI code
free of hardcoded filesystem assumptions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable with a safe default for local demos."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float environment variable with a safe default for local demos."""
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings used across the validation pipeline."""

    project_root: Path = Path(__file__).resolve().parents[1]
    docs_dir: Path = project_root / "data" / "docs"
    eval_path: Path = project_root / "data" / "eval" / "test_questions.csv"
    chunk_size_tokens: int = _env_int("FINGENEVAL_CHUNK_SIZE_TOKENS", 400)
    chunk_overlap_tokens: int = _env_int("FINGENEVAL_CHUNK_OVERLAP_TOKENS", 80)
    top_k: int = _env_int("FINGENEVAL_TOP_K", 5)
    hybrid_vector_weight: float = _env_float("FINGENEVAL_HYBRID_VECTOR_WEIGHT", 0.5)
    hybrid_bm25_weight: float = _env_float("FINGENEVAL_HYBRID_BM25_WEIGHT", 0.5)
    embedding_model_name: str = os.getenv(
        "FINGENEVAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    reranker_model_name: str = os.getenv("FINGENEVAL_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    # DESIGN: The model name is configurable because hosted model versions are
    # retired over time; pin the exact version used in each validation run.
    gemini_model: str = os.getenv("FINGENEVAL_GEMINI_MODEL", "gemini-2.5-flash")
    # Minimum spacing between LLM calls (free-tier rate limit). This wait is
    # applied before the generation timer starts, so it never inflates latency.
    llm_min_interval_seconds: float = _env_float("FINGENEVAL_LLM_MIN_INTERVAL_SECONDS", 4.0)
    # Retries for per-minute rate limits and temporary overloads (not daily quota).
    llm_max_retries: int = _env_int("FINGENEVAL_LLM_MAX_RETRIES", 3)
    results_dir: Path = project_root / "results"

    # Deployment gates applied by the governance report.
    gate_min_contextual_recall: float = 0.80
    gate_min_faithfulness: float = 0.85
    gate_max_hallucination_risk: float = 0.10
    gate_min_citation_coverage: float = 0.90
    gate_min_correct_abstention: float = 0.90
    gate_max_false_refusal: float = 0.10
    gate_max_generation_error_rate: float = 0.05


settings = Settings()
