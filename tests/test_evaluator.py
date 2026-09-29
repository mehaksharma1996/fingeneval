"""Evaluator behavior tests that avoid model downloads and API calls."""

import math

import pandas as pd
import pytest

from src import evaluator, llm
from src.report_generator import generate_governance_report


@pytest.fixture
def api_key(monkeypatch):
    """Pretend a Gemini key is configured without calling the API."""
    object.__setattr__(llm.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(llm.rate_limiter, "wait", lambda: None)


def test_retrieval_only_rows_have_no_answer_metrics():
    frame, metadata = evaluator.run_evaluation(["bm25"], ["strict_governance"], 3)
    assert len(frame) == metadata["questions"]
    assert set(frame["generation_mode"]) == {llm.MODE_RETRIEVAL_ONLY}
    assert frame["faithfulness_proxy"].isna().all()
    assert frame["citation_coverage"].isna().all()
    assert frame["hallucination_risk"].isna().all()
    assert "Insufficient evidence" in generate_governance_report(frame, metadata)
    unanswerable = frame[frame["answerable"] == 0]
    assert unanswerable["reciprocal_rank"].isna().all()


def test_generation_latency_excludes_rate_limit_wait(api_key, monkeypatch):
    waits = []
    monkeypatch.setattr(llm.rate_limiter, "wait", lambda: waits.append(1))
    monkeypatch.setattr(llm, "call_gemini", lambda prompt: "A SAR is due within 30 days [1].")
    answer = llm.answer_question("q", [], "strict_governance")
    assert waits == [1]
    assert answer.mode == llm.MODE_LLM
    assert answer.latency_seconds is not None and answer.latency_seconds < 0.5


def test_generation_errors_are_recorded_not_scored(api_key, monkeypatch):
    def boom(prompt):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(llm, "call_gemini", boom)
    row = evaluator.load_questions().iloc[0]
    record = evaluator.evaluate_row(row, "bm25", "strict_governance", evaluator.RetrievalEngine(), 3)
    assert record["generation_mode"] == llm.MODE_ERROR
    assert math.isnan(record["faithfulness_proxy"])


def test_report_applies_gates_to_llm_rows():
    base = {
        "question_type": "exact_threshold",
        "retrieval_method": "bm25",
        "prompt_style": "strict_governance",
        "hit_at_k": 1.0,
        "reciprocal_rank": 1.0,
        "contextual_precision": 1.0,
        "contextual_recall": 1.0,
        "section_recall": 1.0,
        "retrieval_latency_seconds": 0.001,
        "generation_mode": llm.MODE_LLM,
        "generation_latency_seconds": 0.8,
        "faithfulness_proxy": 1.0,
        "citation_coverage": 1.0,
        "citation_validity": 1.0,
        "hallucination_risk": 0.0,
        "answer_correctness_proxy": 0.9,
        "abstained": 0.0,
    }
    answered_unanswerable = {
        **base,
        "question": "unanswerable",
        "answerable": 0,
        "hit_at_k": math.nan,
        "reciprocal_rank": math.nan,
        "contextual_precision": math.nan,
        "contextual_recall": math.nan,
        "section_recall": math.nan,
        "hallucination_risk": 1.0,
        "abstained": 0.0,
    }
    frame = pd.DataFrame([{**base, "question": "answerable", "answerable": 1}, answered_unanswerable])
    report = generate_governance_report(frame, {})
    assert "High risk" in report
    assert "Correct abstention (unanswerable)" in report


def test_per_minute_rate_limit_is_retried_and_wait_not_timed(api_key, monkeypatch):
    calls = []
    sleeps = []

    def flaky(prompt):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED ... PerMinute ... Please retry in 7.5s.")
        return "ok [1]"

    monkeypatch.setattr(llm, "call_gemini", flaky)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    answer = llm.answer_question("q", [], "strict_governance")
    assert answer.mode == llm.MODE_LLM
    assert len(calls) == 2
    assert sleeps == [8.5]
    assert answer.latency_seconds < 0.5


def test_daily_quota_stops_further_api_calls(api_key, monkeypatch):
    calls = []

    def exhausted(prompt):
        calls.append(1)
        raise RuntimeError(
            "429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
        )

    monkeypatch.setattr(llm, "call_gemini", exhausted)
    llm.reset_daily_quota_flag()
    first = llm.answer_question("q", [], "strict_governance")
    second = llm.answer_question("q", [], "strict_governance")
    llm.reset_daily_quota_flag()
    assert first.mode == second.mode == llm.MODE_ERROR
    assert len(calls) == 1
    assert "skipped call" in second.error


def test_resume_reuses_successful_llm_rows(api_key, monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "call_gemini", lambda prompt: "A SAR must be filed within 30 days [1].")
    first, _ = evaluator.run_evaluation(["bm25"], ["strict_governance"], 3)
    first.loc[first.index[1:], "generation_mode"] = llm.MODE_ERROR
    path = tmp_path / "previous.csv"
    first.to_csv(path, index=False)

    calls = []
    monkeypatch.setattr(llm, "call_gemini", lambda prompt: calls.append(1) or "Answer [1].")
    second, metadata = evaluator.run_evaluation(["bm25"], ["strict_governance"], 3, resume_from=path)
    assert metadata["reused_llm_rows"] == 1
    assert len(calls) == len(second) - 1
    assert second.iloc[0]["answer"] == first.iloc[0]["answer"]
