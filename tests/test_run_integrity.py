"""Benchmark artifact integrity and evidence-status tests."""

from __future__ import annotations

import copy

import pandas as pd
import pytest

from src.report_generator import generate_governance_report
from src.run_integrity import RunIntegrityError, load_saved_run, validate_run
from src.settings import settings


@pytest.fixture(scope="module")
def retrieval_run() -> tuple[pd.DataFrame, dict[str, object]]:
    return load_saved_run(settings.results_dir / "retrieval_only_topk3")


@pytest.fixture(scope="module")
def partial_run() -> tuple[pd.DataFrame, dict[str, object]]:
    return load_saved_run(settings.results_dir / "gemini_strict_topk3")


def test_committed_retrieval_run_is_complete_but_not_deployable(retrieval_run):
    frame, metadata = retrieval_run
    integrity = validate_run(frame, metadata)
    assert integrity.status == "RETRIEVAL_ONLY_COMPLETE"
    assert integrity.actual_rows == integrity.expected_rows == 180
    assert not integrity.deployable_evidence


def test_committed_partial_generation_is_diagnostic_only(partial_run):
    frame, metadata = partial_run
    integrity = validate_run(frame, metadata)
    report = generate_governance_report(frame, metadata)
    assert integrity.status == "PARTIAL_GENERATION"
    assert integrity.generation_modes == {"generation_error": 161, "llm": 19}
    assert not integrity.deployable_evidence
    assert "diagnostic only" in report.lower()
    assert "no end-to-end configuration" in report.lower()
    assert "Insufficient evidence" in report


def test_duplicate_benchmark_key_fails_validation(retrieval_run):
    frame, metadata = retrieval_run
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(RunIntegrityError, match="duplicate benchmark keys"):
        validate_run(duplicated, metadata)


def test_incomplete_matrix_fails_validation(retrieval_run):
    frame, metadata = retrieval_run
    with pytest.raises(RunIntegrityError, match="expected 180 rows"):
        validate_run(frame.iloc[:-1], metadata)


def test_dataset_fingerprint_mismatch_fails_validation(retrieval_run):
    frame, metadata = retrieval_run
    corrupted = copy.deepcopy(metadata)
    corrupted["dataset_sha256_12"] = "000000000000"
    with pytest.raises(RunIntegrityError, match="dataset fingerprint mismatch"):
        validate_run(frame, corrupted)


def test_retrieval_only_answer_metric_contamination_fails(retrieval_run):
    frame, metadata = retrieval_run
    contaminated = frame.copy()
    contaminated.loc[0, "faithfulness_proxy"] = 1.0
    with pytest.raises(RunIntegrityError, match="non-LLM rows contain answer-level metrics"):
        validate_run(contaminated, metadata)


def test_replayed_rows_are_prominent_in_status(partial_run):
    frame, metadata = partial_run
    replayed = copy.deepcopy(metadata)
    replayed["reused_llm_rows"] = 19
    replayed.pop("run_status", None)
    integrity = validate_run(frame, replayed)
    assert integrity.status == "PARTIAL_GENERATION_REPLAYED"
