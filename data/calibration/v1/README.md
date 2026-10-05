# Calibration v1 status

Status: **PENDING_HUMAN_REVIEW**

This directory contains twelve controlled calibration cases and a versioned metric configuration. The candidate cases include known lexical stressors, but their `human_*` columns are intentionally blank. They were prepared with AI assistance and must not be described as human-reviewed evidence.

Run `python -m src.calibration` to see the fail-closed report. Before review it exits with code 2 and publishes no precision, recall, confidence interval, or threshold recommendation. CI uses `--validate-only` solely to verify packet structure and provenance; that flag does not change the reported status.

Follow [the calibration protocol](../../../docs/calibration-protocol.md) to review, adjudicate, and seal the CSV fingerprint.
