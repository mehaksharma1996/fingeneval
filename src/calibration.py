"""Fail-closed calibration analysis for deterministic evaluation metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from . import metrics
from .retrievers import RetrievalResult, build_chunks
from .settings import settings

CALIBRATION_SCHEMA_VERSION = "1.0"
LABEL_COLUMNS = {
    "retrieval_sufficient": "human_retrieval_sufficient",
    "faithful": "human_faithful",
    "citations_valid": "human_citations_valid",
    "answer_correct": "human_answer_correct",
    "abstention_correct": "human_abstention_correct",
}
REQUIRED_COLUMNS = {
    "case_id",
    "question",
    "question_type",
    "answerable",
    "relevant_sections",
    "evidence_keywords",
    "reference_answer",
    "retrieved_sections",
    "candidate_answer",
    "case_origin",
    "perturbation",
    *LABEL_COLUMNS.values(),
    "reviewer_id",
    "reviewed_at_utc",
    "review_status",
    "adjudication_notes",
}
DEFAULT_THRESHOLDS = {
    "contextual_recall": settings.gate_min_contextual_recall,
    "faithfulness_proxy": settings.gate_min_faithfulness,
    "citation_coverage": settings.gate_min_citation_coverage,
    "citation_validity": 1.0,
    "answer_correctness_proxy": 0.80,
}


class CalibrationError(ValueError):
    """Raised when calibration inputs are malformed or falsely claim readiness."""


@dataclass(frozen=True)
class Confusion:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.true_negative + self.false_negative

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else math.nan

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else math.nan

    @property
    def f1(self) -> float:
        if math.isnan(self.precision) or math.isnan(self.recall) or not (self.precision + self.recall):
            return math.nan
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    @property
    def accuracy(self) -> float:
        return (self.true_positive + self.true_negative) / self.total if self.total else math.nan


@dataclass(frozen=True)
class CalibrationResult:
    status: str
    cases: pd.DataFrame
    comparisons: pd.DataFrame
    summaries: pd.DataFrame
    errors: tuple[str, ...]


def _sha256_12(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _parse_label(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    normalised = str(value).strip().lower()
    if normalised in {"", "n/a", "na", "not_applicable"}:
        return None
    if normalised in {"1", "true", "yes", "pass"}:
        return 1
    if normalised in {"0", "false", "no", "fail"}:
        return 0
    raise CalibrationError(f"invalid human label {value!r}; use 1, 0, or blank for not applicable")


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _prediction(value: float, threshold: float, *, at_most: bool = False) -> int | None:
    if value is None or math.isnan(float(value)):
        return None
    return int(float(value) <= threshold if at_most else float(value) >= threshold)


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt((proportion * (1 - proportion) + z**2 / (4 * total)) / total) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _results_by_section() -> dict[str, RetrievalResult]:
    result_map: dict[str, RetrievalResult] = {}
    for chunk in build_chunks():
        key = f"{chunk.source}#{chunk.section}"
        result_map.setdefault(
            key,
            RetrievalResult(
                text=chunk.text,
                source=chunk.source,
                section=chunk.section,
                heading=chunk.heading,
                score=1.0,
                retrieval_method="calibration_fixture",
            ),
        )
    return result_map


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and validate calibration provenance and threshold controls."""

    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != CALIBRATION_SCHEMA_VERSION:
        raise CalibrationError(
            f"unsupported calibration schema {manifest.get('schema_version')!r}; "
            f"expected {CALIBRATION_SCHEMA_VERSION!r}"
        )
    if manifest.get("dataset_sha256_12") != _sha256_12(settings.eval_path):
        raise CalibrationError("calibration manifest dataset fingerprint does not match the current dataset")
    thresholds = manifest.get("thresholds")
    if not isinstance(thresholds, Mapping):
        raise CalibrationError("manifest thresholds must be an object")
    changed = {
        name: value
        for name, value in thresholds.items()
        if name in DEFAULT_THRESHOLDS and float(value) != DEFAULT_THRESHOLDS[name]
    }
    if changed:
        approval = manifest.get("threshold_change")
        required = {"approved_by", "approved_at_utc", "evidence_report", "reason"}
        if not isinstance(approval, Mapping) or any(not approval.get(key) for key in required):
            raise CalibrationError(
                "threshold changes require approved_by, approved_at_utc, evidence_report, and reason"
            )
    return manifest


