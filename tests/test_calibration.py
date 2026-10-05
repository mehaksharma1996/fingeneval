"""Fail-closed human calibration analysis tests."""

from __future__ import annotations

import copy
import json

import pytest

from src.calibration import (
    CalibrationError,
    analyze_calibration,
    calibration_report,
    load_cases,
    load_manifest,
)
from src.settings import settings

CALIBRATION_DIR = settings.project_root / "data" / "calibration" / "v1"


def test_pending_packet_withholds_calibration_scores():
    manifest = load_manifest(CALIBRATION_DIR / "manifest.json")
    cases = load_cases(CALIBRATION_DIR / "calibration_cases.csv", manifest)
    result = analyze_calibration(cases, manifest)
    report = calibration_report(result, manifest)

    assert result.status == "PENDING_HUMAN_REVIEW"
    assert result.summaries.empty
    assert "Insufficient evidence" in report
    assert "precision, recall" in report
    assert "Review status counts: `{'pending': 12}`" in report


def test_adjudicated_synthetic_fixture_reports_false_positives():
    manifest = load_manifest(CALIBRATION_DIR / "manifest.json")
    cases = load_cases(CALIBRATION_DIR / "calibration_cases.csv", manifest).copy()
    for column in (
        "human_retrieval_sufficient",
        "human_faithful",
        "human_citations_valid",
        "human_answer_correct",
        "human_abstention_correct",
    ):
        cases[column] = "1"
    cases.loc[cases["case_id"].isin(["CAL-002", "CAL-003", "CAL-007", "CAL-010"]), "human_faithful"] = "0"
    cases.loc[cases["case_id"].isin(["CAL-004", "CAL-005"]), "human_citations_valid"] = "0"
    cases.loc[
        cases["case_id"].isin(["CAL-002", "CAL-003", "CAL-007", "CAL-008", "CAL-010"]), "human_answer_correct"
    ] = "0"
    cases.loc[cases["case_id"].isin(["CAL-007", "CAL-008"]), "human_abstention_correct"] = "0"
    cases["reviewer_id"] = "synthetic-test-reviewer"
    cases["reviewed_at_utc"] = "2026-10-05T00:00:00Z"
    cases["review_status"] = "adjudicated"

    result = analyze_calibration(cases, manifest)
    report = calibration_report(result, manifest)

    assert result.status == "CALIBRATED"
    assert not result.summaries.empty
    assert "Precision" in report
    assert "false_positive" in report


def test_missing_required_adjudicated_label_fails_closed():
    manifest = load_manifest(CALIBRATION_DIR / "manifest.json")
    cases = load_cases(CALIBRATION_DIR / "calibration_cases.csv", manifest).copy()
    cases.loc[0, "review_status"] = "adjudicated"
    cases.loc[0, "reviewer_id"] = "reviewer"
    cases.loc[0, "reviewed_at_utc"] = "2026-10-05T00:00:00Z"

    result = analyze_calibration(cases, manifest)

    assert result.status == "PENDING_HUMAN_REVIEW"
    assert any("missing required label" in error for error in result.errors)


def test_threshold_change_requires_recorded_approval(tmp_path):
    manifest = load_manifest(CALIBRATION_DIR / "manifest.json")
    changed = copy.deepcopy(manifest)
    changed["thresholds"]["faithfulness_proxy"] = 0.75
    changed["threshold_change"] = None

    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(CalibrationError, match="threshold changes require"):
        load_manifest(path)


def test_invalid_human_label_is_reported():
    manifest = load_manifest(CALIBRATION_DIR / "manifest.json")
    cases = load_cases(CALIBRATION_DIR / "calibration_cases.csv", manifest).copy()
    cases.loc[0, "human_faithful"] = "maybe"

    result = analyze_calibration(cases, manifest)

    assert any("invalid human label" in error for error in result.errors)
