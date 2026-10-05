"""Structural validation and evidence classification for saved benchmark runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .llm import MODE_ERROR, MODE_LLM, MODE_RETRIEVAL_ONLY
from .metrics import ANSWER_METRIC_COLUMNS
from .settings import settings

ALLOWED_GENERATION_MODES = {MODE_RETRIEVAL_ONLY, MODE_LLM, MODE_ERROR}
REQUIRED_COLUMNS = {
    "question",
    "retrieval_method",
    "prompt_style",
    "top_k",
    "generation_mode",
    *ANSWER_METRIC_COLUMNS,
}
REQUIRED_METADATA = {
    "questions",
    "methods",
    "prompt_styles",
    "top_k",
    "generation_modes",
    "dataset_path",
    "dataset_sha256_12",
}


class RunIntegrityError(ValueError):
    """Raised when a benchmark artifact fails integrity validation."""


@dataclass(frozen=True)
class RunIntegrity:
    """Derived structural and evidence status for one benchmark run."""

    status: str
    expected_rows: int
    actual_rows: int
    generation_modes: dict[str, int]
    replayed_rows: int
    structurally_complete: bool
    deployable_evidence: bool
    errors: tuple[str, ...]

    def metadata_fields(self) -> dict[str, Any]:
        """Return stable, JSON-serialisable fields for run metadata."""

        return {
            "run_status": self.status,
            "expected_rows": self.expected_rows,
            "actual_rows": self.actual_rows,
            "structurally_complete": self.structurally_complete,
            "deployable_evidence": self.deployable_evidence,
        }

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _classify_status(mode_counts: Mapping[str, int], actual_rows: int) -> str:
    retrieval_only = _as_int(mode_counts.get(MODE_RETRIEVAL_ONLY))
    generated = _as_int(mode_counts.get(MODE_LLM))
    failed = _as_int(mode_counts.get(MODE_ERROR))

    if actual_rows <= 0:
        return "INVALID"
    if retrieval_only == actual_rows:
        return "RETRIEVAL_ONLY_COMPLETE"
    if failed == actual_rows:
        return "FAILED_GENERATION"
    if failed > 0:
        return "PARTIAL_GENERATION"
    if generated == actual_rows:
        return "COMPLETE_GENERATION"
    return "MIXED_GENERATION"


def _dataset_path(metadata: Mapping[str, Any]) -> Path | None:
    raw_path = metadata.get("dataset_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = settings.project_root / candidate
    return candidate.resolve()


def _verify_dataset(metadata: Mapping[str, Any], errors: list[str]) -> None:
    dataset_path = _dataset_path(metadata)
    if dataset_path is None:
        return

    project_root = settings.project_root.resolve()
    if dataset_path != project_root and project_root not in dataset_path.parents:
        errors.append("dataset_path must resolve inside the project root")
        return
    if not dataset_path.is_file():
        errors.append(f"dataset_path does not exist: {dataset_path}")
        return

    actual_fingerprint = hashlib.sha256(dataset_path.read_bytes()).hexdigest()[:12]
    expected_fingerprint = str(metadata.get("dataset_sha256_12", ""))
    if actual_fingerprint != expected_fingerprint:
        errors.append(
            f"dataset fingerprint mismatch: metadata={expected_fingerprint!r}, current={actual_fingerprint!r}"
        )

    try:
        dataset = pd.read_csv(dataset_path)
    except Exception as exc:  # pragma: no cover - pandas supplies the useful detail
        errors.append(f"could not read dataset_path: {exc}")
        return

    expected_questions = _as_int(metadata.get("questions"), -1)
    if len(dataset) != expected_questions:
        errors.append(
            f"dataset contains {len(dataset)} rows but metadata declares {expected_questions} questions"
        )

    if "answerable" in dataset.columns or "expected_sources" in dataset.columns:
        if "answerable" in dataset.columns:
            values = dataset["answerable"].astype(str).str.strip().str.lower()
            answerable = int(values.isin({"1", "true", "yes"}).sum())
        else:
            answerable = int((dataset["expected_sources"].astype(str).str.strip() != "none").sum())
        unanswerable = int(len(dataset) - answerable)
        declared_answerable = metadata.get("answerable_questions")
        declared_unanswerable = metadata.get("unanswerable_questions")
        if declared_answerable is not None and _as_int(declared_answerable, -1) != answerable:
            errors.append(
                f"metadata declares {declared_answerable} answerable questions; dataset has {answerable}"
            )
        if declared_unanswerable is not None and _as_int(declared_unanswerable, -1) != unanswerable:
            errors.append(
                "metadata declares "
                f"{declared_unanswerable} unanswerable questions; dataset has {unanswerable}"
            )


def inspect_run(
    frame: pd.DataFrame,
    metadata: Mapping[str, Any],
    *,
    verify_dataset: bool = True,
) -> RunIntegrity:
    """Inspect one run without raising, returning all detected integrity errors."""

    errors: list[str] = []
    missing_metadata = sorted(REQUIRED_METADATA - set(metadata))
    if missing_metadata:
        errors.append(f"missing metadata fields: {', '.join(missing_metadata)}")

    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        errors.append(f"missing result columns: {', '.join(missing_columns)}")

    methods = metadata.get("methods", [])
    prompts = metadata.get("prompt_styles", [])
    if not isinstance(methods, list) or not methods:
        errors.append("metadata methods must be a non-empty list")
        methods = []
    if not isinstance(prompts, list) or not prompts:
        errors.append("metadata prompt_styles must be a non-empty list")
        prompts = []

    question_count = _as_int(metadata.get("questions"), -1)
    if question_count <= 0:
        errors.append("metadata questions must be a positive integer")
        question_count = 0
    expected_rows = question_count * len(methods) * len(prompts)
    actual_rows = len(frame)
    if expected_rows != actual_rows:
        errors.append(f"expected {expected_rows} rows from the run matrix; found {actual_rows}")

    mode_counts: dict[str, int] = {}
    if "generation_mode" in frame.columns:
        mode_counts = {
            str(key): int(value) for key, value in frame["generation_mode"].value_counts(dropna=False).items()
        }
        unknown_modes = sorted(set(mode_counts) - ALLOWED_GENERATION_MODES)
        if unknown_modes:
            errors.append(f"unsupported generation modes: {', '.join(unknown_modes)}")

        declared_modes = metadata.get("generation_modes")
        if not isinstance(declared_modes, Mapping):
            errors.append("metadata generation_modes must be an object")
        else:
            normalised_declared = {str(key): _as_int(value) for key, value in declared_modes.items()}
            if normalised_declared != mode_counts:
                errors.append(
                    "generation mode counts do not match metadata: "
                    f"metadata={normalised_declared}, actual={mode_counts}"
                )

    key_columns = ["question", "retrieval_method", "prompt_style"]
    if all(column in frame.columns for column in key_columns):
        duplicate_count = int(frame.duplicated(key_columns, keep=False).sum())
        if duplicate_count:
            errors.append(f"found {duplicate_count} rows with duplicate benchmark keys")

        actual_questions = frame["question"].dropna().astype(str).unique().tolist()
        if len(actual_questions) != question_count:
            errors.append(
                f"results contain {len(actual_questions)} unique questions; metadata declares {question_count}"
            )

        actual_methods = set(frame["retrieval_method"].dropna().astype(str))
        if actual_methods != set(map(str, methods)):
            errors.append(
                f"retrieval methods differ: metadata={sorted(map(str, methods))}, "
                f"actual={sorted(actual_methods)}"
            )

        actual_prompts = set(frame["prompt_style"].dropna().astype(str))
        if actual_prompts != set(map(str, prompts)):
            errors.append(
                f"prompt styles differ: metadata={sorted(map(str, prompts))}, actual={sorted(actual_prompts)}"
            )

        expected_keys = {
            (question, str(method), str(prompt))
            for question in actual_questions
            for method in methods
            for prompt in prompts
        }
        actual_keys = {
            (str(row.question), str(row.retrieval_method), str(row.prompt_style))
            for row in frame[key_columns].itertuples(index=False)
        }
        missing_keys = expected_keys - actual_keys
        extra_keys = actual_keys - expected_keys
        if missing_keys:
            errors.append(f"benchmark matrix is missing {len(missing_keys)} configuration rows")
        if extra_keys:
            errors.append(f"benchmark matrix contains {len(extra_keys)} unexpected configuration rows")

    if "top_k" in frame.columns:
        declared_top_k = _as_int(metadata.get("top_k"), -1)
        actual_top_k = {_as_int(value, -1) for value in frame["top_k"].dropna().unique()}
        if actual_top_k != {declared_top_k}:
            errors.append(f"top_k differs: metadata={declared_top_k}, actual={sorted(actual_top_k)}")

    if "generation_mode" in frame.columns and not missing_columns:
        non_llm = frame[frame["generation_mode"] != MODE_LLM]
        populated_non_llm = [column for column in ANSWER_METRIC_COLUMNS if non_llm[column].notna().any()]
        if populated_non_llm:
            errors.append("non-LLM rows contain answer-level metrics: " + ", ".join(populated_non_llm))

        generated = frame[frame["generation_mode"] == MODE_LLM]
        required_generated_metrics = ["abstained", "abstention_correct", "claim_count"]
        incomplete_generated = [
            column for column in required_generated_metrics if generated[column].isna().any()
        ]
        if incomplete_generated:
            errors.append(
                "successful LLM rows are missing required answer metrics: " + ", ".join(incomplete_generated)
            )

    if verify_dataset and not missing_metadata:
        _verify_dataset(metadata, errors)

    replayed_rows = _as_int(metadata.get("reused_llm_rows"), 0)
    if replayed_rows < 0 or replayed_rows > actual_rows:
        errors.append(f"reused_llm_rows must be between 0 and {actual_rows}")

    status = _classify_status(mode_counts, actual_rows)
    if replayed_rows > 0 and status != "INVALID":
        status = f"{status}_REPLAYED"

    structurally_complete = not errors
    if not structurally_complete:
        status = "INVALID"
    deployable_evidence = structurally_complete and status.removesuffix("_REPLAYED") == (
        "COMPLETE_GENERATION"
    )

    integrity = RunIntegrity(
        status=status,
        expected_rows=expected_rows,
        actual_rows=actual_rows,
        generation_modes=mode_counts,
        replayed_rows=replayed_rows,
        structurally_complete=structurally_complete,
        deployable_evidence=deployable_evidence,
        errors=tuple(errors),
    )

    declared_status = metadata.get("run_status")
    if declared_status is not None and declared_status != integrity.status:
        updated_errors = (
            *integrity.errors,
            f"run_status differs: metadata={declared_status!r}, derived={integrity.status!r}",
        )
        integrity = RunIntegrity(
            status="INVALID",
            expected_rows=expected_rows,
            actual_rows=actual_rows,
            generation_modes=mode_counts,
            replayed_rows=replayed_rows,
            structurally_complete=False,
            deployable_evidence=False,
            errors=updated_errors,
        )

    for field, actual in {
        "expected_rows": integrity.expected_rows,
        "actual_rows": integrity.actual_rows,
        "structurally_complete": integrity.structurally_complete,
        "deployable_evidence": integrity.deployable_evidence,
    }.items():
        declared = metadata.get(field)
        if declared is not None and declared != actual:
            updated_errors = (
                *integrity.errors,
                f"{field} differs: metadata={declared!r}, derived={actual!r}",
            )
            integrity = RunIntegrity(
                status="INVALID",
                expected_rows=expected_rows,
                actual_rows=actual_rows,
                generation_modes=mode_counts,
                replayed_rows=replayed_rows,
                structurally_complete=False,
                deployable_evidence=False,
                errors=updated_errors,
            )

    return integrity


def validate_run(
    frame: pd.DataFrame,
    metadata: Mapping[str, Any],
    *,
    verify_dataset: bool = True,
) -> RunIntegrity:
    """Validate one run and raise with all diagnostics when it is malformed."""

    integrity = inspect_run(frame, metadata, verify_dataset=verify_dataset)
    if integrity.errors:
        details = "\n- ".join(integrity.errors)
        raise RunIntegrityError(f"benchmark run failed integrity validation:\n- {details}")
    return integrity


def load_saved_run(run_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    results_path = run_dir / "evaluation_results.csv"
    metadata_path = run_dir / "run_metadata.json"
    if not results_path.is_file() or not metadata_path.is_file():
        raise RunIntegrityError(f"{run_dir} must contain evaluation_results.csv and run_metadata.json")
    return pd.read_csv(results_path), json.loads(metadata_path.read_text(encoding="utf-8"))


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate saved FinGenEval run artifacts")
    parser.add_argument("run_dirs", nargs="+", type=Path, help="saved run directories")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    failed = False
    for run_dir in args.run_dirs:
        try:
            frame, metadata = load_saved_run(run_dir)
            integrity = validate_run(frame, metadata)
        except (OSError, json.JSONDecodeError, RunIntegrityError) as exc:
            failed = True
            print(f"FAIL {run_dir}: {exc}")
            continue
        modes = ", ".join(f"{key}={value}" for key, value in integrity.generation_modes.items())
        print(
            f"PASS {run_dir}: {integrity.status}; "
            f"rows={integrity.actual_rows}/{integrity.expected_rows}; {modes}"
        )
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
