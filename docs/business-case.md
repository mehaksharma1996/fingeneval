# Business case

## Target users and buyer map

Primary users are AI engineering, model-risk management, compliance validation, product owners, information security, and platform operations. Likely economic buyers are the head of AI platform, model-risk executive, or compliance transformation leader. Legal, privacy, internal audit, and business control owners are stakeholders whose approval needs vary by use case.

## Current pain

Financial AI releases often combine disconnected spreadsheets, model dashboards, ad hoc prompt tests, screenshots, and ticket comments. Aggregate quality can hide a severe individual regression. Provider failures can shrink a sample without making the decision visibly invalid. Evidence, ownership, human exceptions, and reruns become hard to reconstruct during audit or incident review.

## Value hypothesis

FinGenEval creates one reproducible release record: immutable configurations, approved tests, case-level evidence, comparison results, structured findings, rule-by-rule decisions, human actions, remediation, and targeted reruns. The value is faster, more defensible release review and earlier detection of high-impact defects. No customer adoption, cost saving, or regulatory outcome is claimed.

## Success metrics

- Median time from candidate registration to complete release decision
- Share of mandatory cases with traceable evidence
- Critical regressions blocked before release
- Provider-error runs correctly classified as insufficient evidence
- Median finding investigation and remediation time
- Approval turnaround time and override rate
- Reopened findings after rerun
- Run throughput, queue age, retry rate, provider errors, tokens, and estimated cost

All demo measurements are synthetic or simulated.

## Adoption risks

- Teams may resist authoring high-quality expected behavior and evidence labels.
- Reviewers may over-trust automation without calibration and training.
- Weak identity, document entitlement, or provider controls can invalidate tenant boundaries.
- Policy owners may create inconsistent gates across business units.
- Evaluation cost and latency can grow without sampling, caching, and budgets.
- Lexical proxies can miss semantic contradictions and must not be treated as sufficient validation.

## Build versus buy

Buy general experiment tracking, observability, identity, secrets, databases, queues, and object storage where mature managed services exist. Build the institution-specific release ontology, risk-weighted packs, deterministic policy rules, evidence display, approval workflow, and integration adapters. A commercial evaluation platform may replace parts of the stack if it supports immutable comparison runs, tenant entitlements, explainable gates, custom financial-risk cases, and exportable audit history.

