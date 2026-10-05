# Experimental governance-prototype responsible AI assessment

> **Status:** Historical assessment for the frozen synthetic prototype. The canonical FinGenEval product is the offline evaluation harness and does not execute autonomous agents or tools.

## Intended use

FinGenEval supports pre-release evaluation and governance of financial AI systems. It helps trained employees compare versions, inspect evidence, identify regressions, document human decisions, and plan remediation.

## Prohibited use

The platform must not provide financial, legal, regulatory, or compliance advice; make customer eligibility or enforcement decisions; replace qualified review; certify legal compliance; or allow generated output to override deterministic gates. Synthetic demonstration policies must never be represented as real requirements.

## Human oversight

Approved prototype users own datasets, release policies, severity, and final actions. AI-generated test proposals remain drafts. Deterministic helper steps may summarize evidence, while deterministic rules compute the gate. An override requires an authorized reviewer, a substantive justification, timestamp, and audit event. Reviewers see baseline/candidate responses, expected behavior, evidence, metrics, likely failure stage, and limitations.

## Risk classification

Projects record a risk tier. Cases carry severity, risk weight, release-blocking status, answerability, freshness, and review role. Critical unresolved regressions and mandatory-test failures block release. Incomplete runs are insufficient evidence. These are organization policy controls rather than legal classifications.

## Data considerations

The repository uses synthetic policies and users. Production deployment must classify prompts/documents/results, minimize content sent to providers, enforce tenant/document entitlements, redact sensitive fields from logs, set retention by data class, and support verified deletion and legal hold. Training on customer data requires a separate approved basis and governance process.

## Evaluation limitations

The deterministic local provider proves workflow mechanics only. The original lexical metrics can catch unsupported terms, numbers, citations, and missed abstention but cannot reliably understand negation, nuanced obligations, or semantic equivalence. Real programs need calibrated judge models, human-labeled samples, confidence intervals, adversarial red teaming, production-like documents, and post-release monitoring.

## Provider risks

Provider behavior, model versions, regions, retention, safety controls, outages, and prices can change. Pin versions where supported, record provider request IDs, limit sensitive inputs, validate outputs, use contractual/privacy review, implement circuit breakers and budgets, and preserve a credential-free local path.
