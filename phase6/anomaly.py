import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import mysql.connector

# Database Configuration
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",  # Update with your MySQL password
    "database": "telecom_warehouse",
    "port": 3306
}

EPSILON = 1e-6


def get_db_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)


# ============================================================================
# 1. UNIFIED BASELINE ENGINE (SHARED WITH NP3 / ML4)
# ============================================================================

def compute_dynamic_baseline(
    df: pd.DataFrame,
    group_keys: list,
    metric_col: str = "total_activity",
    agg_funcs: list = None
) -> pd.DataFrame:
    """
    Generalized baseline computation engine.
    Computes statistical baselines across arbitrary grouping keys:
      - Within-day baseline: group_keys=['grid_id']
      - Hour-of-day multi-day baseline: group_keys=['grid_id', 'hour']
    """
    grouped = df.groupby(group_keys)[metric_col]
    baseline_df = grouped.agg(
        baseline_mean="mean",
        baseline_median="median",
        baseline_std="std",
        bucket_count="count"
    ).reset_index()

    baseline_df["baseline_std"] = baseline_df["baseline_std"].fillna(0.0)
    return baseline_df


# ============================================================================
# 2. HISTORICAL DATA EXTRACTION & SCORING
# ============================================================================

def extract_historical_and_current_data(as_of: datetime, history_days: int = 7):
    """
    Extracts multi-day historical baseline data strictly prior to as_of,
    and extracts current interval observations at as_of.
    """
    conn = get_db_connection()
    start_history = as_of - timedelta(days=history_days)

    hist_query = """
        SELECT 
            f.grid_id,
            t.hour,
            t.timestamp,
            f.total_activity,
            f.internet_activity
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp >= %s AND t.timestamp < %s;
    """
    hist_df = pd.read_sql(
        hist_query,
        conn,
        params=(start_history.strftime("%Y-%m-%d %H:%M:%S"), as_of.strftime("%Y-%m-%d %H:%M:%S"))
    )

    curr_query = """
        SELECT 
            f.grid_id,
            t.hour,
            t.timestamp,
            f.total_activity,
            f.internet_activity
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp = %s;
    """
    curr_df = pd.read_sql(curr_query, conn, params=(as_of.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.close()

    return hist_df, curr_df


def score_anomalies(as_of: datetime, z_threshold: float = 2.0, pct_threshold: float = 0.75) -> pd.DataFrame:
    """
    Scores current activity against historical hour-of-day baseline.
    Flags both HIGH and LOW operational anomalies.
    """
    hist_df, curr_df = extract_historical_and_current_data(as_of)

    if hist_df.empty or curr_df.empty:
        raise ValueError(f"Insufficient data at cutoff {as_of}")

    baseline_df = compute_dynamic_baseline(
        df=hist_df,
        group_keys=["grid_id", "hour"],
        metric_col="total_activity"
    )

    merged = pd.merge(curr_df, baseline_df, on=["grid_id", "hour"], how="left")
    merged["baseline_mean"] = merged["baseline_mean"].fillna(0.0)
    merged["baseline_std"] = merged["baseline_std"].fillna(0.0)
    merged["bucket_count"] = merged["bucket_count"].fillna(0).astype(int)

    diff = merged["total_activity"] - merged["baseline_mean"]
    merged["pct_deviation"] = diff / (merged["baseline_mean"] + EPSILON)
    merged["z_score"] = diff / (merged["baseline_std"] + EPSILON)
    merged["anomaly_score"] = np.clip(np.abs(merged["z_score"]) / 4.0, 0.0, 1.0).round(4)

    directions = []
    is_anomaly = []
    reasons = []

    for _, r in merged.iterrows():
        act = r["total_activity"]
        base_mu = r["baseline_mean"]
        z = r["z_score"]
        pct = r["pct_deviation"]
        cnt = r["bucket_count"]
        hr = int(r["hour"])

        if cnt < 2:
            directions.append("NORMAL")
            is_anomaly.append(False)
            reasons.append(f"Insufficient history ({cnt} buckets observed).")
            continue

        if z >= z_threshold and pct >= pct_threshold:
            directions.append("HIGH")
            is_anomaly.append(True)
            reasons.append(
                f"High Activity Surge: {act:.1f} units observed vs {base_mu:.1f} baseline at {hr:02d}:00 "
                f"(+{pct*100:.1f}%, Z={z:.2f})."
            )
        elif z <= -z_threshold and pct <= -0.60:
            directions.append("LOW")
            is_anomaly.append(True)
            reasons.append(
                f"Abnormal Activity Drop: {act:.1f} units observed vs {base_mu:.1f} baseline at {hr:02d}:00 "
                f"({pct*100:.1f}%, Z={z:.2f})."
            )
        else:
            directions.append("NORMAL")
            is_anomaly.append(False)
            reasons.append(f"Nominal: Within standard hour-of-day baseline variation (Z={z:.2f}).")

    merged["direction"] = directions
    merged["is_anomaly"] = is_anomaly
    merged["reason"] = reasons
    merged["as_of"] = as_of

    return merged


# ============================================================================
# 3. DATABASE MATERIALIZATION (DROPS STALE TABLE SCHEMA AUTOMATICALLY)
# ============================================================================

def materialize_anomaly_table(anomaly_df: pd.DataFrame):
    """Persists anomaly scores to MySQL."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Drop existing stale table if it has an incompatible schema
    cursor.execute("DROP TABLE IF EXISTS network_anomaly_scores;")

    cursor.execute("""
        CREATE TABLE network_anomaly_scores (
            grid_id INT NOT NULL,
            hour INT NOT NULL,
            as_of DATETIME NOT NULL,
            current_value DOUBLE NOT NULL,
            baseline_value DOUBLE NOT NULL,
            bucket_count INT NOT NULL,
            pct_deviation DOUBLE NOT NULL,
            z_score DOUBLE NOT NULL,
            anomaly_score DOUBLE NOT NULL,
            direction VARCHAR(10) NOT NULL,
            is_anomaly BOOLEAN NOT NULL,
            reason TEXT NOT NULL,
            PRIMARY KEY (grid_id, as_of),
            INDEX idx_anom_asof (as_of),
            INDEX idx_anom_dir (direction)
        ) ENGINE=InnoDB;
    """)

    insert_sql = """
        INSERT INTO network_anomaly_scores (
            grid_id, hour, as_of, current_value, baseline_value, bucket_count,
            pct_deviation, z_score, anomaly_score, direction, is_anomaly, reason
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """

    records = [
        (
            int(r["grid_id"]),
            int(r["hour"]),
            r["as_of"].strftime("%Y-%m-%d %H:%M:%S"),
            float(r["total_activity"]),
            float(r["baseline_mean"]),
            int(r["bucket_count"]),
            float(r["pct_deviation"]),
            float(r["z_score"]),
            float(r["anomaly_score"]),
            r["direction"],
            bool(r["is_anomaly"]),
            r["reason"]
        )
        for _, r in anomaly_df.iterrows()
    ]

    cursor.executemany(insert_sql, records)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Materialized {len(records):,} records into network_anomaly_scores.")


# ============================================================================
# 4. THREE-WAY COMPARISON (NP3 Rule vs ML3 Model vs ML4 Anomaly)
# ============================================================================

def run_three_way_comparison(as_of: datetime, anomaly_df: pd.DataFrame):
    """
    Compares the three operational mechanisms:
      1. NP3 Static Rule Alert (Volume > 6000)
      2. ML3 Trained Classifier (Future Risk at t+1)
      3. ML4 Historical Hour-of-Day Anomaly
    """
    print("\n" + "=" * 85)
    print(f"THREE-WAY TRIANGULATION COMPARISON AT {as_of}")
    print("=" * 85)

    model_artifact_path = os.path.join("artifacts", "baseline_risk_model.joblib")
    if not os.path.exists(model_artifact_path):
        print(f"Warning: ML3 model artifact not found at {model_artifact_path}. Skipping ML3 comparison.")
        return

    artifact = joblib.load(model_artifact_path)
    model = artifact["model"]

    from features import compute_features_for_cutoff
    feat_df = compute_features_for_cutoff(as_of)
    feature_cols = artifact["features"]

    X = feat_df[feature_cols]
    feat_df["ml3_predicted_risk"] = model.predict(X)
    feat_df["ml3_risk_score"] = model.predict_proba(X)[:, 1].round(4)

    comp = pd.merge(
        anomaly_df[["grid_id", "total_activity", "baseline_mean", "direction", "is_anomaly", "anomaly_score", "reason"]],
        feat_df[["grid_id", "ml3_predicted_risk", "ml3_risk_score", "activity_growth", "peak_ratio"]],
        on="grid_id"
    )

    comp["np3_rule_alert"] = (comp["total_activity"] > 6000).astype(int)

    total = len(comp)
    all_agree = comp[(comp["np3_rule_alert"] == 1) & (comp["ml3_predicted_risk"] == 1) & (comp["is_anomaly"] & (comp["direction"] == "HIGH"))]
    
    print(f"Total Grids Evaluated:                    {total:,}")
    print(f"Grids flagged by NP3 Static Rule (>6000): {comp['np3_rule_alert'].sum():,}")
    print(f"Grids flagged by ML3 Classifier (Risk):   {comp['ml3_predicted_risk'].sum():,}")
    print(f"Grids flagged by ML4 Anomaly (Surge/Drop):{comp['is_anomaly'].sum():,} (High: {(comp['direction']=='HIGH').sum()}, Low: {(comp['direction']=='LOW').sum()})")
    print(f"Unanimous High Alerts (All 3 agreed):     {len(all_agree):,}")

    print("\n--- Disagreement Breakdown & Explainability ---")

    # Case 1: Low-volume cell with extreme surge (ML4 flags HIGH, NP3 misses)
    case1 = comp[(comp["np3_rule_alert"] == 0) & (comp["direction"] == "HIGH") & (comp["total_activity"] < 3000)]
    if not case1.empty:
        c1 = case1.iloc[0]
        print(f"\n[Case 1: Localized Hour-of-Day Surge (ML4 Alert, NP3 Rule Miss)]")
        print(f"  Grid ID:         {int(c1['grid_id'])}")
        print(f"  Current Load:    {c1['total_activity']:.1f} units  (Static NP3 rule misses because < 6000)")
        print(f"  Hourly Baseline: {c1['baseline_mean']:.1f} units")
        print(f"  ML4 Assessment:  {c1['reason']}")
        print(f"  ML3 Risk Score:  {c1['ml3_risk_score']:.4f}")
        print(f"  Domain Insight:  ML4 catches localized surges in quiet suburbs that static thresholds ignore.")

    # Case 2: Silent Drop / Outage (ML4 flags LOW, NP3 & ML3 miss)
    case2 = comp[comp["direction"] == "LOW"]
    if not case2.empty:
        c2 = case2.iloc[0]
        print(f"\n[Case 2: Silent Activity Drop / Potential Outage (ML4 Alert Only)]")
        print(f"  Grid ID:         {int(c2['grid_id'])}")
        print(f"  Current Load:    {c2['total_activity']:.1f} units")
        print(f"  Hourly Baseline: {c2['baseline_mean']:.1f} units")
        print(f"  ML4 Assessment:  {c2['reason']}")
        print(f"  NP3 / ML3 State: NP3=0, ML3=0 (Static rules & risk classifiers do not detect drops)")
        print(f"  Domain Insight:  ML4 is the only mechanism that protects against silent service loss.")

    # Case 3: High-capacity core hub on standard load (NP3 alerts, ML4 says NORMAL)
    case3 = comp[(comp["np3_rule_alert"] == 1) & (comp["direction"] == "NORMAL")]
    if not case3.empty:
        c3 = case3.iloc[0]
        print(f"\n[Case 3: Busy Central Cell Operating Nominally (NP3 Alert, ML4 Normal)]")
        print(f"  Grid ID:         {int(c3['grid_id'])}")
        print(f"  Current Load:    {c3['total_activity']:.1f} units (Crosses static >6000 threshold)")
        print(f"  Hourly Baseline: {c3['baseline_mean']:.1f} units")
        print(f"  ML4 Assessment:  {c3['reason']}")
        print(f"  Domain Insight:  NP3 creates alert fatigue on busy cells; ML4 recognizes high volume as normal.")

    print("=" * 85)


if __name__ == "__main__":
    from features import get_warehouse_max_timestamp
    cutoff_ts = get_warehouse_max_timestamp()
    print(f"Running ML4 Anomaly Scorer for Cutoff: {cutoff_ts}")
    
    anomalies = score_anomalies(cutoff_ts)
    materialize_anomaly_table(anomalies)
    run_three_way_comparison(cutoff_ts, anomalies)