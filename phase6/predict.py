# import os
# import json
# import joblib
# import pandas as pd
# import numpy as np
# from datetime import datetime, timedelta
# from sqlalchemy import create_engine

# DB_URL = "mysql+pymysql://root:root@localhost:3306/telecom_warehouse"
# engine = create_engine(DB_URL)

# MODEL_PATH = os.path.join("..", "artifacts", "baseline_risk_model.joblib")
# if not os.path.exists(MODEL_PATH):
#     MODEL_PATH = os.path.join("artifacts", "baseline_risk_model.joblib")

# SCHEMA_PATH = os.path.join("..", "models", "feature_columns.json")
# if not os.path.exists(SCHEMA_PATH):
#     SCHEMA_PATH = os.path.join("models", "feature_columns.json")

# def load_feature_schema():
#     if not os.path.exists(SCHEMA_PATH):
#         # Fallback to model artifact internal feature list if json is pending
#         artifact = joblib.load(MODEL_PATH)
#         return artifact.get("features", ["avg_activity", "activity_growth", "active_hours", "peak_ratio", "variability", "internet_share"])
#     with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
#         return json.load(f)

# def load_model():
#     if not os.path.exists(MODEL_PATH):
#         raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}")
#     artifact = joblib.load(MODEL_PATH)
#     return artifact["model"]

# def extract_features_for_grid(grid_id: int, cutoff_timestamp: datetime):
#     recent_start = cutoff_timestamp - timedelta(hours=23)
#     baseline_start = cutoff_timestamp - timedelta(hours=47)
#     baseline_end = cutoff_timestamp - timedelta(hours=24)

#     # SQL includes recent_sum and recent_internet_sum matching train_ml3.py
#     query = """
#         SELECT 
#             f.grid_id,
#             AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_avg,
#             MAX(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_max,
#             STDDEV_POP(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_std,
#             SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE 0.0 END) AS recent_sum,
#             SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.internet_activity ELSE 0.0 END) AS recent_internet_sum,
#             COUNT(DISTINCT CASE WHEN t.timestamp BETWEEN %s AND %s AND f.total_activity > 0 THEN t.hour ELSE NULL END) AS active_hours,
#             AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS baseline_avg
#         FROM fact_network_activity f
#         JOIN dim_time t ON f.time_key = t.time_key
#         WHERE t.timestamp BETWEEN %s AND %s AND f.grid_id = %s
#         GROUP BY f.grid_id;
#     """
#     # Exactly 17 params for the 17 placeholders
#     params = (
#         recent_start, cutoff_timestamp,      # 1, 2: recent_avg
#         recent_start, cutoff_timestamp,      # 3, 4: recent_max
#         recent_start, cutoff_timestamp,      # 5, 6: recent_std
#         recent_start, cutoff_timestamp,      # 7, 8: recent_sum
#         recent_start, cutoff_timestamp,      # 9, 10: recent_internet_sum
#         recent_start, cutoff_timestamp,      # 11, 12: active_hours
#         baseline_start, baseline_end,        # 13, 14: baseline_avg
#         baseline_start, cutoff_timestamp,    # 15, 16: WHERE range
#         grid_id                              # 17: WHERE grid_id
#     )

#     with engine.connect() as conn:
#         df = pd.read_sql(query, conn, params=params)

#     if df.empty:
#         return None

#     row = df.iloc[0]
#     avg_act = float(row["recent_avg"]) if pd.notnull(row["recent_avg"]) else 0.0
#     base_act = float(row["baseline_avg"]) if pd.notnull(row["baseline_avg"]) else 0.0
#     growth = (avg_act - base_act) / (base_act + 1e-6)
#     peak = (float(row["recent_max"]) / (avg_act + 1e-6)) if avg_act > 0 else 1.0
#     std_val = float(row["recent_std"]) if pd.notnull(row["recent_std"]) else 0.0
#     var = std_val / (avg_act + 1e-6)

#     # Dynamic calculation of internet_share exactly matching train_ml3.py
#     recent_tot = float(row["recent_sum"]) if pd.notnull(row["recent_sum"]) else 0.0
#     recent_net = float(row["recent_internet_sum"]) if pd.notnull(row["recent_internet_sum"]) else 0.0
#     net_share = recent_net / (recent_tot + 1e-6)

