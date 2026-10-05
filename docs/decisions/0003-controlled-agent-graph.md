# ADR 0003: Controlled deterministic workflow

**Status:** Superseded for the supported product; retained for the frozen prototype

The experimental workflow uses explicit typed helper steps with fixed retries and timeouts. It has no recursive delegation, autonomous planning, or tool execution. Deterministic functions handle scoring, authorization, state transitions, and gating. The supported FinGenEval harness does not include this workflow and is not a multi-agent system.
