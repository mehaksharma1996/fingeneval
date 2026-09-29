"""Versioned deterministic release-gate engine, independent of all agents."""

from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import PolicyRuleResult, ReleaseDecisionContract, ReleaseOutcome, Role, RunStatus, Severity


@dataclass(frozen=True)
class RunFacts:
    status: RunStatus
    total_cases: int
    completed_cases: int
    provider_errors: int
    unresolved_regressions: list[tuple[str, Severity]] = field(default_factory=list)
    mandatory_failed_case_ids: list[str] = field(default_factory=list)
    invalid_citation_rate: float = 0.0
    unsupported_numeric_case_ids: list[str] = field(default_factory=list)
    baseline_risk_weighted_pass_rate: float = 0.0
    candidate_risk_weighted_pass_rate: float = 0.0
    open_high_finding_ids: list[str] = field(default_factory=list)


DEFAULT_POLICY = {
    "version": "aml-release-policy/1.0.0",
    "max_invalid_citation_rate": 0.05,
    "max_risk_weighted_drop": 0.02,
    "block_unsupported_numeric_claims": True,
    "required_approvals_for_high": [Role.COMPLIANCE_REVIEWER.value],
}


def _rule(rule_id: str, description: str, triggered: bool, outcome=None, evidence=None) -> PolicyRuleResult:
    return PolicyRuleResult(
        rule_id=rule_id,
        description=description,
        triggered=triggered,
        outcome=outcome if triggered else None,
        evidence=evidence or [],
    )


def compute_release_decision(
    facts: RunFacts,
    policy: dict | None = None,
) -> ReleaseDecisionContract:
    config = {**DEFAULT_POLICY, **(policy or {})}
    incomplete = facts.status != RunStatus.COMPLETE or facts.completed_cases != facts.total_cases
    critical = [
        case_id for case_id, severity in facts.unresolved_regressions if severity == Severity.CRITICAL
    ]
    drop = facts.baseline_risk_weighted_pass_rate - facts.candidate_risk_weighted_pass_rate
    rules = [
        _rule(
            "RUN_COMPLETE",
            "Every selected case completed successfully.",
            incomplete,
            ReleaseOutcome.INSUFFICIENT_EVIDENCE,
            [f"status={facts.status}", f"completed={facts.completed_cases}/{facts.total_cases}"],
        ),
        _rule(
            "PROVIDER_ERROR_BUDGET",
            "Provider errors must be zero for a release decision.",
            facts.provider_errors > 0,
            ReleaseOutcome.INSUFFICIENT_EVIDENCE,
            [f"provider_errors={facts.provider_errors}"],
        ),
        _rule(
            "NO_CRITICAL_REGRESSIONS",
            "No unresolved critical regression is allowed.",
            bool(critical),
            ReleaseOutcome.BLOCK,
            critical,
        ),
        _rule(
            "MANDATORY_COMPLIANCE_CASES",
            "All mandatory compliance cases must pass.",
            bool(facts.mandatory_failed_case_ids),
            ReleaseOutcome.BLOCK,
            facts.mandatory_failed_case_ids,
        ),
        _rule(
            "CITATION_INVALIDITY",
            "Invalid citation rate must remain within policy tolerance.",
            facts.invalid_citation_rate > config["max_invalid_citation_rate"],
            ReleaseOutcome.BLOCK,
            [f"rate={facts.invalid_citation_rate:.3f}", f"limit={config['max_invalid_citation_rate']:.3f}"],
        ),
        _rule(
            "UNSUPPORTED_NUMERIC_CLAIMS",
            "Unsupported numeric, rate, threshold, date, or deadline claims are release blocking.",
            bool(facts.unsupported_numeric_case_ids) and config["block_unsupported_numeric_claims"],
            ReleaseOutcome.BLOCK,
            facts.unsupported_numeric_case_ids,
        ),
        _rule(
            "RISK_WEIGHTED_REGRESSION",
            "Risk-weighted candidate quality may not drop beyond the configured tolerance.",
            drop > config["max_risk_weighted_drop"],
            ReleaseOutcome.BLOCK,
            [f"drop={drop:.3f}", f"limit={config['max_risk_weighted_drop']:.3f}"],
        ),
        _rule(
            "HIGH_FINDING_APPROVAL",
            "Open high-severity findings require compliance approval and conditions.",
            bool(facts.open_high_finding_ids),
            ReleaseOutcome.PASS_WITH_CONDITIONS,
            facts.open_high_finding_ids,
        ),
    ]
    triggered = [item for item in rules if item.triggered]
    if any(item.outcome == ReleaseOutcome.INSUFFICIENT_EVIDENCE for item in triggered):
        outcome = ReleaseOutcome.INSUFFICIENT_EVIDENCE
    elif any(item.outcome == ReleaseOutcome.BLOCK for item in triggered):
        outcome = ReleaseOutcome.BLOCK
    elif any(item.outcome == ReleaseOutcome.PASS_WITH_CONDITIONS for item in triggered):
        outcome = ReleaseOutcome.PASS_WITH_CONDITIONS
    else:
        outcome = ReleaseOutcome.PASS
    required = (
        [Role(value) for value in config["required_approvals_for_high"]]
        if facts.open_high_finding_ids
        else []
    )
    rationale = (
        f"{outcome.value}: " + "; ".join(item.description for item in triggered)
        if triggered
        else "PASS: all configured release-policy rules passed."
    )
    return ReleaseDecisionContract(
        outcome=outcome,
        policy_version=config["version"],
        rules=rules,
        required_approvals=required,
        rationale=rationale,
    )
