# Committed benchmark evidence

These folders contain outputs from actual benchmark executions. Validate them before using any metric:

```powershell
python -m src.run_integrity results/retrieval_only_topk3 results/gemini_strict_topk3
```

The committed dataset fingerprint is `3a8606869041` for `data/eval/test_questions.csv` (45 questions: 36 answerable and 9 unanswerable). Both runs use `top_k=3`, prompt style `strict_governance`, hybrid weights `0.5/0.5`, embedding model `sentence-transformers/all-MiniLM-L6-v2`, and reranker `cross-encoder/ms-marco-MiniLM-L-6-v2` across `vector,bm25,hybrid,hybrid_reranker`.

## Retrieval-only run

Status: `RETRIEVAL_ONLY_COMPLETE` — 180/180 expected rows, all credential-free retrieval-only rows. Answer-level metrics are intentionally empty and this evidence cannot support a deployment recommendation.

Reproduction command:

```powershell
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
python -m src.evaluator --methods vector,bm25,hybrid,hybrid_reranker --prompt-styles strict_governance --top-k 3 --output-dir results/retrieval_only_topk3_reproduced
```

## Hosted Gemini run

Status: `PARTIAL_GENERATION` — 180/180 structurally present rows, but only 19 successful `llm` rows and 161 `generation_error` rows. The recorded model is `gemini-2.5-flash`. Its answer-level metrics are diagnostic only and must not be cited as a complete benchmark or deployment recommendation.

Reproduction/resume command (optional; requires the user's own Gemini access):

```powershell
$env:GEMINI_API_KEY="your-key"
$env:FINGENEVAL_GEMINI_MODEL="gemini-2.5-flash"
python -m src.evaluator --methods vector,bm25,hybrid,hybrid_reranker --prompt-styles strict_governance --top-k 3 --resume-from results/gemini_strict_topk3/evaluation_results.csv --output-dir results/gemini_strict_topk3_resumed
```

The harness defaults used by this reproduction path are a 4-second minimum interval, 3 transient retries, and no FinGenEval-imposed token cap; provider-side quotas remain external and may change. Rate-limit waits are excluded from generation latency.

## Environment provenance

The original 2026-09-28 runs recorded the dataset, configuration, model identifiers, weights, timestamp, and generation-mode counts, but did **not** record the OS, Python patch version, package versions, provider quota, or exact invocation. Those facts are unknown and are not reconstructed here. For a controlled reproduction, use Python 3.12 with the repository's current requirements and record a fresh output directory; CI tests that contract on Ubuntu and validates committed artifact structure separately.

This provenance gap is a limitation of the legacy artifacts, not evidence to fill in by assumption. New saves include derived status, row counts, structural completeness, deployment-evidence eligibility, resume source, and replayed-row count.
