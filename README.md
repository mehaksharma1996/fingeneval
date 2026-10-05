# FinGenEval

**Offline evaluation and release gating for financial RAG configurations**

FinGenEval is a reproducible evaluation harness for financial-policy question answering. It compares retrieval and prompting configurations against labeled questions and produces deterministic validation reports covering retrieval quality, grounding, citation behavior, hallucination risk, abstention, latency, and deployment gates.

The supported product is the offline harness. It is not a conversational assistant, a multi-agent system, a tool-calling runtime, or a business-intelligence platform.

All bundled documents, questions, identities, and outcomes are synthetic. FinGenEval and its reports are not legal, regulatory, compliance, or financial advice.

## Supported architecture

```text
Evaluator
   |-- Streamlit engineering UI
   `-- CLI benchmark runner
             |
       labeled questions
             |
    document loading + section chunking
             |
 BM25 / vector / hybrid / reranked retrieval
             |
 optional Gemini generation or retrieval-only mode
             |
 deterministic metrics and deployment gates
             |
 CSV results + metadata + Markdown validation report
```

Both supported entry points call the same evaluation engine:

- `app.py` provides query inspection, retrieval comparison, benchmark execution, and report download.
- `python -m src.evaluator` runs the reproducible benchmark from the command line.

The architecture is described in [docs/architecture.md](docs/architecture.md) and the execution path in [docs/end-to-end-workflow.md](docs/end-to-end-workflow.md).

## Evaluation scope

- 45 labeled questions: 36 answerable and 9 unanswerable, including near misses
- 7 synthetic financial-policy documents
- 40 section-aware indexed chunks with the default settings
- 4 retrieval configurations: BM25, vector, hybrid, and hybrid plus reranker
- 2 prompt styles: basic and strict governance
- Retrieval metrics: hit@k, MRR, rank-weighted contextual precision, contextual recall, and section recall
- Answer metrics: faithfulness proxy, citation coverage and validity, hallucination risk, abstention accuracy, and answer correctness proxy
- Separate retrieval and generation latency measurements after warm-up

## Run locally

Prerequisites: Python 3.11 or later.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
streamlit run app.py
```

Run a credential-free BM25 benchmark:

```powershell
python -m src.evaluator --methods bm25 --top-k 3 --output-dir results/local_bm25
```

Run all retrieval configurations:

```powershell
python -m src.evaluator --methods vector,bm25,hybrid,hybrid_reranker --top-k 3 --output-dir results/local_all
```

Vector and reranker paths may download configured SentenceTransformer models on first use.

## Generation modes

When `GEMINI_API_KEY` is absent, FinGenEval operates in retrieval-only mode. Retrieval metrics are computed, while answer-level metrics remain empty by design.

When a Gemini key is configured, the harness records successful LLM responses, generation failures, generation latency, and the exact model name. Rate-limit waits are excluded from measured generation latency. Successful rows can be resumed after a partial run.

```powershell
$env:GEMINI_API_KEY="your-key"
python -m src.evaluator --methods bm25 --top-k 3 --output-dir results/gemini_bm25
```

Reports never treat retrieval-only or failed-generation rows as measured answer quality.

Validate a saved run before citing or comparing it:

```powershell
python -m src.run_integrity results/retrieval_only_topk3
```

The validator rejects incomplete matrices, duplicate benchmark keys, undeclared generation modes, dataset-fingerprint drift, metadata/count mismatches, and answer metrics populated on non-LLM rows. Its status distinguishes complete retrieval-only, complete generation, partial generation, failed generation, mixed-mode, invalid, and replayed evidence.

## Saved results

Committed result folders are evidence from actual runs, not illustrative numbers:

- `results/retrieval_only_topk3/` contains 180 retrieval-only rows across four retrieval methods.
- `results/gemini_strict_topk3/` is a partial hosted-generation run with 19 successful LLM rows and 161 recorded generation errors. It must not be presented as a complete answer-quality benchmark.

Each result folder contains the row-level CSV, run metadata, and a deterministic governance report.
Exact reproduction commands and known provenance limitations are documented in [results/README.md](results/README.md). CI validates both committed runs against the current labeled dataset.

## Repository map

- `app.py`: supported Streamlit engineering interface
- `src/document_loader.py`: deterministic Markdown document loading
- `src/chunking.py`: section-aware chunking
- `src/retrievers.py`: BM25, vector, hybrid, and reranked retrieval
- `src/llm.py`: optional Gemini generation, prompts, retries, and rate limiting
- `src/metrics.py`: pure retrieval and answer metrics
- `src/evaluator.py`: benchmark orchestration, timing, resume support, and saved runs
- `src/report_generator.py`: deterministic summaries and deployment gates
- `src/run_integrity.py`: saved-run validation and evidence classification
- `src/settings.py`: paths, models, weights, and thresholds
- `data/docs/`: synthetic financial-policy corpus
- `data/eval/test_questions.csv`: labeled evaluation dataset
- `results/`: saved benchmark evidence
- `tests/`: dataset, metric, evaluator, and regression tests

### Experimental local governance prototype

`src/enterprise/`, `frontend/`, `migrations/`, and the related enterprise documentation are retained as an experimental local prototype that consumes the same synthetic policy assets. They are not the canonical FinGenEval product path and are not evidence of a production deployment, multi-agent system, or validated enterprise scale. New work should not expand that prototype unless the repository scope is explicitly changed first.

## Verification

```powershell
python -m pytest -q
python -m ruff check src tests
python -m mypy src/enterprise
```

Dataset tests verify that labeled sources and sections exist in the index, evidence facts occur in the labeled sections, unanswerable questions have no positive labels, and questions do not copy long evidence phrases.

## Non-goals

- Serving end-user financial questions
- Chat memory or conversational state
- Autonomous agents or recursive delegation
- Tool execution or business-process automation
- Business-data dashboards
- Claims of legal, regulatory, or production readiness

Prioritized supported-harness work is tracked in [docs/next-steps.md](docs/next-steps.md).
