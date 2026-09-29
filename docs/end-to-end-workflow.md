# End-to-end workflow

FinGenEval Enterprise is the primary product path. It evaluates a registered baseline and release candidate against approved financial-policy cases; it does not serve end-user financial questions directly.

## Runtime path

1. The React UI calls `POST /api/v1/demo/bootstrap` to create the synthetic tenant, users, project, baseline, candidate, approved documents, evaluation pack, and release policy.
2. `POST /api/v1/projects/{project_id}/runs` binds the latest approved baseline, candidate, dataset, and policy into an immutable evaluation run.
3. The dispatcher executes the run immediately in local `eager` mode or through the local thread adapter in `threaded` mode.
4. For each approved case, the provider reads `input_text`, restricts the corpus to the case's approved source documents, chunks the Markdown policies, and retrieves the top BM25 evidence.
5. The credential-free local generator returns a deterministic response only after retrieval. The synthetic candidate deliberately changes the SAR deadline from 30 to 45 days so the workflow contains one reproducible regression.
6. Deterministic evaluation compares baseline and candidate answers, citations, required evidence, abstention behavior, and unsupported numeric claims. Each response persists its retrieval method and retrieved evidence IDs.
7. Regressions become findings. The service aggregates completed case facts and passes them to the pure release-policy function.
8. The policy produces `PASS`, `PASS_WITH_CONDITIONS`, `BLOCK`, or `INSUFFICIENT_EVIDENCE`. Controlled agent steps may summarize evidence, but they cannot alter this computed outcome.
9. Authorized reviewers can append a review or override. Remediation creates a new candidate version and a targeted rerun linked to the original run.
10. The final Markdown report records evidence, policy triggers, human actions, open risks, monitoring, rollback guidance, and a SHA-256 digest.

## Local execution

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

Open `http://localhost:5173`, load the synthetic AML workspace, and start the baseline comparison. The finding detail displays the retrieved evidence used for both responses.

For a UI-free smoke test:

```powershell
python -m scripts.demo_enterprise
```

The expected sequence is an initial `BLOCK`, a verified targeted remediation, a rerun `PASS`, and a generated report object with a content digest.

## Relationship to the Streamlit benchmark

`app.py` remains a separate engineering interface for exploring queries and benchmarking BM25, vector, hybrid, and reranked retrieval across `data/eval/test_questions.csv`. Both applications share the same document loading, chunking, and retrieval modules. The React/FastAPI workflow adds versioned systems, tenant ownership, findings, release policy, human review, remediation, audit history, and reports.
