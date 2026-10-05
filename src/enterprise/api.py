"""Experimental local governance API around the FinGenEval assets."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import enterprise_settings
from .db import create_schema
from .jobs import dispatcher
from .models import Project, User
from .observability import CorrelationMiddleware, prometheus_metrics
from .schemas import ApprovalRequest, ErrorContract, RemediationRequest, Role
from .security import actor_from_user, current_user, get_db, require_roles
from .service import EnterpriseService, ServiceError, _safe_dict

logging.basicConfig(level=enterprise_settings.log_level, format="%(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="FinGenEval Governance Prototype API",
    version="0.1.0",
    description=(
        "Experimental local workflow for deterministic release-gate demonstrations. "
        "It is not the supported FinGenEval product path; bundled data and outcomes are synthetic."
    ),
    lifespan=lifespan,
)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-User-Id", "X-Correlation-Id", "Idempotency-Key"],
)


def correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", str(uuid.uuid4()))


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    contract = ErrorContract(code=exc.code, message=str(exc), correlation_id=correlation_id(request))
    return JSONResponse(status_code=exc.status_code, content=contract.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    contract = ErrorContract(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        correlation_id=correlation_id(request),
        details={"errors": exc.errors()},
    )
    return JSONResponse(status_code=422, content=contract.model_dump(mode="json"))


@app.get("/health/live", tags=["operations"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["operations"])
def readiness(session: Session = Depends(get_db)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}


@app.get("/metrics", response_class=PlainTextResponse, tags=["operations"])
def metrics() -> str:
    return prometheus_metrics()


@app.post("/api/v1/demo/bootstrap", status_code=201, tags=["demo"])
def bootstrap_demo(session: Session = Depends(get_db)) -> dict:
    if not enterprise_settings.local_auth_enabled:
        raise HTTPException(status_code=404, detail="Local demo bootstrap is disabled")
    return EnterpriseService(session).bootstrap_demo()


@app.get("/api/v1/dashboard", tags=["dashboard"])
def dashboard(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict:
    return EnterpriseService(session).dashboard(actor_from_user(user))


@app.get("/api/v1/projects", tags=["projects"])
def list_projects(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    name: str | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict:
    statement = select(Project).where(Project.tenant_id == user.tenant_id)
    if name:
        statement = statement.where(Project.name.ilike(f"%{name}%"))
    items = list(session.scalars(statement.offset(offset).limit(limit)))
    return {"items": [_safe_dict(item) for item in items], "limit": limit, "offset": offset}


@app.post("/api/v1/projects/{project_id}/runs", status_code=202, tags=["runs"])
def create_run(
    project_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: User = Depends(require_roles(Role.EVALUATOR, Role.ADMIN)),
    session: Session = Depends(get_db),
) -> dict:
    actor = actor_from_user(user)
    run = EnterpriseService(session).create_run(project_id, actor, idempotency_key)
    if run.status == "QUEUED":
        dispatcher.submit_run(run.id, actor)
        session.refresh(run)
    return _safe_dict(run)


@app.get("/api/v1/runs/{run_id}", tags=["runs"])
def get_run(run_id: str, user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict:
    return EnterpriseService(session).run_detail(run_id, actor_from_user(user))


@app.post("/api/v1/runs/{run_id}/cancel", tags=["runs"])
def cancel_run(
    run_id: str,
    user: User = Depends(require_roles(Role.EVALUATOR, Role.ADMIN)),
    session: Session = Depends(get_db),
) -> dict:
    return _safe_dict(EnterpriseService(session).cancel_run(run_id, actor_from_user(user)))


@app.post("/api/v1/release-decisions/{decision_id}/reviews", status_code=201, tags=["governance"])
def review_decision(
    decision_id: str,
    request: ApprovalRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict:
    return _safe_dict(EnterpriseService(session).record_approval(decision_id, request, actor_from_user(user)))


@app.post("/api/v1/findings/{finding_id}/remediate-and-rerun", status_code=202, tags=["findings"])
def remediate_and_rerun(
    finding_id: str,
    request: RemediationRequest,
    user: User = Depends(require_roles(Role.EVALUATOR, Role.ADMIN)),
    session: Session = Depends(get_db),
) -> dict:
    remediation, run = EnterpriseService(session).remediate_and_rerun(
        finding_id, request, actor_from_user(user)
    )
    return {"remediation": _safe_dict(remediation), "rerun": _safe_dict(run)}


@app.post("/api/v1/runs/{run_id}/reports", status_code=201, tags=["reports"])
def generate_report(
    run_id: str,
    user: User = Depends(require_roles(Role.EVALUATOR, Role.COMPLIANCE_REVIEWER, Role.ADMIN)),
    session: Session = Depends(get_db),
) -> dict:
    return _safe_dict(EnterpriseService(session).generate_report(run_id, actor_from_user(user)))
