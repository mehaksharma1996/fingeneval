"""Credential-free end-to-end release workflow over an in-memory database."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.enterprise.models import (
    AuditEvent,
    Base,
    CaseResult,
    Finding,
    ReleaseDecision,
    User,
)
from src.enterprise.providers import DeterministicProvider
from src.enterprise.schemas import ApprovalAction, ApprovalRequest, RemediationRequest, Role
from src.enterprise.security import ServiceActor
from src.enterprise.service import EnterpriseService, ServiceError
from src.enterprise.storage import ObjectStorage


class MemoryStorage(ObjectStorage):
    def __init__(self):
        self.items = {}

    def put_text(self, object_key: str, content: str):
        import hashlib

        self.items[object_key] = content
        return object_key, hashlib.sha256(content.encode()).hexdigest()


def session_and_demo(provider=None):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    storage = MemoryStorage()
    service = EnterpriseService(
        session, provider=provider, storage=storage, correlation_id="test-correlation"
    )
    demo = service.bootstrap_demo()
    users = {user.role: user for user in session.scalars(select(User)).all()}
    evaluator = ServiceActor(users[Role.EVALUATOR.value].id, demo["tenant_id"], Role.EVALUATOR)
    reviewer = ServiceActor(
        users[Role.COMPLIANCE_REVIEWER.value].id, demo["tenant_id"], Role.COMPLIANCE_REVIEWER
    )
    return session, service, storage, demo, evaluator, reviewer


def test_critical_regression_review_remediation_rerun_and_report():
    session, service, storage, demo, evaluator, reviewer = session_and_demo()
    run = service.create_run(demo["project_id"], evaluator, "e2e-critical-regression")
    run = service.execute_run(run.id, evaluator)
    assert run.status == "COMPLETE"

    case_results = list(session.scalars(select(CaseResult).where(CaseResult.run_id == run.id)))
    assert len(case_results) == 6
    sar_result = next(
        item for item in case_results if "45 calendar days" in item.candidate_response["answer"]
    )
    assert sar_result.baseline_response["retrieval_method"] == "bm25"
    assert (
        "aml_transaction_monitoring_policy.md#SAR Filing Timelines"
        in sar_result.baseline_response["retrieved_evidence"]
    )
    assert sum(item.regression for item in case_results) == 1

    decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.run_id == run.id))
    assert decision.outcome == "BLOCK"
    triggered = {item["rule_id"] for item in decision.rule_results if item["triggered"]}
    assert {
        "NO_CRITICAL_REGRESSIONS",
        "MANDATORY_COMPLIANCE_CASES",
        "UNSUPPORTED_NUMERIC_CLAIMS",
    } <= triggered

    finding = session.scalar(select(Finding).where(Finding.run_id == run.id))
    assert finding.severity == "CRITICAL"
    assert "45 calendar days" in finding.description
    assert finding.evidence == ["aml_transaction_monitoring_policy.md#SAR Filing Timelines"]

    approval = service.record_approval(
        decision.id,
        ApprovalRequest(
            action=ApprovalAction.OVERRIDE,
            justification="Time-limited synthetic demo override with monitoring and documented rollback.",
        ),
        reviewer,
    )
    assert approval.action == "OVERRIDE"
    assert decision.effective_outcome == "PASS_WITH_CONDITIONS"

    remediation, rerun = service.remediate_and_rerun(
        finding.id,
        RemediationRequest(
            description="Bind deadline claims to approved evidence and reject unsupported numeric assertions.",
            owner_user_id=evaluator.user_id,
        ),
        evaluator,
    )
    assert rerun.status == "COMPLETE"
    rerun_decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.run_id == rerun.id))
    assert rerun_decision.outcome == "PASS"
    assert remediation.status == "VERIFIED"
    assert finding.status == "RESOLVED"

    report = service.generate_report(rerun.id, evaluator)
    assert report.object_key in storage.items
    assert "Computed decision: **PASS**" in storage.items[report.object_key]
    assert "## Evaluated system versions" in storage.items[report.object_key]
    assert "Retrieval: `bm25 (top_k=3)`" in storage.items[report.object_key]
    assert "Data source version: `aml-policy/1.0`" in storage.items[report.object_key]
    assert session.scalar(select(AuditEvent).where(AuditEvent.event_type == "FINDING_RESOLVED"))
    assert service.run_detail(run.id, evaluator)["agent_traces"]


def test_partial_provider_failure_cannot_produce_successful_decision():
    provider = DeterministicProvider(fail_case_ids=frozenset({"aml-alert-escalation"}))
    session, service, _, demo, evaluator, _ = session_and_demo(provider)
    run = service.create_run(demo["project_id"], evaluator, "partial-provider")
    service.execute_run(run.id, evaluator)
    decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.run_id == run.id))
    assert run.status == "PARTIAL"
    assert decision.outcome == "INSUFFICIENT_EVIDENCE"
    assert run.error_summary


def test_evaluator_cannot_override_release_decision():
    session, service, _, demo, evaluator, _ = session_and_demo()
    run = service.create_run(demo["project_id"], evaluator, "unauthorized-override")
    service.execute_run(run.id, evaluator)
    decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.run_id == run.id))
    try:
        service.record_approval(
            decision.id,
            ApprovalRequest(
                action=ApprovalAction.OVERRIDE,
                justification="Evaluator attempts an override without the required compliance role.",
            ),
            evaluator,
        )
    except ServiceError as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("evaluator was allowed to override a release decision")


def test_tenant_filter_prevents_cross_tenant_access():
    session, service, _, demo, evaluator, _ = session_and_demo()
    run = service.create_run(demo["project_id"], evaluator, "tenant-boundary")
    outsider = ServiceActor(evaluator.user_id, "other-tenant", Role.ADMIN)
    try:
        service.run_detail(run.id, outsider)
    except ServiceError as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("cross-tenant run access was allowed")
