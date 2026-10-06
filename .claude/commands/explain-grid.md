---
description: Comprehensive NOC 4-section drilldown for a specified grid
argument: grid_id
---
Gather telemetry for Grid $ARGUMENTS using these endpoints:
- GET http://127.0.0.1:8000/network/grid/$ARGUMENTS/location
- GET http://127.0.0.1:8000/network/grid/$ARGUMENTS
- GET http://127.0.0.1:8000/network/grid/$ARGUMENTS/features
- POST http://127.0.0.1:8000/network/anamoly_score?grid_id=$ARGUMENTS&timestamp=2013-11-07T23:00:00

Output MUST follow this format:
SEVERITY: [NORMAL / ATTENTION / HIGH / INSUFFICIENT EVIDENCE]
EVIDENCE: [Values for location, activity, baseline, growth, peak ratio, anomaly score with source endpoints]
INTERPRETATION: [Operational hypothesis - do not assert congestion, measures are interaction units]
NEXT CHECKS: [2 concrete diagnostic steps]