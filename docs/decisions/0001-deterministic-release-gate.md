# ADR 0001: Deterministic release gate

**Status:** Prototype-only; retained as historical design context

Deterministic helper steps may summarize risk and recommend action, but a pure versioned policy function computes the prototype release outcome from persisted facts. This makes rule triggers reproducible and prevents prompt/model drift from changing release authority. The supported offline harness uses its separate deterministic report gates.
