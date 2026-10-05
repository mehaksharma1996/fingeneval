# FinGenEval Validation Report

## Executive Summary

Run status: `RETRIEVAL_ONLY_COMPLETE`. Best retrieval method by MRR: `vector`. Answer-level metrics were not produced in this run.

## Run Metadata

- Run status: RETRIEVAL_ONLY_COMPLETE
- Structural completeness: True; rows: 180/180; deployment evidence: False
- Replayed successful LLM rows: 0
- Run timestamp (UTC): 2026-09-28T05:14:35Z
- Dataset: data/eval/test_questions.csv (sha256 3a8606869041)
- Questions: 45 (36 answerable, 9 unanswerable)
- Retrieval methods: bm25, hybrid, hybrid_reranker, vector; top_k = 3
- Generation modes: {'retrieval_only': 180}
- Generation model: none (retrieval-only)
- Embedding model: sentence-transformers/all-MiniLM-L6-v2; reranker: cross-encoder/ms-marco-MiniLM-L-6-v2

## Retrieval Benchmark

Measured on answerable questions against labeled relevant sections. Latency excludes model loading (models are warmed up before timing).

| Method | Hit@k | MRR | Contextual precision | Contextual recall | Section recall | Retrieval p50 | Retrieval p95 |
|---|---|---|---|---|---|---|---|
| vector | 94.4% | 0.875 | 86.3% | 91.2% | 87.0% | 15.6 ms | 18.2 ms |
| hybrid_reranker | 94.4% | 0.870 | 86.3% | 91.2% | 88.0% | 168.6 ms | 234.3 ms |
| hybrid | 91.7% | 0.815 | 81.5% | 87.5% | 83.3% | 14.8 ms | 18.2 ms |
| bm25 | 75.0% | 0.662 | 64.4% | 71.3% | 63.0% | 0.5 ms | 0.8 ms |

### MRR By Question Type

| Question type | questions | bm25 | hybrid | hybrid_reranker | vector |
|---|---|---|---|---|---|
| conceptual | 5 | 0.800 | 0.900 | 0.767 | 0.800 |
| exact_acronym | 1 | 1.000 | 1.000 | 1.000 | 1.000 |
| exact_policy_term | 3 | 0.667 | 1.000 | 1.000 | 1.000 |
| exact_threshold | 8 | 1.000 | 1.000 | 1.000 | 1.000 |
| multi_concept | 8 | 0.750 | 0.875 | 1.000 | 1.000 |
| semantic_paraphrase | 11 | 0.258 | 0.530 | 0.682 | 0.682 |

## Answer Quality

Not measured: this run used retrieval-only mode (no GEMINI_API_KEY), so no answers were generated.

## Metric Definitions

- Hit@k / MRR / contextual precision: computed from labeled relevant sections; precision is rank-weighted (mean precision@k at each relevant rank).
- Contextual recall: share of labeled evidence facts present in the retrieved context. Section recall: share of labeled relevant sections retrieved.
- Faithfulness proxy: share of answer sentences whose content terms (>= 60%) and all numbers appear in the retrieved context.
- Citation coverage: share of answer sentences with a citation. Citation validity: share of cited sentences citing only retrieved evidence.
- Hallucination risk: answerable questions, share of sentences that are unsupported or cite non-retrieved evidence; unanswerable questions, 1 unless the system abstains.
- Answer correctness proxy: share of reference-answer terms present in the answer.

## Risks And Limitations

The validation corpus is synthetic and small, and answer metrics are lexical proxies that do not detect negation errors or subtle paraphrase drift. Retrieval quality has not been tested against production document scale, access controls, or adversarial prompts. Human review remains required before any customer-impacting deployment.

## Deployment Recommendation

Insufficient evidence. No LLM answers were generated in this run (retrieval-only mode), so faithfulness, citation, hallucination, and abstention were not measured. Retrieval results alone cannot support a deployment decision.
