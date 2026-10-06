---
name: pipeline-troubleshooting
description: Activates when diagnosing pipeline failures, rejected rows, stale analytics layer, or data trustworthiness issues.
triggers:
  - "pipeline failed"
  - "troubleshoot pipeline"
  - "rejected rows"
  - "can I trust this data"
---

# Pipeline Troubleshooting Skill

## Diagnostic Workflow
1. **Status Evaluation:**
   - Inspect `healthy` boolean and `reasons` from `/pipeline/status`.
   - Inspect `rows_in` vs `rows_published` vs `rows_rejected`.
   - Check `freshness_indicator` and compare `as_of` against expected reporting window.

2. **Taint Classification:**
   - **Critical Fault (Data Corrupt):** Negative activity values, schema drift, grain duplicate violations. Action: Mark all downstream analytics as untrustworthy.
   - **Non-Critical Drift (Stale / Delayed):** Pipeline delayed but prior data intact. Action: Analytics usable with explicit staleness caveating.

3. **Output Format:**
   - **RUN_METADATA:** run_id, run_timestamp, as_of
   - **FAILURE_ROOT_CAUSE:** Exact task and validation condition breached
   - **DOWNSTREAM_IMPACT:** Specific tables or features compromised
   - **REMEDIATION_STEPS:** Concrete commands to quarantine bad batch or rerun failed task