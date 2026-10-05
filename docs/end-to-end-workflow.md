# End-to-end evaluation workflow

FinGenEval has two supported entry points over the same offline evaluation engine: the Streamlit engineering UI and the evaluator CLI.

## Benchmark lifecycle

1. Load and validate `data/eval/test_questions.csv`.
2. Load the Markdown policies in `data/docs/` in deterministic filename order.
3. Split documents into section-aware chunks that retain source and heading provenance.
4. Build BM25 immediately and initialize vector/reranker models only when requested.
5. Warm every selected retrieval method so model startup is excluded from latency.
6. For every question, retrieval method, and prompt style:
   - retrieve top-k evidence;
   - record retrieval latency and ranked evidence identifiers;
   - return retrieval-only output when Gemini is not configured, or attempt generation when it is;
   - calculate retrieval metrics and, only for successful generation, answer metrics.
7. Aggregate configurations and apply deterministic deployment gates.
8. Save the row-level CSV, run metadata, and Markdown report when an output directory is supplied.

## Streamlit path

```powershell
streamlit run app.py
```

The UI offers:

- Query Inspector for evidence and claim checks
- Retrieval Comparison across all four methods
- Benchmark execution over the labeled dataset
- Validation Report rendering and downloads

The UI is an engineering surface, not a conversational assistant or business dashboard.

## CLI path

```powershell
python -m src.evaluator --methods bm25 --top-k 3 --output-dir results/local_bm25
```

Multiple methods can be supplied as a comma-separated list. `--resume-from` reuses only successful LLM rows from a compatible prior CSV; failed rows are executed again.

## Generation behavior

- Without `GEMINI_API_KEY`, rows use `retrieval_only` mode and answer-level metrics remain empty.
- Successful hosted generation uses `llm` mode.
- Provider failures use `generation_error` mode and answer-level metrics remain empty.
- Daily quota exhaustion stops additional hosted calls rather than repeatedly failing.

## Output contract

Each saved run contains:

- `evaluation_results.csv`: one row per question, retrieval method, and prompt style
- `run_metadata.json`: dataset fingerprint, configuration, models, row modes, and counts
- `governance_report.md`: deterministic summaries, gates, risks, and recommendation

The experimental FastAPI/React governance prototype is outside this supported workflow.
