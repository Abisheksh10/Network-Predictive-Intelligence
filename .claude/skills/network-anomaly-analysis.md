---
name: network-anomaly-analysis
description: Activates when evaluating why a grid is flagged, explaining an anomaly score, or diagnosing whether an activity pattern is unusual.
triggers:
  - "why is grid flagged"
  - "what does this anomaly score mean"
  - "is this pattern unusual"
  - "explain anomaly"
---

# Network Anomaly Analysis Skill

## 1. Required Evidence Check
Before evaluating or generating any severity assessment, verify that the caller provided the complete evidence package:
- Current interval activity metrics
- Baseline average activity
- Anomaly score and direction
- Rule alerts (or confirmation of 0 alerts)
- Pipeline health status (`GET /pipeline/status`)

**MANDATORY INSUFFICIENCY RULE:**
If ANY required piece of evidence is missing (e.g. user provides a bare grid ID like "Check grid 4821" without metrics, or pipeline status is omitted), **REFUSE** to output a normal severity (`NORMAL`, `ATTENTION`, `HIGH`). You must immediately set:
`SEVERITY: INSUFFICIENT EVIDENCE`
and explicitly name what evidence is missing. Never fill gaps with guesses or estimates.

## 2. Response Structure
Output MUST strictly use these four uppercase headers:

SEVERITY
[Must be strictly: NORMAL, ATTENTION, HIGH, or INSUFFICIENT EVIDENCE]

EVIDENCE
[Tabulate or list exact observed metrics with tool/endpoint citations.]

INTERPRETATION
[State what the evidence might mean. Clearly label all interpretations as inferences or operational hypotheses.]

NEXT CHECKS
[Provide 2-3 actionable diagnostic steps for an on-duty NOC engineer.]

## 3. Strict Terminology Rules
- Metrics are **proportional interaction units**, NEVER call counts, message quantities, or Megabytes (MB/GB).
- NEVER claim or assert "congestion". High activity indicates volume, not line saturation.
- A "grid" is a **geographic cell**, NEVER a cellular tower or antenna site.