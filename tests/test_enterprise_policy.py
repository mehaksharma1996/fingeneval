"""Deterministic release rules are tested independently of agents and providers."""

from src.enterprise.policy import RunFacts, compute_release_decision
from src.enterprise.schemas import ReleaseOutcome, RunStatus, Severity


def test_critical_regression_blocks_even_when_run_is_complete():
    decision = compute_release_decision(
        RunFacts(
            status=RunStatus.COMPLETE,
            total_cases=10,
            completed_cases=10,
            provider_errors=0,
            unresolved_regressions=[("aml-sar-deadline", Severity.CRITICAL)],
            baseline_risk_weighted_pass_rate=1.0,
            candidate_risk_weighted_pass_rate=0.95,
        )
    )
    assert decision.outcome == ReleaseOutcome.BLOCK
    triggered = {rule.rule_id for rule in decision.rules if rule.triggered}
    assert "NO_CRITICAL_REGRESSIONS" in triggered
    assert "RISK_WEIGHTED_REGRESSION" in triggered


def test_partial_run_is_insufficient_evidence_even_if_other_cases_pass():
    decision = compute_release_decision(
        RunFacts(
            status=RunStatus.PARTIAL,
            total_cases=6,
            completed_cases=5,
            provider_errors=1,
            baseline_risk_weighted_pass_rate=1.0,
            candidate_risk_weighted_pass_rate=1.0,
        )
    )
    assert decision.outcome == ReleaseOutcome.INSUFFICIENT_EVIDENCE
    assert {r.rule_id for r in decision.rules if r.triggered} == {"RUN_COMPLETE", "PROVIDER_ERROR_BUDGET"}


def test_all_clear_cases_pass():
    decision = compute_release_decision(
        RunFacts(
            status=RunStatus.COMPLETE,
            total_cases=6,
            completed_cases=6,
            provider_errors=0,
            baseline_risk_weighted_pass_rate=1.0,
            candidate_risk_weighted_pass_rate=1.0,
        )
    )
    assert decision.outcome == ReleaseOutcome.PASS
    assert not any(rule.triggered for rule in decision.rules)
