# ADR 0001: Deterministic release gate

**Status:** Accepted

Agents may summarize risk and recommend action, but a pure versioned policy function computes release outcome from persisted facts. This makes rule triggers reproducible and prevents prompt/model drift from changing release authority. The tradeoff is that policy authors must explicitly encode thresholds, severity, and approval needs.

