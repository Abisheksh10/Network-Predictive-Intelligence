# Engineering Controls: Hooks vs. CI Matrix

| Control Category | Placement | Rationale |
| :--- | :--- | :--- |
| **Grain Duplicate Check on (grid_id, timestamp)** | **Hook (Post-Edit)** | Grain duplication corrupts star schema analytics silently. Running this locally takes < 2 seconds and stops faulty aggregation code before it is committed. |
| **ML Feature Leakage Check** | **Hook (Post-Edit)** | Feature leakage produces deceptively high offline metrics. Catching it at edit-time prevents invalid model artifacts from being serialized. |
| **Pre-Action Airflow Confirmation** | **Hook (Pre-Edit / Ask)** | Prevents accidental modification of orchestration intervals and DAG schedules on production batches. |
| **Full End-to-End Regression Suite** | **CI Pipeline** | Running the complete multi-phase test suite takes several minutes and consumes external services, which introduces too much friction during iterative local editing. |
| **Docker Build & GeoJSON Topo Validation** | **CI Pipeline** | Resource-intensive container builds and multi-gigabyte spatial polygon topology checks belong in decoupled CI runners. |