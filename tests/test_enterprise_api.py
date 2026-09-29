"""API/database integration checks for auth boundaries and error contracts."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.enterprise import api as api_module
from src.enterprise.models import Base, User
from src.enterprise.security import get_db
from src.enterprise.service import EnterpriseService


def test_demo_bootstrap_and_authenticated_release_run(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    def override_db():
        yield session

    api_module.app.dependency_overrides[get_db] = override_db

    class SameSessionDispatcher:
        def submit_run(self, run_id, actor):
            EnterpriseService(session).execute_run(run_id, actor)

    monkeypatch.setattr(api_module, "dispatcher", SameSessionDispatcher())
    try:
        client = TestClient(api_module.app)
        demo = client.post("/api/v1/demo/bootstrap")
        assert demo.status_code == 201
        assert demo.json()["synthetic"] is True

        anonymous = client.get("/api/v1/projects")
        assert anonymous.status_code == 401

        evaluator = session.scalar(select(User).where(User.role == "EVALUATOR"))
        response = client.get("/api/v1/projects", headers={"X-User-Id": evaluator.id})
        assert response.status_code == 200
        assert response.json()["items"][0]["name"] == "AML Policy Assistant Release Validation"
        assert response.headers["X-Correlation-Id"]

        project_id = response.json()["items"][0]["id"]
        created = client.post(
            f"/api/v1/projects/{project_id}/runs",
            headers={"X-User-Id": evaluator.id, "Idempotency-Key": "api-e2e"},
        )
        assert created.status_code == 202
        assert created.json()["status"] == "COMPLETE"
        detail = client.get(f"/api/v1/runs/{created.json()['id']}", headers={"X-User-Id": evaluator.id})
        assert detail.status_code == 200
        assert detail.json()["decision"]["outcome"] == "BLOCK"
        assert len(detail.json()["case_results"]) == 6
    finally:
        api_module.app.dependency_overrides.clear()
        session.close()
