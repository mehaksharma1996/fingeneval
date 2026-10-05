# Prioritized next steps for the supported harness

1. **Metric calibration:** complete independent human review of the versioned v1 packet, then publish its withheld agreement and disagreement analysis.
2. **Provider-independent replay:** define a recorded-response format so answer evaluation can be reproduced offline without repeating paid calls.
3. **Corpus-scale evaluation:** test larger synthetic corpora and publish measured retrieval latency, memory use, and quality changes.
4. **Adversarial coverage:** extend labeled financial cases for stale sources, conflicting policies, prompt injection, citation laundering, and near-miss abstention.
5. **Paired system comparison:** add paired baseline-versus-candidate tests when two complete answer runs and an adequate sample are available.
6. **Run provenance:** record code revision and dependency/model versions with each run while avoiding environment secrets.
7. **Packaging:** expose stable evaluator, metric, and report contracts for CI use without adding agents, tool execution, or chat behavior.

The experimental local governance prototype is frozen pending a separate scope decision. Cloud deployment, identity platforms, durable workers, generic business authoring, and operational dashboards are not current product goals.
