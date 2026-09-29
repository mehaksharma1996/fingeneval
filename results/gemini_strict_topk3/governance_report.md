# FinGenEval Validation Report

## Executive Summary

Best retrieval method by MRR: `vector`. Best end-to-end configuration: `hybrid_reranker / strict_governance` (hallucination risk 0.0%, faithfulness 100.0%, correct abstention n/a).

## Run Metadata

- Run timestamp (UTC): 2026-09-28T05:35:23Z
- Dataset: data/eval/test_questions.csv (sha256 3a8606869041)
- Questions: 45 (36 answerable, 9 unanswerable)
- Retrieval methods: bm25, hybrid, hybrid_reranker, vector; top_k = 3
- Generation modes: {'generation_error': 161, 'llm': 19}
- Generation model: gemini-2.5-flash
- Embedding model: sentence-transformers/all-MiniLM-L6-v2; reranker: cross-encoder/ms-marco-MiniLM-L-6-v2

## Retrieval Benchmark

Measured on answerable questions against labeled relevant sections. Latency excludes model loading (models are warmed up before timing).

| Method | Hit@k | MRR | Contextual precision | Contextual recall | Section recall | Retrieval p50 | Retrieval p95 |
|---|---|---|---|---|---|---|---|
| vector | 94.4% | 0.875 | 86.3% | 91.2% | 87.0% | 12.6 ms | 24.1 ms |
| hybrid_reranker | 94.4% | 0.870 | 86.3% | 91.2% | 88.0% | 149.2 ms | 219.3 ms |
| hybrid | 91.7% | 0.815 | 81.5% | 87.5% | 83.3% | 11.5 ms | 19.5 ms |
| bm25 | 75.0% | 0.662 | 64.4% | 71.3% | 63.0% | 0.4 ms | 0.6 ms |

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

Measured only on rows where the LLM produced an answer (see Answered). Generation latency excludes rate-limit and retry waits.

| Configuration | Answered | Faithfulness | Citation coverage | Citation validity | Hallucination risk | Correct abstention | False refusal | Answer correctness | Gen p50 | Gen p95 | Errors |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hybrid_reranker / strict_governance | 4/45 | 100.0% | 100.0% | 100.0% | 0.0% | n/a | 0.0% | 76.9% | 1047.3 ms | 1503.8 ms | 91.1% |
| vector / strict_governance | 7/45 | 100.0% | 100.0% | 100.0% | 0.0% | n/a | 0.0% | 84.7% | 1241.0 ms | 2346.1 ms | 84.4% |
| hybrid / strict_governance | 4/45 | 100.0% | 100.0% | 100.0% | 0.0% | n/a | 0.0% | 84.2% | 1032.7 ms | 1301.0 ms | 91.1% |
| bm25 / strict_governance | 4/45 | 100.0% | 100.0% | 100.0% | 0.0% | n/a | 0.0% | 79.8% | 1204.8 ms | 1651.6 ms | 91.1% |

### Deployment Gates For `hybrid_reranker / strict_governance`

| Gate | Threshold | Result |
|---|---|---|
| Contextual recall | >= 80.0% | PASS |
| Faithfulness proxy | >= 85.0% | PASS |
| Hallucination risk (answerable) | <= 10.0% | PASS |
| Citation coverage | >= 90.0% | PASS |
| Correct abstention (unanswerable) | >= 90.0% | FAIL |
| False refusal (answerable) | <= 10.0% | PASS |
| Generation error rate | <= 5.0% | FAIL |

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

Insufficient evidence. Generation failed on 91.1% of rows; rerun before deciding.