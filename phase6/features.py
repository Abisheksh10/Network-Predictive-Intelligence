import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import mysql.connector

# Database Configuration
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",  # Update with your MySQL password
    "database": "telecom_warehouse",
    "port": 3306
}

EPSILON = 1e-6  # Division-by-zero guard


def get_db_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)


def get_warehouse_max_timestamp() -> datetime:
    """Returns the latest timestamp present in dim_time."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT MAX(timestamp) AS max_ts FROM dim_time;")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row or not row["max_ts"]:
        raise ValueError("No timestamps found in analytics warehouse.")
    return row["max_ts"]


def extract_raw_window_data(as_of: datetime, total_hours: int = 48) -> pd.DataFrame:
    """
    Extracts hourly grid activity strictly on or before as_of (t).
    Reads trailing `total_hours` (e.g. 48 hours for 24h recent + 24h baseline).
    """
    start_time = as_of - timedelta(hours=total_hours - 1)
    
    conn = get_db_connection()
    query = """
        SELECT 
            f.grid_id,
            t.timestamp,
            f.total_activity,
            f.internet_activity,
            f.total_calls,
            f.total_sms
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp BETWEEN %s AND %s
        ORDER BY f.grid_id ASC, t.timestamp ASC;
    """
    params = (
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        as_of.strftime("%Y-%m-%d %H:%M:%S")
    )
    
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


def compute_features_for_cutoff(as_of: datetime) -> pd.DataFrame:
    """
    Computes the 6 ML2 features for all active grids strictly using data <= as_of (t).
    Window splits:
      - Recent window: (as_of - 23h) to as_of (24 hours)
      - Baseline window: (as_of - 47h) to (as_of - 24h) (24 hours)
    """
    df = extract_raw_window_data(as_of, total_hours=48)
    
    if df.empty:
        raise ValueError(f"No activity data available in warehouse up to {as_of}")

    recent_start = as_of - timedelta(hours=23)
    baseline_start = as_of - timedelta(hours=47)
    baseline_end = as_of - timedelta(hours=24)

    recent_df = df[(df["timestamp"] >= recent_start) & (df["timestamp"] <= as_of)]
    baseline_df = df[(df["timestamp"] >= baseline_start) & (df["timestamp"] <= baseline_end)]

    # Compute Recent Window Aggregations (Trailing 24h)
    recent_grp = recent_df.groupby("grid_id")
    
    recent_stats = recent_grp.agg(
        avg_act=("total_activity", "mean"),
        max_act=("total_activity", "max"),
        std_act=("total_activity", "std"),
        sum_total=("total_activity", "sum"),
        sum_internet=("internet_activity", "sum"),
        active_hrs=("total_activity", lambda s: (s > 0).sum())
    ).reset_index()

    # Compute Baseline Window Aggregations (Prior 24h)
    baseline_grp = baseline_df.groupby("grid_id")
    baseline_stats = baseline_grp.agg(
        baseline_avg_act=("total_activity", "mean")
    ).reset_index()

    # Merge Recent and Baseline
    features_df = pd.merge(recent_stats, baseline_stats, on="grid_id", how="left")
    features_df["baseline_avg_act"] = features_df["baseline_avg_act"].fillna(0.0)

    # 1. avg_activity
    features_df["avg_activity"] = features_df["avg_act"].round(4)

    # 2. activity_growth: (recent_avg - baseline_avg) / (baseline_avg + epsilon)
    growth = (features_df["avg_act"] - features_df["baseline_avg_act"]) / (features_df["baseline_avg_act"] + EPSILON)
    # Clip extreme ratios when baseline is close to zero
    features_df["activity_growth"] = growth.clip(lower=-1.0, upper=10.0).round(4)

    # 3. active_hours: count of active hours [0-24] (scaled to integer)
    features_df["active_hours"] = features_df["active_hrs"].astype(int)

    # 4. peak_ratio: max_activity / (avg_activity + epsilon)
    peak_rat = features_df["max_act"] / (features_df["avg_act"] + EPSILON)
    features_df["peak_ratio"] = peak_rat.fillna(1.0).clip(lower=1.0).round(4)

    # 5. variability: std / (avg_activity + epsilon)
    features_df["std_act"] = features_df["std_act"].fillna(0.0)
    var = features_df["std_act"] / (features_df["avg_act"] + EPSILON)
    features_df["variability"] = var.fillna(0.0).clip(lower=0.0).round(4)

    # 6. internet_share: sum(internet) / (sum(total) + epsilon)
    net_share = features_df["sum_internet"] / (features_df["sum_total"] + EPSILON)
    features_df["internet_share"] = net_share.fillna(0.0).clip(lower=0.0, upper=1.0).round(4)

    # Add Temporal Marker
    features_df["feature_timestamp"] = as_of
    features_df["data_quality_status"] = "PASSED"

    # Select final canonical columns
    final_cols = [
        "grid_id",
        "avg_activity",
        "activity_growth",
        "active_hours",
        "peak_ratio",
        "variability",
        "internet_share",
        "feature_timestamp",
        "data_quality_status"
    ]
    return features_df[final_cols]


def materialize_feature_table(features_df: pd.DataFrame):
    """Persists computed features into MySQL tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create network_feature_table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_feature_table (
            grid_id INT NOT NULL,
            avg_activity DOUBLE NOT NULL,
            activity_growth DOUBLE NOT NULL,
            active_hours INT NOT NULL,
            peak_ratio DOUBLE NOT NULL,
            variability DOUBLE NOT NULL,
            internet_share DOUBLE NOT NULL,
            feature_timestamp DATETIME NOT NULL,
            data_quality_status VARCHAR(50) NOT NULL,
            PRIMARY KEY (grid_id, feature_timestamp),
            INDEX idx_feat_ts (feature_timestamp)
        ) ENGINE=InnoDB;
    """)

    insert_sql = """
        INSERT INTO network_feature_table (
            grid_id, avg_activity, activity_growth, active_hours,
            peak_ratio, variability, internet_share, feature_timestamp, data_quality_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            avg_activity=VALUES(avg_activity),
            activity_growth=VALUES(activity_growth),
            active_hours=VALUES(active_hours),
            peak_ratio=VALUES(peak_ratio),
            variability=VALUES(variability),
            internet_share=VALUES(internet_share),
            data_quality_status=VALUES(data_quality_status);
    """

    records = [
        (
            int(r["grid_id"]),
            float(r["avg_activity"]),
            float(r["activity_growth"]),
            int(r["active_hours"]),
            float(r["peak_ratio"]),
            float(r["variability"]),
            float(r["internet_share"]),
            r["feature_timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            r["data_quality_status"]
        )
        for _, r in features_df.iterrows()
    ]

    cursor.executemany(insert_sql, records)

    # Sync into grid_features for API4 serving
    cursor.execute("""
        INSERT INTO grid_features (
            grid_id, avg_activity, activity_growth, active_hours,
            peak_ratio, variability, internet_share, feature_timestamp, data_quality_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            avg_activity=VALUES(avg_activity),
            activity_growth=VALUES(activity_growth),
            active_hours=VALUES(active_hours),
            peak_ratio=VALUES(peak_ratio),
            variability=VALUES(variability),
            internet_share=VALUES(internet_share),
            feature_timestamp=VALUES(feature_timestamp),
            data_quality_status=VALUES(data_quality_status);
    """, records[0] if len(records) == 1 else records[0])  # Batch update will use executemany
    
    cursor.executemany("""
        INSERT INTO grid_features (
            grid_id, avg_activity, activity_growth, active_hours,
            peak_ratio, variability, internet_share, feature_timestamp, data_quality_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            avg_activity=VALUES(avg_activity),
            activity_growth=VALUES(activity_growth),
            active_hours=VALUES(active_hours),
            peak_ratio=VALUES(peak_ratio),
            variability=VALUES(variability),
            internet_share=VALUES(internet_share),
            feature_timestamp=VALUES(feature_timestamp),
            data_quality_status=VALUES(data_quality_status);
    """, records)

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Materialized {len(records):,} records into network_feature_table & grid_features.")


def run_pipeline(as_of: datetime = None):
    if as_of is None:
        as_of = get_warehouse_max_timestamp()
    print(f"Running ML2 Feature Engineering for cutoff t = {as_of} ...")
    features_df = compute_features_for_cutoff(as_of)
    materialize_feature_table(features_df)
    return features_df


if __name__ == "__main__":
    run_pipeline()