#     features = {
#         "avg_activity": round(avg_act, 4),
#         "activity_growth": round(np.clip(growth, -1.0, 10.0), 4),
#         "active_hours": int(row["active_hours"]) if pd.notnull(row["active_hours"]) else 0,
#         "peak_ratio": round(max(1.0, peak), 4),
#         "variability": round(max(0.0, var), 4),
#         "internet_share": round(np.clip(net_share, 0.0, 1.0), 4)
#     }

#     # Reorder columns to guarantee exact match with persisted training schema
#     schema = load_feature_schema()
#     return pd.DataFrame([features])[schema]

# def predict_grid_risk(grid_id: int, cutoff_timestamp: str = "2013-11-07 23:00:00"):
#     model = load_model()
#     ts = datetime.fromisoformat(cutoff_timestamp)
#     feat_df = extract_features_for_grid(grid_id, ts)
    
#     if feat_df is None:
#         return {"grid_id": grid_id, "error": "No telemetry found"}

#     risk_prob = float(model.predict_proba(feat_df)[:, 1][0])
#     risk_label = int(model.predict(feat_df)[0])

#     return {
#         "grid_id": grid_id,
#         "features": feat_df.to_dict(orient="records")[0],
#         "risk_probability": round(risk_prob, 4),
#         "risk_flag": risk_label
#     }

# if __name__ == "__main__":
#     import sys
#     test_grid = int(sys.argv[1]) if len(sys.argv) > 1 else 5259
#     res = predict_grid_risk(test_grid)
#     print(res)




import os
import json
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine

DB_URL = "mysql+pymysql://root:root@localhost:3306/telecom_warehouse"
engine = create_engine(DB_URL, pool_pre_ping=True)

# Resolves path regardless of execution from root or phase6/
POSSIBLE_PATHS = [
    os.path.join("artifacts", "baseline_risk_model.joblib"),
    os.path.join("..", "artifacts", "baseline_risk_model.joblib"),
    os.path.join(os.path.dirname(__file__), "..", "artifacts", "baseline_risk_model.joblib")
]

MODEL_PATH = next((p for p in POSSIBLE_PATHS if os.path.exists(p)), "artifacts/baseline_risk_model.joblib")


