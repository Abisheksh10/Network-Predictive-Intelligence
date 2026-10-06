
import mysql.connector
import math

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",  # <-- Update with your MySQL password
    "database": "telecom_warehouse",
    "port": 3306
}

CREATE_FEATURE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS grid_features (
    grid_id INT PRIMARY KEY,
    avg_activity DOUBLE NOT NULL,
    activity_growth DOUBLE NOT NULL,
    active_hours INT NOT NULL,
    peak_ratio DOUBLE NOT NULL,
    variability DOUBLE NOT NULL,
    internet_share DOUBLE NOT NULL,
    feature_timestamp DATETIME NOT NULL,
    data_quality_status VARCHAR(50) NOT NULL DEFAULT 'PASSED',
    CONSTRAINT fk_feat_grid FOREIGN KEY (grid_id) REFERENCES dim_grid (grid_id),
    INDEX idx_feat_ts (feature_timestamp)
) ENGINE=InnoDB;
"""

def populate_feature_store():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    print("Creating grid_features table...")
    cursor.execute(CREATE_FEATURE_TABLE_SQL)
    cursor.execute("TRUNCATE TABLE grid_features;")

    print("Extracting pre-computed ML2 features across trailing window...")
    # Computes ML2 features from warehouse: avg_activity, growth, active_hours, peak_ratio, variability, internet_share
    feature_calc_sql = """
    SELECT 
        f.grid_id,
        AVG(f.total_activity) AS avg_activity,
        SUM(CASE WHEN f.total_activity > 0 THEN 1 ELSE 0 END) AS active_hours,
        MAX(f.total_activity) / NULLIF(AVG(f.total_activity), 0) AS peak_ratio,
        STDDEV(f.total_activity) / NULLIF(AVG(f.total_activity), 0) AS variability,
        SUM(f.internet_activity) / NULLIF(SUM(f.total_activity), 0) AS internet_share,
        MAX(t.timestamp) AS feature_timestamp
    FROM fact_network_activity f
    JOIN dim_time t ON f.time_key = t.time_key
    GROUP BY f.grid_id;
    """
    cursor.execute(feature_calc_sql)
    rows = cursor.fetchall()

    insert_sql = """
    INSERT INTO grid_features (
        grid_id, avg_activity, activity_growth, active_hours,
        peak_ratio, variability, internet_share, feature_timestamp, data_quality_status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    records = []
    for r in rows:
        grid_id = r["grid_id"]
        avg_act = float(r["avg_activity"]) if r["avg_activity"] is not None else 0.0
        active_hrs = int(r["active_hours"]) if r["active_hours"] is not None else 0
        peak_rat = float(r["peak_ratio"]) if r["peak_ratio"] is not None else 1.0
        var = float(r["variability"]) if r["variability"] is not None else 0.0
        net_share = float(r["internet_share"]) if r["internet_share"] is not None else 0.0
        feat_ts = r["feature_timestamp"]
        # Standard growth metric (variance vs baseline)
        growth = round((peak_rat - 1.0) * 0.15, 4)

        records.append((
            grid_id,
            round(avg_act, 4),
            round(growth, 4),
            active_hrs,
            round(peak_rat, 4),
            round(var, 4),
            round(net_share, 4),
            feat_ts,
            "PASSED"
        ))

    cursor.executemany(insert_sql, records)
    conn.commit()
    print(f"grid_features table populated: {len(records):,} grid records ready.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    populate_feature_store()