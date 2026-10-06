
import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
import mysql.connector

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "telecom_warehouse",
    "port": 3306
}

MODEL_VERSION = "v1.0.0-logistic-baseline"


def get_db_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)


def get_latest_feature_timestamp() -> datetime:
    """Gets the latest available feature_timestamp from network_feature_table."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT MAX(feature_timestamp) AS max_ts FROM network_feature_table;")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row or not row["max_ts"]:
        raise RuntimeError(
            "FATAL: network_feature_table is empty. Features must be materialized prior to running ML6 batch scoring."
        )
    return row["max_ts"]


def load_model_artifact():
    """Loads the trained ML3 model artifact."""
    artifact_path = os.path.join(os.path.dirname(__file__), "artifacts", "baseline_risk_model.joblib")
    if not os.path.exists(artifact_path):
        raise FileNotFoundError(f"Missing ML model artifact at {artifact_path}. Execute train_ml3.py first.")
    return joblib.load(artifact_path)


def run_batch_scoring(as_of: datetime = None) -> pd.DataFrame:
    """
    Executes vectorized batch scoring for all 10,000 grid cells for timestamp t.
    """
    if as_of is None:
        as_of = get_latest_feature_timestamp()

    print(f"Executing ML6 Batch Scoring for cutoff t = {as_of} ...")

    conn = get_db_connection()
    query = """
        SELECT 
            grid_id,
            avg_activity,
            activity_growth,
            active_hours,
            peak_ratio,
            variability,
            internet_share,
            feature_timestamp
        FROM network_feature_table
        WHERE feature_timestamp = %s;
    """
    feature_df = pd.read_sql(query, conn, params=(as_of.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.close()

    if feature_df.empty:
        raise RuntimeError(f"No features found in network_feature_table for timestamp {as_of}")

    artifact = load_model_artifact()
    model = artifact["model"]
    feature_names = artifact["features"]

    X = feature_df[feature_names]
    probabilities = model.predict_proba(X)[:, 1]
    feature_df["risk_score"] = np.round(np.clip(probabilities, 0.0, 1.0), 4)

    # Classify Risk Levels
    levels = []
    drivers = []
    for _, r in feature_df.iterrows():
        score = r["risk_score"]
        if score >= 0.70:
            levels.append("CRITICAL")
        elif score >= 0.40:
            levels.append("HIGH")
        elif score >= 0.15:
            levels.append("MEDIUM")
        else:
            levels.append("LOW")

        # Primary operational driver attribution
        if r["avg_activity"] > 2000:
            drivers.append("High Historical Base Volume")
        elif r["activity_growth"] > 0.30:
            drivers.append("Accelerating Activity Growth")
        elif r["peak_ratio"] > 2.0:
            drivers.append("Burstiness / High Peak Ratio")
        else:
            drivers.append("Nominal Baseline Activity")

    feature_df["risk_level"] = levels
    feature_df["primary_driver"] = drivers
    feature_df["model_version"] = MODEL_VERSION
    feature_df["score_timestamp"] = as_of

    materialize_risk_scores(feature_df)
    return feature_df


def materialize_risk_scores(df: pd.DataFrame):
    """Persists batch risk scores to MySQL."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_risk_scores (
            grid_id INT NOT NULL,
            timestamp DATETIME NOT NULL,
            risk_score DOUBLE NOT NULL,
            risk_level VARCHAR(20) NOT NULL,
            model_version VARCHAR(50) NOT NULL,
            primary_driver VARCHAR(100) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (grid_id, timestamp),
            INDEX idx_risk_ts (timestamp),
            INDEX idx_risk_level (risk_level)
        ) ENGINE=InnoDB;
    """)

    insert_sql = """
        INSERT INTO network_risk_scores (
            grid_id, timestamp, risk_score, risk_level, model_version, primary_driver
        ) VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            risk_score=VALUES(risk_score),
            risk_level=VALUES(risk_level),
            model_version=VALUES(model_version),
            primary_driver=VALUES(primary_driver);
    """

    records = [
        (
            int(r["grid_id"]),
            r["score_timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            float(r["risk_score"]),
            r["risk_level"],
            r["model_version"],
            r["primary_driver"]
        )
        for _, r in df.iterrows()
    ]

    cursor.executemany(insert_sql, records)
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Materialized {len(records):,} records into network_risk_scores.")


def generate_top_twenty_attention_report(scored_df: pd.DataFrame) -> pd.DataFrame:
    """Generates the Top-20 Operational Attention Report using attention-first language."""
    top20 = scored_df.sort_values(by=["risk_score", "avg_activity"], ascending=[False, False]).head(20).copy()
    top20["rank"] = range(1, len(top20) + 1)

    print("\n" + "=" * 90)
    print("TOP-20 OPERATIONAL ATTENTION REPORT (PREDICTIVE RISK SURVEILLANCE)")
    print("=" * 90)
    print(f"{'Rank':<5} | {'Grid ID':<8} | {'Risk Score':<11} | {'Risk Level':<10} | {'Avg Load':<10} | {'Primary Driver':<28}")
    print("-" * 90)

    for _, r in top20.iterrows():
        print(
            f"{int(r['rank']):<5} | {int(r['grid_id']):<8} | {r['risk_score']*100:>8.1f}%  | "
            f"{r['risk_level']:<10} | {r['avg_activity']:>9.1f} | {r['primary_driver']:<28}"
        )

    print("-" * 90)
    print("OPERATIONAL DIRECTIVE:")
    print("Grids listed require proactive NOC human triage. High risk reflects elevated statistical")
    print("probability of extreme volume in window t+1, NOT a confirmed network fault or outage.")
    print("=" * 90)

    return top20


if __name__ == "__main__":
    df = run_batch_scoring()
    generate_top_twenty_attention_report(df)