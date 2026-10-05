# Prioritized next steps for the supported harness

1. **Result integrity:** validate expected row counts, dataset fingerprints, duplicates, generation modes, and report eligibility for every saved run.
2. **Metric calibration:** create a human-reviewed calibration subset and measure disagreement, false positives, and false negatives for grounding and hallucination proxies.
3. **Provider-independent replay:** define a recorded-response format so answer evaluation can be reproduced offline without repeating paid calls.
4. **Corpus-scale evaluation:** test larger synthetic corpora and publish measured retrieval latency, memory use, and quality changes.
5. **Adversarial coverage:** extend labeled financial cases for stale sources, conflicting policies, prompt injection, citation laundering, and near-miss abstention.
6. **Statistical comparison:** add confidence intervals and paired baseline-versus-candidate comparisons where the sample size supports them.
7. **Run provenance:** record code revision and dependency/model versions with each run while avoiding environment secrets.
8. **Packaging:** expose stable evaluator, metric, and report contracts for CI use without adding agents, tool execution, or chat behavior.

The experimental local governance prototype is frozen pending a separate scope decision. Cloud deployment, identity platforms, durable workers, generic business authoring, and operational dashboards are not current product goals.
