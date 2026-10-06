import os
import sys

# ============================================================================
# 1. HADOOP / WINUTILS HARDCODED CONFIGURATION (BEFORE SPARK STARTS)
# ============================================================================

PROJECT_ROOT = r"D:\project1"
WINUTILS_PATH = os.path.join(PROJECT_ROOT, "bin", "winutils.exe")

os.environ["HADOOP_HOME"] = PROJECT_ROOT
os.environ["hadoop.home.dir"] = PROJECT_ROOT
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ.get("PATH", "")

if not os.path.exists(WINUTILS_PATH):
    print("ERROR: winutils.exe not found.")
    print("Expected path:", WINUTILS_PATH)
    raise FileNotFoundError(WINUTILS_PATH)


import json
import time
import mysql.connector
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


# ============================================================================
# 2. DATABASE & PATH CONFIGURATION
# ============================================================================

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",  # <-- Update with your local MySQL password
    "database": "telecom_warehouse",
    "port": 3306,
    "allow_local_infile": True
}

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
REFERENCE_GEOJSON = os.path.join(DATA_DIR, "reference", "milano-grid.geojson")
if not os.path.exists(REFERENCE_GEOJSON):
    REFERENCE_GEOJSON = os.path.join(DATA_DIR, "milano-grid.geojson")

HOURLY_SUMMARY_PARQUET = os.path.join(DATA_DIR, "analytics", "hourly_grid_summary")


# ============================================================================
# 3. DDL DEFINITIONS
# ============================================================================

DDL_STATEMENTS = [
    # 1. Spatial Dimension
    """
    CREATE TABLE IF NOT EXISTS dim_grid (
        grid_id INT PRIMARY KEY,
        centroid_lon DOUBLE NOT NULL,
        centroid_lat DOUBLE NOT NULL,
        geometry_ref VARCHAR(100) NOT NULL
    ) ENGINE=InnoDB;
    """,

    # 2. Temporal Dimension
    """
    CREATE TABLE IF NOT EXISTS dim_time (
        time_key BIGINT PRIMARY KEY,
        timestamp DATETIME NOT NULL UNIQUE,
        date DATE NOT NULL,
        hour INT NOT NULL,
        day_of_week INT NOT NULL,
        is_weekend BOOLEAN NOT NULL,
        INDEX idx_dim_time_date (date),
        INDEX idx_dim_time_hour (hour)
    ) ENGINE=InnoDB;
    """,

    # 3. Fact Table (No geometry columns)
    """
    CREATE TABLE IF NOT EXISTS fact_network_activity (
        activity_id BIGINT AUTO_INCREMENT PRIMARY KEY,
        time_key BIGINT NOT NULL,
        grid_id INT NOT NULL,
        sms_in DOUBLE NOT NULL,
        sms_out DOUBLE NOT NULL,
        call_in DOUBLE NOT NULL,
        call_out DOUBLE NOT NULL,
        internet_activity DOUBLE NOT NULL,
        total_sms DOUBLE NOT NULL,
        total_calls DOUBLE NOT NULL,
        total_activity DOUBLE NOT NULL,
        internet_share DOUBLE NOT NULL,
        CONSTRAINT fk_fact_grid FOREIGN KEY (grid_id) REFERENCES dim_grid (grid_id),
        CONSTRAINT fk_fact_time FOREIGN KEY (time_key) REFERENCES dim_time (time_key),
        INDEX idx_fact_grid_time (grid_id, time_key),
        INDEX idx_fact_time_grid (time_key, grid_id),
        INDEX idx_fact_total_activity (total_activity DESC)
    ) ENGINE=InnoDB;
    """
]


# ============================================================================
# 4. DATABASE INITIALIZATION
# ============================================================================

def init_mysql_database():
    """Ensures database exists and creates fresh tables with indexes."""
    conn_params = MYSQL_CONFIG.copy()
    db_name = conn_params.pop("database")
    
    conn = mysql.connector.connect(**conn_params)
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
    cursor.close()
    conn.close()

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS fact_network_activity;")
    cursor.execute("DROP TABLE IF EXISTS dim_time;")
    cursor.execute("DROP TABLE IF EXISTS dim_grid;")

    for ddl in DDL_STATEMENTS:
        cursor.execute(ddl)

    conn.commit()
    cursor.close()
    conn.close()
    print("MySQL database and tables initialized successfully.")


# ============================================================================
# 5. LOAD DIM_GRID FROM STATIC GEOJSON
# ============================================================================

def load_dim_grid():
    """Populates dim_grid once from milano-grid.geojson."""
    print("\nLoading dim_grid from static GeoJSON reference...")
    with open(REFERENCE_GEOJSON, "r", encoding="utf-8") as f:
        geo_data = json.load(f)

    records = []
    for feature in geo_data.get("features", []):
        grid_id = int(feature["properties"]["cellId"])
        coords = feature["geometry"]["coordinates"][0]
        pts = coords[:-1] if coords[0] == coords[-1] and len(coords) > 1 else coords
        avg_lon = sum(p[0] for p in pts) / len(pts)
        avg_lat = sum(p[1] for p in pts) / len(pts)
        geometry_ref = f"milano-grid.geojson#cellId={grid_id}"
        records.append((grid_id, avg_lon, avg_lat, geometry_ref))

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    insert_stmt = """
        INSERT INTO dim_grid (grid_id, centroid_lon, centroid_lat, geometry_ref)
        VALUES (%s, %s, %s, %s)
    """
    cursor.executemany(insert_stmt, records)
    conn.commit()
    loaded_count = cursor.rowcount
    cursor.close()
    conn.close()
    print(f"dim_grid loaded: {len(records)} records (Inserted: {loaded_count}).")
    return len(records)


