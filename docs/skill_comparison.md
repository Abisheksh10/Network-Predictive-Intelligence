# C8: Skills Evaluation & Before-and-After Comparison

## Skill: network-anomaly-analysis

### Test Query
`"Why is Grid 4821 flagged with an anomaly score of -0.7138?"`

---

### Run 1: WITHOUT Skill (Standard Unassisted Prompt)
**Observed Behavior:**
- Produces an unstructured conversational essay.
- Conversational drift: refers to activity as "high data traffic / MB download rates" or mentions "tower congestion".
- Accepts incomplete inputs without checking for pipeline health or baseline definitions.
- Blends facts with speculative opinions into one narrative paragraph.

---

### Run 2: WITH Skill (`network-anomaly-analysis` Active)
**Observed Behavior:**
- Strictly formats into the 4 mandatory sections: `SEVERITY`, `EVIDENCE`, `INTERPRETATION`, `NEXT CHECKS`.
- Refuses to assert "congestion"; describes values strictly as proportional interaction units.
- Treats the grid as a geographic cell.
- If pipeline status or baseline figures are absent, automatically switches `SEVERITY` to `INSUFFICIENT EVIDENCE`.

---

### Incomplete Evidence Test (Acceptance Criterion 3)
**Prompt:** `"Assess severity for Grid 4821."` (Bare grid ID provided with no metrics)
- **Result:**
  ```text
  SEVERITY: INSUFFICIENT EVIDENCE
  
  EVIDENCE: None provided (Missing: current activity, baseline activity, anomaly score, rule alerts, pipeline status).
  
  INTERPRETATION: Cannot evaluate grid state without factual telemetry. Filling gaps with estimates is strictly prohibited by domain rules.
  
  NEXT CHECKS:
  1. Call get_grid_activity(grid_id=4821) and get_grid_features(grid_id=4821).
  2. Query get_pipeline_status() to verify data trustworthiness.