"""Controlled, bounded agent workflow with typed outputs and deterministic tools.

The local implementation deliberately uses an explicit acyclic graph instead of
recursive delegation. Nodes can later be wrapped by LangGraph without changing
their contracts. Release decisions never come from this module.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from .models import Finding, Project
from .schemas import (
    HandoffOutput,
    IntakeOutput,
    InvestigationOutput,
    ReleaseOutcome,
    RiskGovernanceOutput,
    Role,
    Severity,
    TestDesignOutput,
    TestProposal,
)

T = TypeVar("T", bound=BaseModel)


def return_output(output: T) -> T:
    """Adapter for tracing deterministic tools through the typed agent runner."""
    return output


@dataclass(frozen=True)
class AgentExecution:
    agent_name: str
    step_name: str
    status: str
    attempt: int
    duration_ms: float
    input_summary: dict[str, Any]
    output: dict[str, Any]
    error: str | None = None


class AgentStepError(RuntimeError):
    pass


class ControlledAgentRunner:
    """Run one typed node with a fixed timeout and retry count."""

    def __init__(self, timeout_seconds: float = 5.0, max_retries: int = 1) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def run(
        self,
        agent_name: str,
        step_name: str,
        function: Callable[[], T],
        input_summary: dict[str, Any],
        trace_sink: Callable[[AgentExecution], None],
    ) -> T:
        last_error = None
        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(function)
            try:
                result = future.result(timeout=self.timeout_seconds)
                if not isinstance(result, BaseModel):
                    raise TypeError("agent node did not return a validated schema")
                trace_sink(
                    AgentExecution(
                        agent_name,
                        step_name,
                        "COMPLETE",
                        attempt,
                        (time.perf_counter() - started) * 1000,
                        input_summary,
                        result.model_dump(mode="json"),
                    )
                )
                return result
            except Exception as exc:
                if isinstance(exc, TimeoutError):
                    future.cancel()
                last_error = str(exc)
                trace_sink(
                    AgentExecution(
                        agent_name,
                        step_name,
                        "FAILED",
                        attempt,
                        (time.perf_counter() - started) * 1000,
                        input_summary,
                        {},
                        last_error,
                    )
                )
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
        raise AgentStepError(f"{agent_name}.{step_name} failed after retries: {last_error}")


def intake_agent(project: Project) -> IntakeOutput:
    missing = []
    for field in ("intended_use", "business_owner", "technical_owner", "risk_tier"):
        if not getattr(project, field):
            missing.append(field)
    sufficient = not missing and bool(project.prohibited_uses)
    return IntakeOutput(
        completeness="SUFFICIENT" if sufficient else "MISSING_INFORMATION",
        initial_risk=Severity(project.risk_tier),
        recommendation="CONTINUE" if sufficient else "CLARIFY",
        missing_information=missing,
        rationale=(
            "The use case has owners, explicit boundaries, prohibited uses, and a risk tier."
            if sufficient
            else "Required scope fields must be completed before evaluation."
        ),
    )


def test_design_agent(source_document_ids: list[str]) -> TestDesignOutput:
    """Produce drafts only; generated tests cannot enter an approved dataset."""
    return TestDesignOutput(
        source_document_ids=source_document_ids,
        proposals=[
            TestProposal(
                title="Draft stale-policy contradiction test",
                category="stale_source",
                expected_behavior="Prefer the current approved document and surface the contradiction.",
                permitted_evidence_ids=source_document_ids,
                severity=Severity.HIGH,
                release_blocking=True,
            )
        ],
        human_approval_required=True,
    )


def risk_governance_agent(findings: list[Finding]) -> RiskGovernanceOutput:
    severities = [Severity(item.severity) for item in findings]
    maximum = max(severities, default=Severity.LOW, key=lambda s: list(Severity).index(s))
    if Severity.CRITICAL in severities:
        recommendation = ReleaseOutcome.BLOCK
    elif Severity.HIGH in severities:
        recommendation = ReleaseOutcome.PASS_WITH_CONDITIONS
    else:
        recommendation = ReleaseOutcome.PASS
    return RiskGovernanceOutput(
        finding_ids=[item.id for item in findings],
        risk_categories=sorted({item.category for item in findings}),
        recommended_severity=maximum,
        required_reviewers=[Role.COMPLIANCE_REVIEWER] if findings else [],
        recommendation=recommendation,
        rationale="Recommendation summarizes findings for reviewers; deterministic policy computes the release outcome.",
    )


def investigation_agent(finding: Finding, case_key: str) -> InvestigationOutput:
    stage = (
        "generation" if finding.category in {"incorrect_policy_deadline", "unsupported_numeric"} else "prompt"
    )
    return InvestigationOutput(
        finding_id=finding.id,
        likely_stage=stage,
        confidence=0.82,
        evidence=finding.evidence,
        remediation=finding.recommended_remediation,
        engineering_ticket=(
            f"Correct {case_key}: constrain generated deadlines to retrieved approved evidence, "
            "add an assertion check, and rerun the failed case."
        ),
        rerun_case_ids=[case_key],
    )


def handoff_agent(
    outcome: ReleaseOutcome,
    evidence: list[str],
    owners: dict[str, str],
    open_risks: list[str],
) -> HandoffOutput:
    return HandoffOutput(
        release_outcome=outcome,
        architecture_rationale="Typed agent steps assist review while deterministic rules and human approvals control release.",
        test_evidence=evidence,
        open_risks=open_risks,
        scaling_concerns=[
            "Move eager jobs to a durable distributed queue before concurrent production use.",
            "Use PostgreSQL row-level security and an external identity provider for multi-tenant deployment.",
        ],
        owners=owners,
        monitoring_requirements=[
            "Alert on provider errors, partial runs, critical regressions, overrides, and queue age.",
            "Track latency, token usage, estimated cost, and release-policy outcomes by version.",
        ],
        rollback_guidance="Retain the registered baseline and route traffic back to it if release monitors breach policy.",
        unresolved_decisions=open_risks,
    )
