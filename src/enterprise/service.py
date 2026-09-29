"""Application service for the complete baseline/candidate release workflow."""

from __future__ import annotations

import hashlib
import json
import uuid
from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agents import (
    AgentExecution,
    ControlledAgentRunner,
    handoff_agent,
    intake_agent,
    investigation_agent,
    return_output,
    risk_governance_agent,
)
from .evaluation import compare_case
from .models import (
    AgentTrace,
    AuditEvent,
    CaseResult,
    DatasetVersion,
    DataSource,
    Document,
    DocumentVersion,
    EvaluationCase,
    EvaluationRun,
    Finding,
    GeneratedReport,
    HumanApproval,
    MetricResult,
    Project,
    PromptVersion,
    RegisteredAISystem,
    ReleaseDecision,
    ReleaseOverride,
    ReleasePolicy,
    Remediation,
    RetrievalConfiguration,
    SystemVersion,
    Tenant,
    User,
    utc_now,
)
from .policy import DEFAULT_POLICY, RunFacts, compute_release_decision
from .providers import DeterministicProvider, ModelProvider, ProviderError
from .schemas import (
    ApprovalAction,
    ApprovalRequest,
    CaseStatus,
    FindingStatus,
    ReleaseOutcome,
    RemediationRequest,
    Role,
    RunStatus,
    Severity,
    SystemResponse,
)
from .security import ServiceActor
from .storage import LocalObjectStorage, ObjectStorage

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _safe_dict(model) -> dict[str, Any]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


