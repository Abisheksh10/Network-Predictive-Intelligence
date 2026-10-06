"""
project_context.py - Canonical domain memory for Telecom NOC platform.
Injected as the base system context into all Claude API calls.
"""

PROJECT_MEMORY = """
=== TELECOM NOC SYSTEM CONTEXT & DOMAIN INVARIANTS ===

1. SPATIAL & TEMPORAL GRAIN:
   - Primary data grain: (time_key, grid_id).
   - Each entry in fact_network_activity represents an hourly aggregation for a 235m x 235m grid square in Milan.
   - Milan spatial grid comprises grid_ids 1 to 10000.
   - Spatial join key between dimension tables and external geo-coordinates is strictly `cellId` (never mix up grid_id with cellId).

2. TELEMETRY & TERMINOLOGY CONSTRAINTS:
   - Values in `sms_in`, `sms_out`, `call_in`, `call_out`, and `internet` are proportional interaction units, NOT counts and NOT megabytes/data volumes.
   - STRICT TERMINOLOGY PROHIBITION: Never assert, diagnose, or state "network congestion". The system operates on activity anomalies, elevated demand, or statistical outliers, but cannot infer physical queue depth or hardware packet dropping.

3. DATA WAREHOUSE SCHEMA:
   - Database: MySQL `telecom_warehouse`.
   - Core tables:
     * `fact_network_activity` (time_key, grid_id, sms_in, sms_out, call_in, call_out, internet_activity, total_activity)
     * `dim_time` (time_key, timestamp, year, month, day, hour, day_of_week)
     * `dim_grid` (grid_id, centroid_lat, centroid_lon, district_name)

4. MACHINE LEARNING & PREDICTION RULES:
   - Model artifact: Logistic Regression (`artifacts/baseline_risk_model.joblib`).
   - Feature Schema: Governed strictly by `models/feature_columns.json`:
     ["avg_activity", "activity_growth", "active_hours", "peak_ratio", "variability", "internet_share"].
   - Cutoff temporal windows: Recent activity spans 23 hours; baseline comparison spans prior 24-48 hours.
   - Predictions target future 1-hour risk surge (threshold: >= 1.35 * baseline mean and >= 50.0 total activity).
   - Training-serving consistency is mandatory; never hardcode feature defaults at inference.

5. API SURFACE & CONTRACTS:
   - Endpoints in phase4 FastAPI service:
     * GET /network/summary
     * GET /network/grid/{grid_id}
     * GET /network/grid/{grid_id}/features
     * GET /network/grid/{grid_id}/location
     * GET /network/hotspots
     * POST /network/anamoly_score
     * GET /pipeline/status
"""

def get_project_context() -> str:
    return PROJECT_MEMORY.strip()