def load_model_artifact():
    """Loads the trained HistGradientBoosting model, feature list, and learned optimal threshold."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}")
    artifact = joblib.load(MODEL_PATH)
    return artifact


def extract_features_for_grid(grid_id: int, cutoff_timestamp: datetime):
    """
    Extracts all 10 features matching train_ml3.py:
    - 6 rolling 24h summary features
    - 1 immediate momentum ratio (current activity vs 24h average)
    - 3 cyclical diurnal features (hour_sin, hour_cos, dayofweek)
    """
    recent_start = cutoff_timestamp - timedelta(hours=23)
    baseline_start = cutoff_timestamp - timedelta(hours=47)
    baseline_end = cutoff_timestamp - timedelta(hours=24)

    # Query aggregates 24h window + 24h baseline + current immediate activity at cutoff
    query = """
        SELECT 
            f.grid_id,
            AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_avg,
            MAX(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_max,
            STDDEV_POP(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_std,
            SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE 0.0 END) AS recent_sum,
            SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.internet_activity ELSE 0.0 END) AS recent_internet_sum,
            COUNT(DISTINCT CASE WHEN t.timestamp BETWEEN %s AND %s AND f.total_activity > 0 THEN t.hour ELSE NULL END) AS active_hours,
            AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS baseline_avg,
            MAX(CASE WHEN t.timestamp = %s THEN f.total_activity ELSE NULL END) AS immediate_activity
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp BETWEEN %s AND %s AND f.grid_id = %s
        GROUP BY f.grid_id;
    """
    params = (
        recent_start, cutoff_timestamp,      # recent_avg
        recent_start, cutoff_timestamp,      # recent_max
        recent_start, cutoff_timestamp,      # recent_std
        recent_start, cutoff_timestamp,      # recent_sum
        recent_start, cutoff_timestamp,      # recent_internet_sum
        recent_start, cutoff_timestamp,      # active_hours
        baseline_start, baseline_end,        # baseline_avg
        cutoff_timestamp,                    # immediate_activity at t
        baseline_start, cutoff_timestamp,    # WHERE range
        grid_id                              # WHERE grid_id
    )

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    if df.empty or pd.isnull(df.iloc[0]["recent_avg"]):
        return None

    row = df.iloc[0]
    avg_act = float(row["recent_avg"]) if pd.notnull(row["recent_avg"]) else 0.0
    base_act = float(row["baseline_avg"]) if pd.notnull(row["baseline_avg"]) else 0.0
    growth = (avg_act - base_act) / (base_act + 1e-6)
    peak = (float(row["recent_max"]) / (avg_act + 1e-6)) if avg_act > 0 else 1.0
    std_val = float(row["recent_std"]) if pd.notnull(row["recent_std"]) else 0.0
    var = std_val / (avg_act + 1e-6)

    recent_tot = float(row["recent_sum"]) if pd.notnull(row["recent_sum"]) else 0.0
    recent_net = float(row["recent_internet_sum"]) if pd.notnull(row["recent_internet_sum"]) else 0.0
    net_share = recent_net / (recent_tot + 1e-6)

    # Immediate Short-Term Momentum: Current volume vs 24h baseline
    curr_act = float(row["immediate_activity"]) if pd.notnull(row["immediate_activity"]) else avg_act
    imm_ratio = curr_act / (avg_act + 1e-6)

    # Diurnal Cyclicity Features
    hour_val = cutoff_timestamp.hour
    hour_sin = np.sin(2 * np.pi * hour_val / 24.0)
    hour_cos = np.cos(2 * np.pi * hour_val / 24.0)
    dayofweek = float(cutoff_timestamp.weekday())

    features = {
        "avg_activity": round(avg_act, 4),
        "activity_growth": round(float(np.clip(growth, -1.0, 10.0)), 4),
        "active_hours": float(row["active_hours"]) if pd.notnull(row["active_hours"]) else 0.0,
        "peak_ratio": round(float(max(1.0, peak)), 4),
        "variability": round(float(max(0.0, var)), 4),
        "internet_share": round(float(np.clip(net_share, 0.0, 1.0)), 4),
        "immediate_ratio": round(float(np.clip(imm_ratio, 0.0, 10.0)), 4),
        "hour_sin": round(float(hour_sin), 4),
        "hour_cos": round(float(hour_cos), 4),
        "dayofweek": dayofweek
    }

    artifact = load_model_artifact()
    feature_order = artifact.get("features", list(features.keys()))
    return pd.DataFrame([features])[feature_order]


def predict_grid_risk(grid_id: int, cutoff_timestamp: str = "2013-11-07 23:00:00"):
    """
    Predicts lookahead surge risk for a grid at a given timestamp using
    the trained tree-based model and the learned decision cutoff.
    """
    artifact = load_model_artifact()
    model = artifact["model"]
    optimal_threshold = artifact.get("optimal_threshold", 0.70)

    ts = datetime.fromisoformat(cutoff_timestamp)
    feat_df = extract_features_for_grid(grid_id, ts)

    if feat_df is None:
        return {"grid_id": grid_id, "error": f"No telemetry found for grid {grid_id} at {cutoff_timestamp}"}

    risk_prob = float(model.predict_proba(feat_df)[:, 1][0])
    
    # Use learned optimal threshold (0.70) instead of naive 0.50
    is_surge_flag = int(risk_prob >= optimal_threshold)

    # Multi-tier categorical classification for NOC triage
    if risk_prob >= optimal_threshold:
        risk_level = "CRITICAL"
    elif risk_prob >= 0.40:
        risk_level = "ELEVATED"
    else:
        risk_level = "NORMAL"

    return {
        "grid_id": grid_id,
        "cutoff_timestamp": cutoff_timestamp,
        "features": feat_df.to_dict(orient="records")[0],
        "risk_probability": round(risk_prob, 4),
        "optimal_threshold": round(optimal_threshold, 4),
        "risk_flag": is_surge_flag,
        "risk_level": risk_level
    }


if __name__ == "__main__":
    import sys
    test_grid = int(sys.argv[1]) if len(sys.argv) > 1 else 5259
    test_time = sys.argv[2] if len(sys.argv) > 2 else "2013-11-07 23:00:00"
    res = predict_grid_risk(test_grid, test_time)
    print(json.dumps(res, indent=2))