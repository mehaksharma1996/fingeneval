# Model Risk Management Policy

## Model Inventory And Tiering

All models used for credit, market, operational, AML, capital, or AI-assisted decisions must be registered in the enterprise model inventory. Models are tiered by business impact, complexity, data sensitivity, and regulatory exposure.

## Validation Evidence

Model validation evidence must include conceptual soundness, data quality assessment, performance testing, sensitivity analysis, limitations, and implementation verification. Validators must challenge assumptions and document unresolved findings before production approval.

## Monitoring Requirements

Model owners must monitor performance, data drift, stability, overrides, and user feedback. Drift thresholds should be defined before deployment and calibrated to model materiality. Breaches must trigger root-cause analysis and remediation planning.

## Review Cadence

The model review cadence is `annual minimum`, `quarterly for high-risk models`. High-risk models include models with material customer, capital, compliance, or regulatory impact. Missed reviews must be escalated to the model risk committee.

## Challenger Model Review

Material models should have challenger analysis when feasible. Challenger reviews compare baseline performance, stability, and business impact against alternative approaches before major redevelopment or retirement decisions.

## Deployment Approval Checklist

Production deployment requires validation signoff, monitoring plan approval, owner attestation, limitation disclosure, change-management evidence, and issue tracking. No high-risk model may deploy with open critical validation findings unless an executive exception is approved.
