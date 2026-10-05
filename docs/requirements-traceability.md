# Requirements traceability

| Supported capability | Repository evidence | Current boundary |
|---|---|---|
| Offline reproducible evaluation | `src/evaluator.py`, saved run metadata | Hosted generation still depends on provider availability and quota |
| Section-aware financial-policy ingestion | `src/document_loader.py`, `src/chunking.py`, `data/docs/` | Markdown-only synthetic corpus |
| Retrieval comparison | `src/retrievers.py` | BM25, exact FAISS vector, weighted hybrid, and optional cross-encoder reranking |
| Labeled benchmark | `data/eval/test_questions.csv`, `tests/test_dataset.py` | 45 questions over seven synthetic documents |
| Retrieval metrics | `src/metrics.py`, `tests/test_metrics.py` | Deterministic labels and lexical evidence matching |
| Answer-quality proxies | `src/metrics.py`, `tests/test_metrics.py` | Lexical proxies require human calibration before consequential use |
| Safe missing-generation behavior | `src/llm.py`, `tests/test_evaluator.py` | Retrieval-only and generation-error rows remain unscored at answer level |
| Deterministic release gates | `src/report_generator.py`, `src/settings.py` | Thresholds are demonstration defaults, not institution-approved policy |
| Engineering interface | `app.py` | Streamlit evaluation surface; not an end-user chat application |
| Reproducible artifacts | `src/evaluator.py`, `results/` | Committed hosted run is partial and clearly identified as such |
| Automated verification | `tests/`, `.github/workflows/ci.yml` | Production-scale and external-provider reliability are not established |

## Experimental code

The FastAPI/React/SQLAlchemy files are retained as an experimental local governance prototype. They are not part of the supported requirements baseline and must not be used to claim a production enterprise, cloud, or multi-agent deployment.
