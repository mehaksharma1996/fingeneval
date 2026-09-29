# FinGenEval Enterprise

**Agentic validation and release gating for financial AI systems**

FinGenEval Enterprise helps model-risk, compliance, product, and engineering teams answer one release question: **is a financial AI assistant, copilot, RAG application, or agent safe and reliable enough to release?**

The platform compares a registered production baseline with a release candidate, executes a versioned risk-weighted evaluation pack, exposes case-level evidence and regressions, creates governed findings, and applies deterministic release rules. Its four possible recommendations are `PASS`, `PASS WITH CONDITIONS`, `BLOCK`, and `INSUFFICIENT EVIDENCE`.

The bundled scenario is a synthetic internal AML policy assistant. Candidate version `2.0-regression` looks healthy on most cases but changes a mandatory suspicious-activity-report deadline from 30 to 45 days. The system identifies the unsupported deadline, preserves the authoritative policy citation, creates a critical finding, and blocks the release. A reviewer can record a justified decision, engineering can register remediation, and a targeted rerun validates candidate `2.0-remediated`.

> All bundled policies, organizations, identities, cases, metrics, and outcomes are synthetic. This software and its outputs are not legal, regulatory, compliance, or financial advice. It is designed to support evaluation and governance workflows; it has not been independently assessed for compliance with any law or standard.

## Why aggregate scores are insufficient

A candidate can improve average retrieval or answer quality while failing one business-critical deadline, threshold, access boundary, or tool-permission case. FinGenEval preserves aggregate metrics but releases are controlled by case severity and explicit rules. One unresolved critical regression blocks a release even when a weighted average rises.

## What is agentic—and what remains deterministic

The controlled workflow has typed, bounded steps for intake and scoping, test design, evidence verification, risk summarization, failure investigation, remediation, and production handoff. Each step has validated output, timeout/retry behavior, and a persisted trace. Test proposals remain drafts until human approval.

Metric computation, run completeness, authorization, and the final release gate are deterministic. Agents cannot approve a test, override a decision, mutate a release policy, or recursively delegate work. A human override requires an authorized role, a justification, a timestamp, and an audit event.

## Architecture

```text
React/TypeScript workflow UI
            |
        FastAPI /api/v1  -- correlation IDs, RBAC, OpenAPI
            |
  application service + controlled agent graph
            |
 deterministic evaluation + versioned release policy
            |
 SQLAlchemy repositories -- SQLite local / PostgreSQL production target
            |
 local object storage -- S3-compatible production target
```

The original Streamlit retrieval inspector remains available as a legacy engineering tool. The product workflow is the React application and FastAPI service. The original 45-question retrieval benchmark, retrievers, lexical metrics, Gemini adapter, and saved artifacts are preserved.

See [architecture](docs/architecture.md), [API](docs/api.md), [threat model](docs/threat-model.md), and [deployment](docs/deployment.md).

## Run locally without paid credentials

Prerequisites: Python 3.11+, Node.js 22+, and npm.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn src.enterprise.api:app --reload
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Choose **Load synthetic AML workspace**, then **Start baseline comparison**. No model credential is needed; the deterministic provider is the default.

The same full flow can run from the command line against a fresh database:

```powershell
python -m scripts.demo_enterprise
```

Docker is the shortest integrated path:

```powershell
docker compose up --build
```

Open `http://localhost:8080`. API documentation is at `http://localhost:8000/docs`.

## Demo flow

1. Load the synthetic AML project, registered baseline/candidate, approved dataset, and release policy.
2. Start the comparison. Local eager execution persists all six case results.
3. Open **Finding detail** to compare the correct 30-day baseline with the candidate's unsupported 45-day deadline and inspect the authoritative evidence identifier.
4. Open **Release decision** to see every rule and the rules that caused `BLOCK`.
5. Optionally record the synthetic compliance override; the computed decision remains immutable while the effective decision records the human action.
6. Record remediation and rerun the failed case. The new version passes and the finding moves to `RESOLVED`.
7. Generate the validation/handoff report. The database stores its object key and SHA-256 digest.

The interview script is in [portfolio-walkthrough.md](docs/portfolio-walkthrough.md).

## Tests and engineering checks

```powershell
python -m pytest -q
python -m ruff check src tests
python -m mypy src/enterprise
python -m alembic upgrade head
python -m alembic check

cd frontend
npm run lint
npm test
npm run build
```

The credential-free end-to-end test covers project loading, baseline/candidate execution, the critical AML regression, `BLOCK`, reviewer override, audit history, remediation, targeted rerun, `PASS`, finding resolution, and report generation. Failure-mode coverage includes partial provider failure, invalid citations, unsupported deadlines, unauthorized roles, and cross-tenant access.

The CI workflow adds formatting, type checking, dependency audits, Bandit, CodeQL, Gitleaks, container builds, Trivy, and migration validation.

## Configuration

Copy `.env.example` to `.env` and use placeholders only. Core enterprise settings:

| Variable | Local default | Purpose |
|---|---|---|
| `FINGENEVAL_DATABASE_URL` | `sqlite:///.../fingeneval.db` | SQLAlchemy database URL |
| `FINGENEVAL_EXECUTION_MODE` | `eager` | `eager` or local `threaded` execution |
| `FINGENEVAL_LOCAL_AUTH_ENABLED` | `true` | Enables synthetic-user bootstrap; disable outside local development |
| `FINGENEVAL_REPORT_DIR` | `reports/generated` | Local object-storage root |
| `GEMINI_API_KEY` | unset | Optional legacy Gemini generation adapter |

## Repository map

- `src/enterprise/`: domain, policy engine, controlled agents, providers, persistence, jobs, API, authorization, observability, reports
- `frontend/`: accessible React/TypeScript workflow UI
- `data/packs/`: reusable AML and complaint-handling evaluation packs
- `src/`: preserved retrieval/evaluation harness
- `tests/`: legacy and enterprise unit/integration/end-to-end tests
- `migrations/`: Alembic database lifecycle
- `docs/engagements/aml-assistant/`: forward-deployed discovery-to-handoff record
- `patterns/`: reusable contracts and extension guidance
- `deploy/`: reference deployment assets

## Known limitations

- Local authentication uses a synthetic `X-User-Id` boundary. Production requires OIDC/SAML validation, short-lived tokens, and centralized policy enforcement.
- Tenant IDs and tenant-filtered queries are implemented; PostgreSQL row-level security and independent penetration testing remain required for true multi-tenant production.
- Eager and threaded workers are development adapters. Production needs a durable queue, leases, heartbeats, distributed cancellation, and dead-letter recovery.
- The deterministic provider proves workflow behavior, not real model quality. The legacy lexical metrics cannot reliably detect negation or subtle semantic errors and need calibrated NLI/LLM judging plus human labels.
- Local reports use the filesystem. S3-compatible storage, retention enforcement, legal hold, deletion verification, and tamper-evident audit export are documented production work.
- The included load test is a configuration only; no scale result is claimed.
- Generic project/dataset authoring is API/domain work in progress; the completed vertical slice loads the approved AML demonstration project.

Prioritized remaining work is tracked in [docs/next-steps.md](docs/next-steps.md).
