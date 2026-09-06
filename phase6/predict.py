import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine

DB_URL = "mysql+pymysql://root:root@localhost:3306/telecom_warehouse"
engine = create_engine(DB_URL)

MODEL_PATH = os.path.join("..", "artifacts", "baseline_risk_model.joblib")
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = os.path.join("artifacts", "baseline_risk_model.joblib")

def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}")
    artifact = joblib.load(MODEL_PATH)
    return artifact["model"]

def extract_features_for_grid(grid_id: int, cutoff_timestamp: datetime):
    recent_start = cutoff_timestamp - timedelta(hours=23)
    baseline_start = cutoff_timestamp - timedelta(hours=47)
    baseline_end = cutoff_timestamp - timedelta(hours=24)

    query = """
        SELECT 
            f.grid_id,
            AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_avg,
            MAX(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_max,
            STDDEV_POP(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_std,
            COUNT(DISTINCT CASE WHEN t.timestamp BETWEEN %s AND %s AND f.total_activity > 0 THEN t.hour ELSE NULL END) AS active_hours,
            AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS baseline_avg
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp BETWEEN %s AND %s AND f.grid_id = %s
        GROUP BY f.grid_id;
    """
    # Exactly 13 params matching the 13 %s placeholders:
    params = (
        recent_start, cutoff_timestamp,      # 1, 2: recent_avg
        recent_start, cutoff_timestamp,      # 3, 4: recent_max
        recent_start, cutoff_timestamp,      # 5, 6: recent_std
        recent_start, cutoff_timestamp,      # 7, 8: active_hours
        baseline_start, baseline_end,        # 9, 10: baseline_avg
        baseline_start, cutoff_timestamp,    # 11, 12: WHERE timestamp range
        grid_id                              # 13: WHERE grid_id
    )

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)

    if df.empty:
        return None

    # INFERENCE FEATURE RECONSTRUCTION (DEFECTIVE: Training-Serving Skew for CL1)
    row = df.iloc[0]
    avg_act = float(row["recent_avg"]) if pd.notnull(row["recent_avg"]) else 0.0
    base_act = float(row["baseline_avg"]) if pd.notnull(row["baseline_avg"]) else 0.0
    growth = (avg_act - base_act) / (base_act + 1e-6)
    peak = (float(row["recent_max"]) / (avg_act + 1e-6)) if avg_act > 0 else 1.0
    std_val = float(row["recent_std"]) if pd.notnull(row["recent_std"]) else 0.0
    var = std_val / (avg_act + 1e-6)

    # Hardcoded schema & static default simulating the inference defect
    features = {
        "avg_activity": round(avg_act, 4),
        "activity_growth": round(np.clip(growth, -1.0, 10.0), 4),
        "active_hours": int(row["active_hours"]) if pd.notnull(row["active_hours"]) else 0,
        "peak_ratio": round(max(1.0, peak), 4),
        "variability": round(max(0.0, var), 4),
        "internet_share": 0.5000  # <--- DEFECT: Hardcoded static default
    }
    return pd.DataFrame([features])

def predict_grid_risk(grid_id: int, cutoff_timestamp: str = "2013-11-07 23:00:00"):
    model = load_model()
    ts = datetime.fromisoformat(cutoff_timestamp)
    feat_df = extract_features_for_grid(grid_id, ts)
    
    if feat_df is None:
        return {"grid_id": grid_id, "error": "No telemetry found"}

    risk_prob = float(model.predict_proba(feat_df)[:, 1][0])
    risk_label = int(model.predict(feat_df)[0])

    return {
        "grid_id": grid_id,
        "features": feat_df.to_dict(orient="records")[0],
        "risk_probability": round(risk_prob, 4),
        "risk_flag": risk_label
    }

if __name__ == "__main__":
    import sys
    test_grid = int(sys.argv[1]) if len(sys.argv) > 1 else 5259
    res = predict_grid_risk(test_grid)
    print(res)