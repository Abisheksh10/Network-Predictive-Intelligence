# Network Operations Custom Slash Commands

| Command | Classification | Inputs | Endpoints / Tools Used | Expected Output Shape |
| :--- | :--- | :--- | :--- | :--- |
| `/check-pipeline` | **NOC-oriented** | None | `GET /pipeline/status` | Operational health summary, AS_OF, rejected rows, freshness flag. |
| `/explain-grid` | **NOC-oriented** | `grid_id` (e.g. 4821) | Grid location, activity, features, anomaly score | 4-section brief: `SEVERITY`, `EVIDENCE`, `INTERPRETATION`, `NEXT CHECKS`. |
| `/review-anomaly` | **NOC-oriented** | `grid_id` (e.g. 4821) | Alerts, Risk classifier, Anomaly score | Tri-factor comparison explaining consensus or disagreement. |
| `/test-api` | **Engineering-oriented**| Optional filter | `pytest phase4/tests/` | Test execution status, count of passing/failing suites. |
| `/network-health` | **Engineering-oriented**| None | Direct SQL grain assertion | `PASS` or `FAIL` verifying no duplicates on `(time_key, grid_id)`. |