def load_cases(path: Path, manifest: Mapping[str, Any]) -> pd.DataFrame:
    """Load an annotation packet and validate its immutable provenance."""

    if manifest.get("annotation_file") != path.name:
        raise CalibrationError("manifest annotation_file does not match the supplied file")
    declared_hash = manifest.get("annotation_sha256_12")
    if declared_hash not in {None, "PENDING"} and declared_hash != _sha256_12(path):
        raise CalibrationError("annotation file fingerprint does not match the manifest")

    frame = pd.read_csv(path, keep_default_na=False)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise CalibrationError(f"calibration packet is missing columns: {', '.join(missing)}")
    if frame.empty:
        raise CalibrationError("calibration packet must contain at least one case")
    if frame["case_id"].duplicated().any():
        raise CalibrationError("calibration case_id values must be unique")
    allowed_statuses = {"pending", "reviewed", "adjudicated"}
    unknown_statuses = sorted(set(frame["review_status"]) - allowed_statuses)
    if unknown_statuses:
        raise CalibrationError(f"unsupported review statuses: {', '.join(unknown_statuses)}")

    dataset = pd.read_csv(settings.eval_path, keep_default_na=False).set_index("question")
    for row in frame.itertuples(index=False):
        if row.question not in dataset.index:
            raise CalibrationError(f"case {row.case_id} question is not present in the labeled dataset")
        source = dataset.loc[row.question]
        expected = {
            "question_type": str(source["question_type"]),
            "relevant_sections": str(source["relevant_sections"]),
            "evidence_keywords": str(source["evidence_keywords"]),
            "reference_answer": str(source["reference_answer"]),
            "answerable": str(int(str(source["expected_sources"]).strip() != "none")),
        }
        actual = {
            "question_type": str(row.question_type),
            "relevant_sections": str(row.relevant_sections),
            "evidence_keywords": str(row.evidence_keywords),
            "reference_answer": str(row.reference_answer),
            "answerable": str(row.answerable),
        }
        if actual != expected:
            raise CalibrationError(f"case {row.case_id} labels drift from the source dataset")

    if (frame["review_status"] == "adjudicated").all() and declared_hash in {None, "PENDING"}:
        raise CalibrationError(
            "an adjudicated packet must replace annotation_sha256_12=PENDING with its content hash"
        )
    return frame


def _required_labels(row: pd.Series) -> set[str]:
    answerable = _as_bool(row["answerable"])
    abstained = metrics.is_abstention(row["candidate_answer"])
    required = {"abstention_correct"}
    if answerable:
        required.update({"retrieval_sufficient", "answer_correct"})
    if not abstained:
        required.update({"faithful", "citations_valid"})
    return required


def _case_predictions(
    row: pd.Series,
    section_map: Mapping[str, RetrievalResult],
    thresholds: Mapping[str, float],
) -> dict[str, int | None]:
    section_keys = metrics.split_labels(row["retrieved_sections"])
    missing_sections = [key for key in section_keys if key not in section_map]
    if missing_sections:
        raise CalibrationError(
            f"case {row['case_id']} references unknown sections: {', '.join(missing_sections)}"
        )
    results = [section_map[key] for key in section_keys]
    answerable = _as_bool(row["answerable"])
    recall = metrics.contextual_recall(results, metrics.split_labels(row["evidence_keywords"]))
    answer_scores = metrics.answer_metrics(
        row["candidate_answer"],
        row["question"],
        results,
        answerable,
        row["reference_answer"],
    )
    citation_pass = None
    coverage = answer_scores["citation_coverage"]
    validity = answer_scores["citation_validity"]
    if not math.isnan(coverage):
        citation_pass = int(
            coverage >= float(thresholds["citation_coverage"])
            and not math.isnan(validity)
            and validity >= float(thresholds["citation_validity"])
        )
    return {
        "retrieval_sufficient": _prediction(recall, float(thresholds["contextual_recall"])),
        "faithful": _prediction(answer_scores["faithfulness_proxy"], float(thresholds["faithfulness_proxy"])),
        "citations_valid": citation_pass,
        "answer_correct": _prediction(
            answer_scores["answer_correctness_proxy"],
            float(thresholds["answer_correctness_proxy"]),
        ),
        "abstention_correct": int(answer_scores["abstention_correct"]),
    }