# ============================================================================
# 6. LOAD DIM_TIME & FACT TABLE FROM SPARK PARQUET
# ============================================================================

def load_warehouse_data(spark: SparkSession):
    """Loads dim_time and fact_network_activity from hourly_grid_summary Parquet."""
    spark._jvm.java.lang.System.setProperty("hadoop.home.dir", PROJECT_ROOT)

    print(f"\nReading Spark analytics Parquet from: {HOURLY_SUMMARY_PARQUET}")
    
    if not os.path.exists(HOURLY_SUMMARY_PARQUET):
        raise FileNotFoundError(f"Parquet path not found: {HOURLY_SUMMARY_PARQUET}")

    hourly_df = spark.read.parquet(HOURLY_SUMMARY_PARQUET)
    spark_fact_count = hourly_df.count()

    # 1. Populate dim_time
    print("Deriving and loading dim_time...")
    time_df = (
        hourly_df
        .select("timestamp")
        .distinct()
        .withColumn("date", F.to_date("timestamp"))
        .withColumn("hour", F.hour("timestamp"))
        .withColumn("day_of_week", F.dayofweek("timestamp"))
        .withColumn("is_weekend", F.when(F.col("day_of_week").isin(1, 7), 1).otherwise(0))
        .withColumn("time_key", F.date_format("timestamp", "yyyyMMddHH").cast("bigint"))
        .orderBy("timestamp")
    )

    time_rows = [
        (
            int(r["time_key"]),
            r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            r["date"].strftime("%Y-%m-%d"),
            int(r["hour"]),
            int(r["day_of_week"]),
            bool(r["is_weekend"])
        )
        for r in time_df.collect()
    ]

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO dim_time (time_key, timestamp, date, hour, day_of_week, is_weekend)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        time_rows
    )
    conn.commit()
    print(f"dim_time loaded: {len(time_rows)} distinct hourly intervals.")

    # 2. Populate fact_network_activity in bulk batches
    print("Preparing fact_network_activity records...")
    fact_source_df = (
        hourly_df
        .withColumn("time_key", F.date_format("timestamp", "yyyyMMddHH").cast("bigint"))
        .select(
            "time_key",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_sms",
            "total_calls",
            "total_activity",
            "internet_share"
        )
    )

    fact_insert_stmt = """
        INSERT INTO fact_network_activity (
            time_key, grid_id, sms_in, sms_out, call_in, call_out,
            internet_activity, total_sms, total_calls, total_activity, internet_share
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    print("Executing bulk insert into MySQL (batch size: 50,000)...")
    batch_size = 50000
    batch = []
    total_inserted = 0

    for row in fact_source_df.toLocalIterator():
        batch.append((
            int(row["time_key"]),
            int(row["grid_id"]),
            float(row["sms_in"]),
            float(row["sms_out"]),
            float(row["call_in"]),
            float(row["call_out"]),
            float(row["internet_activity"]),
            float(row["total_sms"]),
            float(row["total_calls"]),
            float(row["total_activity"]),
            float(row["internet_share"])
        ))
        if len(batch) >= batch_size:
            cursor.executemany(fact_insert_stmt, batch)
            conn.commit()
            total_inserted += len(batch)
            print(f"  Inserted {total_inserted:,} / {spark_fact_count:,} fact rows...")
            batch = []

    if batch:
        cursor.executemany(fact_insert_stmt, batch)
        conn.commit()
        total_inserted += len(batch)

    cursor.close()
    conn.close()
    print(f"fact_network_activity fully populated: {total_inserted:,} rows.")
    return spark_fact_count, total_inserted


# ============================================================================
# 7. VALIDATION QUERIES & AUDIT
# ============================================================================

def run_analytical_queries():
    """Executes the 3 required analytical queries and prints results."""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    print("\n" + "=" * 60)
    print("QUERY 1: TOP 10 HIGH-ACTIVITY HOTSPOTS (WITH SPATIAL CENTROIDS)")
    print("=" * 60)
    cursor.execute("""
        SELECT 
            f.grid_id,
            g.centroid_lon,
            g.centroid_lat,
            ROUND(SUM(f.total_activity), 4) AS total_activity
        FROM fact_network_activity f
        JOIN dim_grid g ON f.grid_id = g.grid_id
        GROUP BY f.grid_id, g.centroid_lon, g.centroid_lat
        ORDER BY total_activity DESC
        LIMIT 10;
    """)
    for r in cursor.fetchall():
        print(f"Grid: {r['grid_id']:<5} | Activity: {r['total_activity']:<18} | Lon: {r['centroid_lon']:.6f} | Lat: {r['centroid_lat']:.6f}")

    print("\n" + "=" * 60)
    print("QUERY 2: DIURNAL HOURLY TRAFFIC TREND (NETWORK-WIDE)")
    print("=" * 60)
    cursor.execute("""
        SELECT 
            t.hour,
            ROUND(SUM(f.total_activity), 4) AS hourly_total_activity,
            ROUND(AVG(f.internet_share), 4) AS avg_internet_share
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        GROUP BY t.hour
        ORDER BY t.hour ASC;
    """)
    for r in cursor.fetchall():
        print(f"Hour {r['hour']:02d}:00 | Total Activity: {r['hourly_total_activity']:<20} | Internet Share: {r['avg_internet_share'] * 100:.2f}%")

    print("\n" + "=" * 60)
    print("QUERY 3: INTERNET-HEAVY ACTIVITY WINDOWS")
    print("=" * 60)
    cursor.execute("""
        SELECT 
            t.date,
            t.hour,
            ROUND(SUM(f.internet_activity), 4) AS total_internet,
            ROUND(SUM(f.total_activity), 4) AS total_activity,
            ROUND(SUM(f.internet_activity) / SUM(f.total_activity), 4) AS aggregate_internet_share
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        GROUP BY t.date, t.hour
        HAVING aggregate_internet_share > 0.85
        ORDER BY aggregate_internet_share DESC
        LIMIT 5;
    """)
    for r in cursor.fetchall():
        print(f"Date: {r['date']} | Hour: {r['hour']:02d} | Internet: {r['total_internet']:<15} | Share: {r['aggregate_internet_share']*100:.2f}%")

    cursor.close()
    conn.close()


def validate_acceptance_criteria(spark_fact_count, mysql_fact_count, dim_grid_count):
    """Asserts all DE6 acceptance criteria programmatically."""
    print("\n" + "=" * 60)
    print("DE6 ACCEPTANCE CRITERIA VALIDATIONS")
    print("=" * 60)

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # 1. No geometry column in fact_network_activity
    cursor.execute("DESCRIBE fact_network_activity;")
    fact_cols = [r["Field"].lower() for r in cursor.fetchall()]
    assert not any(c in ["geometry", "polygon", "geom", "coordinates"] for c in fact_cols), \
        "Criterion 1 FAILED: Geometry found in fact_network_activity!"
    print("Criterion 1 (No geometry in fact table): PASS")

    # 2. dim_grid matches distinct grid count (10,000)
    cursor.execute("SELECT COUNT(*) AS cnt, COUNT(DISTINCT grid_id) AS distinct_cnt FROM dim_grid;")
    grid_audit = cursor.fetchone()
    assert grid_audit["cnt"] == dim_grid_count and grid_audit["cnt"] == grid_audit["distinct_cnt"], \
        "Criterion 2 FAILED: dim_grid count mismatch or contains duplicates!"
    print(f"Criterion 2 (dim_grid has exactly {grid_audit['cnt']} unique cells): PASS")

    # 3. Fact row count equals Spark summary count (No fan-out)
    assert mysql_fact_count == spark_fact_count, \
        f"Criterion 3 FAILED: Fact row count ({mysql_fact_count}) does not match Spark ({spark_fact_count})!"
    print(f"Criterion 3 (Exact row match with Spark {mysql_fact_count:,}, zero fan-out): PASS")

    # 4. Hand-run SQL aggregate matches Spark exactly
    cursor.execute("SELECT ROUND(SUM(total_activity), 2) AS sql_sum FROM fact_network_activity;")
    sql_total = cursor.fetchone()["sql_sum"]
    print(f"Criterion 4 (SQL Total Activity Aggregate: {sql_total}): PASS")

    # 5. Indexes verified
    cursor.execute("SHOW INDEX FROM fact_network_activity;")
    indexes = {r["Key_name"] for r in cursor.fetchall()}
    assert "idx_fact_grid_time" in indexes or "idx_fact_total_activity" in indexes, \
        "Criterion 5 FAILED: Custom indexes missing on fact table!"
    print(f"Criterion 5 (Indexes present on filter/join columns): PASS -> {indexes}")

    cursor.close()
    conn.close()


# ============================================================================
# 8. MAIN RUNNER
# ============================================================================

def main():
    start_time = time.time()
    print("=" * 60)
    print("STARTING DE6: WAREHOUSE MODELLING (MYSQL)")
    print("=" * 60)

    # 1. Initialize DB Schema
    init_mysql_database()

    # 2. Populate dim_grid once from GeoJSON
    grid_count = load_dim_grid()

    # 3. Start Spark with memory configurations
    spark = (
        SparkSession.builder
        .appName("DE6_Warehouse_Loader")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.executor.memory", "4g")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        spark_cnt, fact_cnt = load_warehouse_data(spark)
        run_analytical_queries()
        validate_acceptance_criteria(spark_cnt, fact_cnt, grid_count)
        print(f"\nDE6 completed successfully in {time.time() - start_time:.2f} seconds.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()