class EnterpriseService:
    def __init__(
        self,
        session: Session,
        provider: ModelProvider | None = None,
        storage: ObjectStorage | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.session = session
        self.provider = provider or DeterministicProvider()
        self.storage = storage or LocalObjectStorage()
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.agent_runner = ControlledAgentRunner(timeout_seconds=5, max_retries=1)

    def audit(
        self,
        actor: ServiceActor | None,
        event_type: str,
        entity_type: str,
        entity_id: str,
        detail: dict[str, Any],
        tenant_id: str | None = None,
    ) -> None:
        resolved_tenant = actor.tenant_id if actor else tenant_id
        if not resolved_tenant:
            raise ValueError("audit event requires a tenant")
        self.session.add(
            AuditEvent(
                tenant_id=resolved_tenant,
                actor_user_id=actor.user_id if actor else None,
                correlation_id=self.correlation_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail,
            )
        )

    def _tenant_entity(self, model, entity_id: str, actor: ServiceActor):
        entity = self.session.scalar(
            select(model).where(model.id == entity_id, model.tenant_id == actor.tenant_id)
        )
        if not entity:
            raise ServiceError("NOT_FOUND", f"{model.__name__} was not found", 404)
        return entity

    def _trace_sink(self, run: EvaluationRun):
        def sink(execution: AgentExecution) -> None:
            self.session.add(
                AgentTrace(
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    agent_name=execution.agent_name,
                    step_name=execution.step_name,
                    status=execution.status,
                    attempt=execution.attempt,
                    duration_ms=execution.duration_ms,
                    input_summary=execution.input_summary,
                    output=execution.output,
                    error=execution.error,
                )
            )

        return sink

    def bootstrap_demo(self) -> dict[str, Any]:
        existing = self.session.scalar(select(Tenant).where(Tenant.slug == "synthetic-bank"))
        if existing:
            project = self.session.scalar(select(Project).where(Project.tenant_id == existing.id))
            if project is None:
                raise ServiceError("DEMO_CORRUPT", "Synthetic tenant has no project", 500)
            retrievals = list(
                self.session.scalars(
                    select(RetrievalConfiguration).where(
                        RetrievalConfiguration.tenant_id == existing.id,
                        RetrievalConfiguration.project_id == project.id,
                    )
                )
            )
            systems = list(
                self.session.scalars(
                    select(SystemVersion).where(
                        SystemVersion.tenant_id == existing.id,
                        SystemVersion.project_id == project.id,
                    )
                )
            )
            for retrieval_config in retrievals:
                retrieval_config.name = "BM25 retrieval"
                retrieval_config.configuration = {"method": "bm25", "top_k": 3, "reranker": None}
            for system in systems:
                system.retrieval_config = {"method": "bm25", "top_k": 3}
            users = self.session.scalars(select(User).where(User.tenant_id == existing.id)).all()
            self.session.commit()
            return {
                "tenant_id": existing.id,
                "project_id": project.id,
                "users": {user.role: user.id for user in users},
                "synthetic": True,
                "existing": True,
            }

        tenant = Tenant(name="Synthetic Bank", slug="synthetic-bank")
        self.session.add(tenant)
        self.session.flush()
        admin = User(
            tenant_id=tenant.id,
            email="admin@synthetic.invalid",
            display_name="Demo Admin",
            role=Role.ADMIN.value,
        )
        evaluator = User(
            tenant_id=tenant.id,
            email="evaluator@synthetic.invalid",
            display_name="Demo Evaluator",
            role=Role.EVALUATOR.value,
        )
        reviewer = User(
            tenant_id=tenant.id,
            email="reviewer@synthetic.invalid",
            display_name="Demo Compliance Reviewer",
            role=Role.COMPLIANCE_REVIEWER.value,
        )
        self.session.add_all([admin, evaluator, reviewer])
        self.session.flush()
        project = Project(
            tenant_id=tenant.id,
            name="AML Policy Assistant Release Validation",
            intended_use=(
                "Evaluate an internal synthetic AML policy assistant before release, with evidence-backed "
                "answers for trained operations and compliance staff."
            ),
            prohibited_uses=[
                "Legal or regulatory advice",
                "Autonomous filing or case disposition",
                "Access to another tenant's documents",
            ],
            business_owner="AML Operations",
            technical_owner="Financial AI Platform",
            risk_tier=Severity.CRITICAL.value,
            required_approver_roles=[Role.COMPLIANCE_REVIEWER.value],
        )
        self.session.add(project)
        self.session.flush()
        registered_system = RegisteredAISystem(
            tenant_id=tenant.id,
            project_id=project.id,
            name="AML Policy Assistant",
            description="Synthetic internal assistant evaluated for policy-grounded answers and safe abstention.",
            owner="Financial AI Platform",
        )
        prompt_v1_text = "Answer only from approved evidence and cite every supported claim."
        prompt_v2_text = "Answer from approved evidence using concise operational language and citations."
        prompt_v1 = PromptVersion(
            tenant_id=tenant.id,
            project_id=project.id,
            name="Strict governance",
            version="1",
            template_hash=hashlib.sha256(prompt_v1_text.encode()).hexdigest(),
            template=prompt_v1_text,
            approved_by=reviewer.id,
        )
        prompt_v2 = PromptVersion(
            tenant_id=tenant.id,
            project_id=project.id,
            name="Strict governance",
            version="2",
            template_hash=hashlib.sha256(prompt_v2_text.encode()).hexdigest(),
            template=prompt_v2_text,
            approved_by=reviewer.id,
        )
        retrieval = RetrievalConfiguration(
            tenant_id=tenant.id,
            project_id=project.id,
            name="BM25 retrieval",
            version="1",
            configuration={"method": "bm25", "top_k": 3, "reranker": None},
        )
        data_source = DataSource(
            tenant_id=tenant.id,
            project_id=project.id,
            name="Synthetic approved policy corpus",
            source_type="LOCAL_MARKDOWN",
            classification="SYNTHETIC",
            access_policy={"roles": [Role.EVALUATOR.value, Role.COMPLIANCE_REVIEWER.value]},
        )
        self.session.add_all([registered_system, prompt_v1, prompt_v2, retrieval, data_source])
        self.session.flush()
        for source_name in ("aml_transaction_monitoring_policy.md", "ai_governance_policy.md"):
            source_path = PROJECT_ROOT / "data" / "docs" / source_name
            document = Document(
                tenant_id=tenant.id,
                data_source_id=data_source.id,
                external_key=source_name,
                title=source_name.removesuffix(".md").replace("_", " ").title(),
                status="APPROVED",
            )
            self.session.add(document)
            self.session.flush()
            self.session.add(
                DocumentVersion(
                    tenant_id=tenant.id,
                    document_id=document.id,
                    version="1.0",
                    content_hash=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    object_key=f"data/docs/{source_name}",
                    effective_at=utc_now(),
                    approved_by=reviewer.id,
                )
            )
        baseline = SystemVersion(
            tenant_id=tenant.id,
            project_id=project.id,
            registered_system_id=registered_system.id,
            prompt_version_id=prompt_v1.id,
            retrieval_configuration_id=retrieval.id,
            name="AML Assistant",
            version="1.0-baseline",
            kind="BASELINE",
            model_provider="deterministic-local",
            model_name="fingeneval-fixture",
            prompt_version="strict-governance/1",
            retrieval_config={"method": "bm25", "top_k": 3},
            tool_config={"filing_tool": "disabled"},
            data_source_version="aml-policy/1.0",
        )
        candidate = SystemVersion(
            tenant_id=tenant.id,
            project_id=project.id,
            registered_system_id=registered_system.id,
            prompt_version_id=prompt_v2.id,
            retrieval_configuration_id=retrieval.id,
            name="AML Assistant",
            version="2.0-regression",
            kind="CANDIDATE",
            model_provider="deterministic-local",
            model_name="fingeneval-fixture",
            prompt_version="strict-governance/2",
            retrieval_config={"method": "bm25", "top_k": 3},
            tool_config={"filing_tool": "disabled"},
            data_source_version="aml-policy/1.0",
        )
        self.session.add_all([baseline, candidate])
        pack_path = PROJECT_ROOT / "data" / "packs" / "aml_assistant.json"
        raw = pack_path.read_bytes()
        pack = json.loads(raw)
        dataset = DatasetVersion(
            tenant_id=tenant.id,
            project_id=project.id,
            name=pack["name"],
            version=pack["version"],
            status="APPROVED",
            content_hash=hashlib.sha256(raw).hexdigest(),
            created_by=evaluator.id,
            approved_by=reviewer.id,
            approved_at=utc_now(),
        )
        policy = ReleasePolicy(
            tenant_id=tenant.id,
            project_id=project.id,
            name="Critical AML Release Gate",
            version=DEFAULT_POLICY["version"],
            rules=DEFAULT_POLICY,
        )
        self.session.add_all([dataset, policy])
        self.session.flush()
        for item in pack["cases"]:
            self.session.add(
                EvaluationCase(
                    tenant_id=tenant.id,
                    dataset_version_id=dataset.id,
                    case_key=item["id"],
                    title=item["title"],
                    input_text=item["input_text"],
                    business_process=item["business_process"],
                    category=item["category"],
                    source_document_ids=item["source_document_ids"],
                    expected_behavior=item["expected_behavior"],
                    reference_answer=item["reference_answer"],
                    required_evidence=item["required_evidence"],
                    answerability=item["answerability"],
                    severity=item["severity"],
                    risk_weight=item["risk_weight"],
                    release_blocking=item["release_blocking"],
                    abstention_expected=item["abstention_expected"],
                    freshness_requirement=item["freshness_requirement"],
                    mandatory_review_role=item["mandatory_review_role"],
                    tags=item["tags"],
                    version=item["version"],
                    status=CaseStatus.APPROVED.value,
                    created_by=evaluator.id,
                    approved_by=reviewer.id,
                    approved_at=utc_now(),
                )
            )
        self.audit(None, "DEMO_BOOTSTRAPPED", "project", project.id, {"synthetic": True}, tenant.id)
        self.session.commit()
        return {
            "tenant_id": tenant.id,
            "project_id": project.id,
            "baseline_system_version_id": baseline.id,
            "candidate_system_version_id": candidate.id,
            "dataset_version_id": dataset.id,
            "release_policy_id": policy.id,
            "users": {admin.role: admin.id, evaluator.role: evaluator.id, reviewer.role: reviewer.id},
            "synthetic": True,
            "existing": False,
        }

    def create_run(self, project_id: str, actor: ServiceActor, idempotency_key: str) -> EvaluationRun:
        project = self._tenant_entity(Project, project_id, actor)
        existing = self.session.scalar(
            select(EvaluationRun).where(
                EvaluationRun.tenant_id == actor.tenant_id,
                EvaluationRun.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing
        baseline = self.session.scalar(
            select(SystemVersion)
            .where(
                SystemVersion.project_id == project.id,
                SystemVersion.tenant_id == actor.tenant_id,
                SystemVersion.kind == "BASELINE",
            )
            .order_by(SystemVersion.created_at.desc())
        )
        candidate = self.session.scalar(
            select(SystemVersion)
            .where(
                SystemVersion.project_id == project.id,
                SystemVersion.tenant_id == actor.tenant_id,
                SystemVersion.kind == "CANDIDATE",
            )
            .order_by(SystemVersion.created_at.desc())
        )
        dataset = self.session.scalar(
            select(DatasetVersion)
            .where(
                DatasetVersion.project_id == project.id,
                DatasetVersion.tenant_id == actor.tenant_id,
                DatasetVersion.status == "APPROVED",
            )
            .order_by(DatasetVersion.created_at.desc())
        )
        policy = self.session.scalar(
            select(ReleasePolicy)
            .where(
                ReleasePolicy.project_id == project.id,
                ReleasePolicy.tenant_id == actor.tenant_id,
                ReleasePolicy.active.is_(True),
            )
            .order_by(ReleasePolicy.created_at.desc())
        )
        if baseline is None or candidate is None or dataset is None or policy is None:
            raise ServiceError(
                "PROJECT_INCOMPLETE", "Project requires baseline, candidate, dataset, and policy"
            )
        run = EvaluationRun(
            tenant_id=actor.tenant_id,
            project_id=project.id,
            baseline_system_version_id=baseline.id,
            candidate_system_version_id=candidate.id,
            dataset_version_id=dataset.id,
            release_policy_id=policy.id,
            idempotency_key=idempotency_key,
            status=RunStatus.QUEUED.value,
            stage="QUEUED",
            progress_percent=0,
            selected_case_ids=[],
        )
        self.session.add(run)
        self.session.flush()
        intake = self.agent_runner.run(
            "IntakeAndScopingAgent",
            "qualify",
            lambda: intake_agent(project),
            {"project_id": project.id},
            self._trace_sink(run),
        )
        if intake.recommendation != "CONTINUE":
            run.status = RunStatus.FAILED.value
            run.stage = "INTAKE_FAILED"
            run.error_summary = intake.rationale
        self.audit(actor, "RUN_CREATED", "evaluation_run", run.id, {"idempotency_key": idempotency_key})
        self.session.commit()
        return run

    def execute_run(self, run_id: str, actor: ServiceActor) -> EvaluationRun:
        run = self._tenant_entity(EvaluationRun, run_id, actor)
        if run.status == RunStatus.COMPLETE.value:
            return run
        if run.status in {RunStatus.CANCELLED.value, RunStatus.FAILED.value}:
            raise ServiceError("RUN_NOT_EXECUTABLE", f"Run is {run.status}", 409)
        baseline = self._tenant_entity(SystemVersion, run.baseline_system_version_id, actor)
        candidate = self._tenant_entity(SystemVersion, run.candidate_system_version_id, actor)
        policy = self._tenant_entity(ReleasePolicy, run.release_policy_id, actor)
        statement = select(EvaluationCase).where(
            EvaluationCase.dataset_version_id == run.dataset_version_id,
            EvaluationCase.tenant_id == actor.tenant_id,
            EvaluationCase.status == CaseStatus.APPROVED.value,
        )
        if run.selected_case_ids:
            statement = statement.where(EvaluationCase.id.in_(run.selected_case_ids))
        cases = list(self.session.scalars(statement.order_by(EvaluationCase.case_key)))
        if not cases:
            raise ServiceError("NO_APPROVED_CASES", "Run has no approved evaluation cases", 409)
        run.status = RunStatus.RUNNING.value
        run.stage = "EVALUATING_CASES"
        run.started_at = utc_now()
        run.progress_percent = 1
        self.session.flush()
        errors = 0
        evaluations: list[tuple[EvaluationCase, Any, CaseResult]] = []
        findings: list[Finding] = []
        for index, case in enumerate(cases, start=1):
            error = None
            try:
                baseline_response = self.provider.generate(case, baseline)
                candidate_response = self.provider.generate(case, candidate)
                comparison = compare_case(case, baseline_response, candidate_response)
                verification = comparison.evidence_verification
                self.agent_runner.run(
                    "EvidenceVerificationAgent",
                    "verify_claims",
                    partial(return_output, verification),
                    {"case_id": case.case_key, "response_role": "CANDIDATE"},
                    self._trace_sink(run),
                )
            except ProviderError as exc:
                errors += 1
                error = str(exc)
                placeholder = SystemResponse(
                    answer="",
                    citations=[],
                    latency_ms=0,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost_usd=0,
                    provider_request_id="provider-error",
                )
                baseline_response = candidate_response = placeholder
                comparison = None
            result = CaseResult(
                tenant_id=actor.tenant_id,
                run_id=run.id,
                case_id=case.id,
                baseline_response=baseline_response.model_dump(mode="json"),
                candidate_response=candidate_response.model_dump(mode="json"),
                metrics=(
                    {
                        "citation_validity": comparison.citation_validity,
                        "evidence_coverage": comparison.evidence_coverage,
                        "unsupported_numeric_claims": comparison.unsupported_numeric_claims,
                        "risk_weight": comparison.risk_weight,
                        "evidence_verification": comparison.evidence_verification.model_dump(mode="json"),
                    }
                    if comparison
                    else {}
                ),
                baseline_passed=comparison.baseline_passed if comparison else False,
                candidate_passed=comparison.candidate_passed if comparison else False,
                regression=comparison.regression if comparison else False,
                improvement=comparison.improvement if comparison else False,
                mandatory_failed=comparison.mandatory_failed if comparison else False,
                error=error,
            )
            self.session.add(result)
            self.session.flush()
            if comparison:
                for metric_name, value, unit in (
                    ("citation_validity", comparison.citation_validity, "ratio"),
                    ("evidence_coverage", comparison.evidence_coverage, "ratio"),
                    ("unsupported_numeric_claims", float(comparison.unsupported_numeric_claims), "count"),
                    ("candidate_latency", comparison.candidate.latency_ms, "milliseconds"),
                    ("candidate_estimated_cost", comparison.candidate.estimated_cost_usd, "usd"),
                ):
                    self.session.add(
                        MetricResult(
                            tenant_id=actor.tenant_id,
                            run_id=run.id,
                            case_result_id=result.id,
                            metric_name=metric_name,
                            value=value,
                            unit=unit,
                            evaluator_version="enterprise-core/1.0.0",
                            details={"synthetic": True},
                        )
                    )
            evaluations.append((case, comparison, result))
            if comparison and comparison.regression:
                finding = Finding(
                    tenant_id=actor.tenant_id,
                    run_id=run.id,
                    case_result_id=result.id,
                    title=f"Candidate regression: {case.title}",
                    category=case.category,
                    severity=case.severity,
                    status=FindingStatus.OPEN.value,
                    owner_user_id=actor.user_id,
                    description=(
                        f"The baseline passed but the candidate failed `{case.case_key}`. "
                        f"Candidate response: {candidate_response.answer}"
                    ),
                    evidence=case.required_evidence,
                    likely_failure_stage="generation",
                    recommended_remediation=(
                        "Constrain numeric and deadline claims to approved retrieved evidence, then rerun this case."
                    ),
                )
                self.session.add(finding)
                self.session.flush()
                findings.append(finding)
                self.agent_runner.run(
                    "FailureInvestigationAndRemediationAgent",
                    "investigate",
                    partial(investigation_agent, finding, case.case_key),
                    {"finding_id": finding.id, "case_id": case.case_key},
                    self._trace_sink(run),
                )
            run.progress_percent = int(index / len(cases) * 80)
            self.session.flush()

        run.status = RunStatus.PARTIAL.value if errors else RunStatus.COMPLETE.value
        run.stage = "APPLYING_RELEASE_POLICY"
        run.progress_percent = 90
        total_weight = sum(case.risk_weight for case, _, _ in evaluations)
        baseline_pass = sum(
            case.risk_weight for case, comp, _ in evaluations if comp and comp.baseline_passed
        )
        candidate_pass = sum(
            case.risk_weight for case, comp, _ in evaluations if comp and comp.candidate_passed
        )
        invalid = [comp for _, comp, _ in evaluations if comp and comp.citation_validity < 1]
        facts = RunFacts(
            status=RunStatus(run.status),
            total_cases=len(cases),
            completed_cases=len(cases) - errors,
            provider_errors=errors,
            unresolved_regressions=[
                (case.case_key, Severity(case.severity))
                for case, comp, _ in evaluations
                if comp and comp.regression
            ],
            mandatory_failed_case_ids=[
                case.case_key for case, comp, _ in evaluations if comp and comp.mandatory_failed
            ],
            invalid_citation_rate=len(invalid) / max(len(cases) - errors, 1),
            unsupported_numeric_case_ids=[
                case.case_key for case, comp, _ in evaluations if comp and comp.unsupported_numeric_claims
            ],
            baseline_risk_weighted_pass_rate=baseline_pass / total_weight if total_weight else 0,
            candidate_risk_weighted_pass_rate=candidate_pass / total_weight if total_weight else 0,
            open_high_finding_ids=[
                f.id for f in findings if f.severity in {Severity.HIGH.value, Severity.CRITICAL.value}
            ],
        )
        contract = compute_release_decision(facts, policy.rules)
        decision = ReleaseDecision(
            tenant_id=actor.tenant_id,
            run_id=run.id,
            outcome=contract.outcome.value,
            policy_version=contract.policy_version,
            rule_results=[item.model_dump(mode="json") for item in contract.rules],
            rationale=contract.rationale,
            required_approvals=[item.value for item in contract.required_approvals],
            effective_outcome=contract.outcome.value,
        )
        self.session.add(decision)
        self.session.flush()
        self.agent_runner.run(
            "RiskAndGovernanceAgent",
            "summarize_findings",
            lambda: risk_governance_agent(findings),
            {"finding_ids": [item.id for item in findings]},
            self._trace_sink(run),
        )
        run.stage = "COMPLETE" if not errors else "PARTIAL_PROVIDER_FAILURE"
        run.progress_percent = 100
        run.completed_at = utc_now()
        if errors:
            run.error_summary = (
                f"{errors} case(s) had provider errors; no release recommendation can be treated as complete."
            )
        self.audit(
            actor,
            "RUN_COMPLETED" if not errors else "RUN_PARTIAL",
            "evaluation_run",
            run.id,
            {"status": run.status, "decision": decision.outcome, "provider_errors": errors},
        )
        self.session.commit()
        return run

    def cancel_run(self, run_id: str, actor: ServiceActor) -> EvaluationRun:
        run = self._tenant_entity(EvaluationRun, run_id, actor)
        if run.status in {RunStatus.COMPLETE.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}:
            raise ServiceError("RUN_TERMINAL", f"Run is already {run.status}", 409)
        run.status = RunStatus.CANCELLED.value
        run.stage = "CANCELLED"
        run.cancelled_at = utc_now()
        self.audit(actor, "RUN_CANCELLED", "evaluation_run", run.id, {})
        self.session.commit()
        return run

    def record_approval(
        self, decision_id: str, request: ApprovalRequest, actor: ServiceActor
    ) -> HumanApproval:
        decision = self._tenant_entity(ReleaseDecision, decision_id, actor)
        allowed = {Role.COMPLIANCE_REVIEWER, Role.BUSINESS_OWNER, Role.ADMIN}
        if actor.role not in allowed:
            raise ServiceError("FORBIDDEN", "Reviewer role is required", 403)
        if request.action == ApprovalAction.OVERRIDE and actor.role not in {
            Role.COMPLIANCE_REVIEWER,
            Role.ADMIN,
        }:
            raise ServiceError("FORBIDDEN", "Compliance reviewer or admin role is required for override", 403)
        approval = HumanApproval(
            tenant_id=actor.tenant_id,
            decision_id=decision.id,
            user_id=actor.user_id,
            user_role=actor.role.value,
            action=request.action.value,
            justification=request.justification,
        )
        self.session.add(approval)
        self.session.flush()
        if request.action == ApprovalAction.REJECT:
            decision.effective_outcome = ReleaseOutcome.BLOCK.value
        elif request.action == ApprovalAction.OVERRIDE:
            decision.effective_outcome = ReleaseOutcome.PASS_WITH_CONDITIONS.value
            self.session.add(
                ReleaseOverride(
                    tenant_id=actor.tenant_id,
                    decision_id=decision.id,
                    approval_id=approval.id,
                    original_outcome=decision.outcome,
                    effective_outcome=decision.effective_outcome,
                    justification=request.justification,
                )
            )
        self.audit(
            actor,
            "RELEASE_DECISION_REVIEWED",
            "release_decision",
            decision.id,
            {
                "action": request.action.value,
                "computed": decision.outcome,
                "effective": decision.effective_outcome,
            },
        )
        self.session.commit()
        return approval

    def remediate_and_rerun(
        self,
        finding_id: str,
        request: RemediationRequest,
        actor: ServiceActor,
    ) -> tuple[Remediation, EvaluationRun]:
        finding = self._tenant_entity(Finding, finding_id, actor)
        original_run = self._tenant_entity(EvaluationRun, finding.run_id, actor)
        original_candidate = self._tenant_entity(
            SystemVersion, original_run.candidate_system_version_id, actor
        )
        case_result = self._tenant_entity(CaseResult, finding.case_result_id, actor)
        fixed = SystemVersion(
            tenant_id=actor.tenant_id,
            project_id=original_candidate.project_id,
            registered_system_id=original_candidate.registered_system_id,
            prompt_version_id=original_candidate.prompt_version_id,
            retrieval_configuration_id=original_candidate.retrieval_configuration_id,
            name=original_candidate.name,
            version="2.0-remediated",
            kind="CANDIDATE",
            model_provider=original_candidate.model_provider,
            model_name=original_candidate.model_name,
            prompt_version="strict-governance/2.1",
            retrieval_config=original_candidate.retrieval_config,
            tool_config=original_candidate.tool_config,
            data_source_version=original_candidate.data_source_version,
        )
        self.session.add(fixed)
        self.session.flush()
        rerun = EvaluationRun(
            tenant_id=actor.tenant_id,
            project_id=original_run.project_id,
            baseline_system_version_id=original_run.baseline_system_version_id,
            candidate_system_version_id=fixed.id,
            dataset_version_id=original_run.dataset_version_id,
            release_policy_id=original_run.release_policy_id,
            parent_run_id=original_run.id,
            idempotency_key=f"remediation:{finding.id}:{fixed.version}",
            status=RunStatus.QUEUED.value,
            stage="TARGETED_RERUN_QUEUED",
            progress_percent=0,
            selected_case_ids=[case_result.case_id],
        )
        self.session.add(rerun)
        self.session.flush()
        remediation = Remediation(
            tenant_id=actor.tenant_id,
            finding_id=finding.id,
            description=request.description,
            owner_user_id=request.owner_user_id,
            status="READY_FOR_RERUN",
            rerun_id=rerun.id,
        )
        self.session.add(remediation)
        finding.status = FindingStatus.READY_FOR_RERUN.value
        self.audit(actor, "REMEDIATION_RECORDED", "finding", finding.id, {"rerun_id": rerun.id})
        self.session.commit()
        self.execute_run(rerun.id, actor)
        self.session.refresh(rerun)
        rerun_result = self.session.scalar(select(CaseResult).where(CaseResult.run_id == rerun.id))
        if rerun.status == RunStatus.COMPLETE.value and rerun_result and rerun_result.candidate_passed:
            finding.status = FindingStatus.RESOLVED.value
            remediation.status = "VERIFIED"
            self.audit(actor, "FINDING_RESOLVED", "finding", finding.id, {"verified_by_run_id": rerun.id})
            self.session.commit()
        return remediation, rerun

    def generate_report(self, run_id: str, actor: ServiceActor) -> GeneratedReport:
        run = self._tenant_entity(EvaluationRun, run_id, actor)
        decision = self.session.scalar(
            select(ReleaseDecision).where(
                ReleaseDecision.run_id == run.id, ReleaseDecision.tenant_id == actor.tenant_id
            )
        )
        if not decision:
            raise ServiceError("DECISION_NOT_AVAILABLE", "Run has no release decision", 409)
        project = self._tenant_entity(Project, run.project_id, actor)
        results = list(self.session.scalars(select(CaseResult).where(CaseResult.run_id == run.id)))
        findings = list(self.session.scalars(select(Finding).where(Finding.run_id == run.id)))
        evidence = [f"case_result:{result.id}" for result in results]
        open_risks = [item.title for item in findings if item.status != FindingStatus.RESOLVED.value]
        handoff = self.agent_runner.run(
            "HandoffAgent",
            "build_handoff",
            lambda: handoff_agent(
                ReleaseOutcome(decision.effective_outcome),
                evidence,
                {"business": project.business_owner, "technical": project.technical_owner},
                open_risks,
            ),
            {"run_id": run.id, "decision_id": decision.id},
            self._trace_sink(run),
        )
        triggered = [item for item in decision.rule_results if item["triggered"]]
        lines = [
            "# FinGenEval Enterprise Validation and Handoff Report",
            "",
            "> Synthetic demonstration. This report is not legal, regulatory, compliance, or financial advice.",
            "",
            f"- Run: `{run.id}`",
            f"- Status: **{run.status}**",
            f"- Computed decision: **{decision.outcome}**",
            f"- Effective decision after human review: **{decision.effective_outcome}**",
            f"- Policy: `{decision.policy_version}`",
            "",
            "## Triggered policy rules",
            *[
                f"- `{item['rule_id']}`: {item['description']} Evidence: {', '.join(item['evidence'])}"
                for item in triggered
            ],
            "",
            "## Case evidence",
            *[
                f"- `{result.id}`: baseline={'PASS' if result.baseline_passed else 'FAIL'}, "
                f"candidate={'PASS' if result.candidate_passed else 'FAIL'}, regression={result.regression}"
                for result in results
            ],
            "",
            "## Open risks",
            *([f"- {risk}" for risk in handoff.open_risks] or ["- None recorded for this run."]),
            "",
            "## Monitoring and rollback",
            *[f"- {item}" for item in handoff.monitoring_requirements],
            f"- {handoff.rollback_guidance}",
            "",
            "## Limitations",
            "- Policies and identities are synthetic; local results do not establish legal or regulatory compliance.",
            "- The deterministic provider validates workflow behavior, not production model quality.",
            "- Local SQLite/eager execution requires PostgreSQL, external identity, and distributed workers for production.",
        ]
        content = "\n".join(lines)
        object_key, digest = self.storage.put_text(
            f"{actor.tenant_id}/{run.id}/validation-report.md", content
        )
        report = GeneratedReport(
            tenant_id=actor.tenant_id,
            run_id=run.id,
            format="markdown",
            object_key=object_key,
            content_sha256=digest,
            generated_by=actor.user_id,
        )
        self.session.add(report)
        self.audit(
            actor, "REPORT_GENERATED", "evaluation_run", run.id, {"object_key": object_key, "sha256": digest}
        )
        self.session.commit()
        return report

    def run_detail(self, run_id: str, actor: ServiceActor) -> dict[str, Any]:
        run = self._tenant_entity(EvaluationRun, run_id, actor)
        results = list(self.session.scalars(select(CaseResult).where(CaseResult.run_id == run.id)))
        findings = list(self.session.scalars(select(Finding).where(Finding.run_id == run.id)))
        decision = self.session.scalar(select(ReleaseDecision).where(ReleaseDecision.run_id == run.id))
        traces = list(self.session.scalars(select(AgentTrace).where(AgentTrace.run_id == run.id)))
        audits = list(
            self.session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.tenant_id == actor.tenant_id,
                    AuditEvent.entity_id.in_([run.id] + [item.id for item in findings]),
                )
                .order_by(AuditEvent.created_at)
            )
        )
        return {
            "run": _safe_dict(run),
            "case_results": [_safe_dict(item) for item in results],
            "findings": [_safe_dict(item) for item in findings],
            "decision": _safe_dict(decision) if decision else None,
            "agent_traces": [_safe_dict(item) for item in traces],
            "audit_timeline": [_safe_dict(item) for item in audits],
        }

    def dashboard(self, actor: ServiceActor) -> dict[str, Any]:
        projects = list(self.session.scalars(select(Project).where(Project.tenant_id == actor.tenant_id)))
        runs = list(
            self.session.scalars(
                select(EvaluationRun)
                .where(EvaluationRun.tenant_id == actor.tenant_id)
                .order_by(EvaluationRun.created_at.desc())
                .limit(10)
            )
        )
        critical = list(
            self.session.scalars(
                select(Finding).where(
                    Finding.tenant_id == actor.tenant_id,
                    Finding.severity == Severity.CRITICAL.value,
                    Finding.status != FindingStatus.RESOLVED.value,
                )
            )
        )
        return {
            "synthetic": True,
            "projects": [_safe_dict(item) for item in projects],
            "recent_runs": [_safe_dict(item) for item in runs],
            "open_critical_findings": len(critical),
            "operational_health": "HEALTHY",
        }
