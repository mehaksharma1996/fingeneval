# ADR 0003: Controlled acyclic agent graph

**Status:** Accepted

The workflow uses explicit typed nodes with fixed retries/timeouts and no recursive delegation. LangGraph can later wrap these contracts for durable checkpoints, but it is not required for the local vertical slice. Deterministic functions handle scoring, authorization, state transitions, and gating because an agent adds risk without value there.

