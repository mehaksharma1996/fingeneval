"""Run the credential-free AML release workflow and print auditable outcomes."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from src.enterprise.db import SessionLocal, create_schema
from src.enterprise.models import Finding, ReleaseDecision, User
from src.enterprise.schemas import RemediationRequest, Role
from src.enterprise.security import ServiceActor
from src.enterprise.service import EnterpriseService


def main() -> None:
    create_schema()
    with SessionLocal() as session:
        service = EnterpriseService(session)
        demo = service.bootstrap_demo()
        evaluator_user = session.scalar(
            select(User).where(User.tenant_id == demo["tenant_id"], User.role == Role.EVALUATOR.value)
        )
        if evaluator_user is None:
            raise RuntimeError("Synthetic evaluator was not created")
        actor = ServiceActor(evaluator_user.id, demo["tenant_id"], Role.EVALUATOR)
        run = service.create_run(demo["project_id"], actor, f"cli-demo:{uuid.uuid4()}")
        service.execute_run(run.id, actor)
        decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.run_id == run.id))
        finding = session.scalar(select(Finding).where(Finding.run_id == run.id))
        if decision is None or finding is None:
            raise RuntimeError("Expected synthetic blocking decision and finding were not produced")
        initial_finding_status = finding.status
        remediation, rerun = service.remediate_and_rerun(
            finding.id,
            RemediationRequest(
                description="Bind deadline claims to approved evidence and reject unsupported numbers.",
                owner_user_id=actor.user_id,
            ),
            actor,
        )
        rerun_decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.run_id == rerun.id))
        report = service.generate_report(rerun.id, actor)
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "initial_run": {"id": run.id, "status": run.status, "decision": decision.outcome},
                    "critical_finding": {
                        "id": finding.id,
                        "initial_status": initial_finding_status,
                        "final_status": finding.status,
                    },
                    "remediation": {"id": remediation.id, "status": remediation.status},
                    "targeted_rerun": {
                        "id": rerun.id,
                        "status": rerun.status,
                        "decision": rerun_decision.outcome if rerun_decision else None,
                    },
                    "report": {"object_key": report.object_key, "sha256": report.content_sha256},
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