def analyze_calibration(cases: pd.DataFrame, manifest: Mapping[str, Any]) -> CalibrationResult:
    """Compare deterministic predictions with adjudicated human labels."""

    errors: list[str] = []
    comparisons: list[dict[str, Any]] = []
    section_map = _results_by_section()
    thresholds = {name: float(value) for name, value in manifest["thresholds"].items()}

    for _, row in cases.iterrows():
        try:
            predictions = _case_predictions(row, section_map, thresholds)
        except CalibrationError as exc:
            errors.append(str(exc))
            continue

        required = _required_labels(row)
        if row["review_status"] == "adjudicated":
            if not str(row["reviewer_id"]).strip() or not str(row["reviewed_at_utc"]).strip():
                errors.append(f"case {row['case_id']} is adjudicated without reviewer and timestamp")
            for metric_name in required:
                try:
                    label = _parse_label(row[LABEL_COLUMNS[metric_name]])
                except CalibrationError as exc:
                    errors.append(f"case {row['case_id']}: {exc}")
                    continue
                if label is None:
                    errors.append(f"case {row['case_id']} is missing required label {metric_name}")

        for metric_name, column in LABEL_COLUMNS.items():
            try:
                human = _parse_label(row[column])
            except CalibrationError as exc:
                errors.append(f"case {row['case_id']}: {exc}")
                continue
            predicted = predictions[metric_name]
            if human is None or predicted is None:
                continue
            comparisons.append(
                {
                    "case_id": row["case_id"],
                    "question_type": row["question_type"],
                    "metric": metric_name,
                    "predicted": predicted,
                    "human": human,
                    "agreement": int(predicted == human),
                    "error_type": (
                        "false_positive"
                        if predicted == 1 and human == 0
                        else "false_negative"
                        if predicted == 0 and human == 1
                        else ""
                    ),
                }
            )

    comparison_frame = pd.DataFrame(comparisons)
    all_adjudicated = bool((cases["review_status"] == "adjudicated").all())
    status = "CALIBRATED" if all_adjudicated and not errors else "PENDING_HUMAN_REVIEW"
    summaries: list[dict[str, Any]] = []
    if status == "CALIBRATED":
        for metric_name, group in comparison_frame.groupby("metric"):
            confusion = Confusion(
                true_positive=int(((group["predicted"] == 1) & (group["human"] == 1)).sum()),
                false_positive=int(((group["predicted"] == 1) & (group["human"] == 0)).sum()),
                true_negative=int(((group["predicted"] == 0) & (group["human"] == 0)).sum()),
                false_negative=int(((group["predicted"] == 0) & (group["human"] == 1)).sum()),
            )
            low, high = _wilson_interval(confusion.true_positive + confusion.true_negative, confusion.total)
            summaries.append(
                {
                    "metric": metric_name,
                    "n": confusion.total,
                    "tp": confusion.true_positive,
                    "fp": confusion.false_positive,
                    "tn": confusion.true_negative,
                    "fn": confusion.false_negative,
                    "precision": confusion.precision,
                    "recall": confusion.recall,
                    "f1": confusion.f1,
                    "accuracy": confusion.accuracy,
                    "accuracy_ci95_low": low,
                    "accuracy_ci95_high": high,
                }
            )
    return CalibrationResult(
        status=status,
        cases=cases,
        comparisons=comparison_frame,
        summaries=pd.DataFrame(summaries),
        errors=tuple(errors),
    )


def _pct(value: float) -> str:
    return "n/a" if math.isnan(float(value)) else f"{100 * float(value):.1f}%"


def calibration_report(result: CalibrationResult, manifest: Mapping[str, Any]) -> str:
    """Render a report that never publishes calibration scores from pending labels."""

    lines = [
        "# FinGenEval Metric Calibration Report",
        "",
        f"- Status: **{result.status}**",
        f"- Calibration version: `{manifest['calibration_version']}`",
        f"- Evaluator version: `{manifest['evaluator_version']}`",
        f"- Cases: {len(result.cases)}",
        f"- Dataset fingerprint: `{manifest['dataset_sha256_12']}`",
        f"- Probabilistic judge: `{manifest['judge']['status']}` (advisory only)",
        "",
    ]
    if result.status != "CALIBRATED":
        counts = result.cases["review_status"].value_counts().to_dict()
        lines.extend(
            [
                "## Calibration decision",
                "",
                "Insufficient evidence. Human review and adjudication are incomplete, so precision, recall, "
                "confidence intervals, and threshold recommendations are intentionally withheld.",
                "",
                f"Review status counts: `{counts}`.",
            ]
        )
        if result.errors:
            lines.extend(["", "Validation errors:", *[f"- {error}" for error in result.errors]])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "## Deterministic metric agreement",
            "",
            "| Metric | n | Precision | Recall | F1 | Accuracy | Accuracy 95% CI | FP | FN |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in result.summaries.itertuples(index=False):
        lines.append(
            f"| {row.metric} | {row.n} | {_pct(row.precision)} | {_pct(row.recall)} | "
            f"{_pct(row.f1)} | {_pct(row.accuracy)} | "
            f"{_pct(row.accuracy_ci95_low)}–{_pct(row.accuracy_ci95_high)} | {row.fp} | {row.fn} |"
        )

    disagreements = result.comparisons[result.comparisons["agreement"] == 0]
    lines.extend(["", "## Disagreements", ""])
    if disagreements.empty:
        lines.append("No deterministic-versus-human disagreements were recorded in this subset.")
    else:
        lines.extend(
            [
                "| Case | Question type | Metric | Error |",
                "|---|---|---|---|",
                *[
                    f"| {row.case_id} | {row.question_type} | {row.metric} | {row.error_type} |"
                    for row in disagreements.itertuples(index=False)
                ],
            ]
        )
    lines.extend(
        [
            "",
            "## Decision boundary",
            "",
            "Deterministic metrics remain authoritative for automated reporting. Human calibration measures "
            "their limitations; any threshold change requires the approval evidence declared in the manifest. "
            "Probabilistic judge output, when available, is advisory and is never substituted for missing labels.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a versioned FinGenEval calibration packet")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=settings.project_root / "data" / "calibration" / "v1" / "manifest.json",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=settings.project_root / "data" / "calibration" / "v1" / "calibration_cases.csv",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="return success for a structurally valid pending packet (for CI only)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        cases = load_cases(args.cases, manifest)
        result = analyze_calibration(cases, manifest)
    except (OSError, json.JSONDecodeError, CalibrationError) as exc:
        print(f"Calibration validation failed: {exc}")
        return 1
    print(calibration_report(result, manifest), end="")
    return 0 if result.status == "CALIBRATED" or args.validate_only else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
