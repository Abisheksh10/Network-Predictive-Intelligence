---
description: Compare rule alert, classifier output, and anomaly score for a grid
argument: grid_id
---
Inspect Grid $ARGUMENTS:
1. Check rule alerts at GET http://127.0.0.1:8000/network/alerts.
2. Check risk classification at POST http://127.0.0.1:8000/model/predict_risk with {"grid_id": $ARGUMENTS}.
3. Check anomaly score at POST http://127.0.0.1:8000/network/anamoly_score?grid_id=$ARGUMENTS&timestamp=2013-11-07T23:00:00.

Compare the three outputs. Explain any disagreement between statistical anomaly score and rule-based thresholds.