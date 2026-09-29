# Repository Guidance

## Project Purpose

FinGenEval is an offline evaluation harness for financial RAG configurations. It
benchmarks retrieval and generation on labeled financial policy questions and
produces gated, deterministic validation reports covering retrieval quality,
grounding, citation behavior, hallucination risk, abstention, and latency.

Keep the scope narrow. This is not a conversational assistant, not a multi-agent
system, and not a BI or analytics platform. Do not add chat memory, agents, tool
calling, or business-data dashboards.

## Architecture

- `app.py` is the Streamlit front end (query inspector, retrieval comparison, benchmark, report).
- `src/document_loader.py` loads the source policy documents.
- `src/chunking.py` divides source documents into section chunks.
- `src/retrievers.py` implements BM25, FAISS vector, hybrid, and reranked retrieval.
- `src/llm.py` handles Gemini generation (`google-genai`), prompts, and rate limiting.
- `src/metrics.py` contains every metric as a pure, unit-tested function.
- `src/evaluator.py` runs the benchmark, times retrieval and generation separately, and saves runs.
- `src/report_generator.py` builds the gated validation report.
- `src/settings.py` contains configuration and deployment gate thresholds.
- `data/docs/` contains the policy documents; `data/eval/test_questions.csv` the labeled questions.
- `results/` contains saved benchmark runs; `tests/` the pytest suite.

## Evaluation Scope

- 45 labeled questions (36 answerable, 9 unanswerable including 6 near-misses)
- 7 source policy documents, 40 indexed section chunks
- 4 retrieval configurations, 2 prompt styles
- Retrieval metrics: hit@k, MRR, contextual precision (rank-weighted), contextual recall, section recall
- Answer metrics: faithfulness proxy, citation coverage, citation validity, hallucination risk, abstention accuracy, answer correctness proxy
- Latency: retrieval and generation p50/p95, measured after warm-up and excluding rate-limit waits

## Rules

- Do not invent benchmark results that have not been produced by an actual run. Saved runs live in `results/`.
- Answer-level metrics must stay empty for retrieval-only or failed-generation rows.
- When editing the dataset, keep `python -m pytest -q` passing; `tests/test_dataset.py` checks labels against the index.

## Development Commands

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m src.evaluator --methods vector,bm25,hybrid,hybrid_reranker --top-k 3 --output-dir results/my_run
streamlit run app.py
```
