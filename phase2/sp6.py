import os
import glob
import shutil

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from sp2 import run_sp2
from sp3 import run_sp3


# ============================================================
# 1. PATHS CONFIGURATION
# ============================================================

PROJECT_ROOT = r"D:\project1"
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
REFERENCE_DIR = os.path.join(DATA_DIR, "reference")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
ANALYTICS_DIR = os.path.join(DATA_DIR, "analytics")

WINUTILS_PATH = os.path.join(PROJECT_ROOT, "bin", "winutils.exe")

os.environ["HADOOP_HOME"] = PROJECT_ROOT
os.environ["hadoop.home.dir"] = PROJECT_ROOT
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ.get("PATH", "")


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def get_directory_size(directory):
    total_size = 0
    if not os.path.exists(directory):
        return 0
    for root, _, files in os.walk(directory):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)
    return total_size


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# ============================================================
# 3. SP6 MAIN EXECUTION
# ============================================================

def run_sp6(spark):

    # Set JVM Hadoop home directory directly
    spark._jvm.java.lang.System.setProperty("hadoop.home.dir", PROJECT_ROOT)

    print("\n" + "=" * 60)
    print("SP6 — WRITE PROCESSED & ANALYTICS DATA")
    print("=" * 60)

    os.makedirs(REFERENCE_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(ANALYTICS_DIR, exist_ok=True)

    # 1. Run Ingestion & Transformations
    clean_network_df = run_sp2(spark)

    (
        hourly_grid_summary,
        daily_traffic_summary,
        hotspot_ranking,
        peak_activity_hour
    ) = run_sp3(spark)


    # ========================================================
    # 2. GEOMETRY VALIDATION
    # ========================================================

    print("\n===== 1. GEOMETRY VALIDATION (ANALYTICS GRAIN) =====")
    geo_cols = [c for c in hourly_grid_summary.columns if c.lower() in ["geometry", "polygon", "geom"]]
    assert len(geo_cols) == 0, "SP6 FAILED: Geometry column exists in hourly_grid_summary."
    print("Pre-write geometry check: PASS (No geometry in analytics fact summary)")


    # ========================================================
    # 3. WRITE CLEAN ACTIVITY (PARQUET PARTITIONED BY DATE)
    # ========================================================

    print("\n===== 2. WRITE CLEAN ACTIVITY (PARTITIONED BY DATE) =====")
    activity_output_path = os.path.join(PROCESSED_DIR, "activity")

    if os.path.exists(activity_output_path):
        shutil.rmtree(activity_output_path)

    # Repartition by date before writing to avoid local sort spills
    (
        clean_network_df
        .repartition("date")
        .write
        .mode("overwrite")
        .partitionBy("date")
        .parquet(activity_output_path)
    )
    print(f"Clean activity Parquet written: {activity_output_path}")

    # Validate physical date partition folders on disk
    date_partitions = [
        d for d in os.listdir(activity_output_path)
        if os.path.isdir(os.path.join(activity_output_path, d)) and d.startswith("date=")
    ]
    date_partitions.sort()
    print(f"Date partitions verified on disk ({len(date_partitions)}): {date_partitions}")
    assert len(date_partitions) > 0, "SP6 FAILED: No date partition directories found on disk."


    # ========================================================
    # 4. ROUND-TRIP VALIDATION — CLEAN ACTIVITY
    # ========================================================

    print("\n===== 3. ROUND-TRIP VALIDATION — CLEAN ACTIVITY =====")
    processed_activity_df = spark.read.parquet(activity_output_path)

    orig_act_count = clean_network_df.count()
    rt_act_count = processed_activity_df.count()

    print(f"Original clean activity count: {orig_act_count}")
    print(f"Round-trip activity count    : {rt_act_count}")
    assert orig_act_count == rt_act_count, "SP6 FAILED: Activity row count mismatch after round trip!"

    orig_fields = {f.name: f.dataType.simpleString() for f in clean_network_df.schema.fields}
    rt_fields = {f.name: f.dataType.simpleString() for f in processed_activity_df.schema.fields}
    assert orig_fields == rt_fields, "SP6 FAILED: Activity schema mismatch after round trip!"
    print("Activity count & schema round-trip validation: PASS")


    # ========================================================
    # 5. WRITE HOURLY GRID SUMMARY (PARQUET)
    # ========================================================

    print("\n===== 4. WRITE HOURLY GRID SUMMARY (ANALYTICS LAYER) =====")
    hourly_output_path = os.path.join(ANALYTICS_DIR, "hourly_grid_summary")

    if os.path.exists(hourly_output_path):
        shutil.rmtree(hourly_output_path)

    (
        hourly_grid_summary
        .write
        .mode("overwrite")
        .parquet(hourly_output_path)
    )
    print(f"Hourly grid summary Parquet written: {hourly_output_path}")


    # ========================================================
    # 6. ROUND-TRIP VALIDATION — HOURLY GRID SUMMARY
    # ========================================================

    print("\n===== 5. ROUND-TRIP VALIDATION — HOURLY SUMMARY =====")
    parquet_hourly_df = spark.read.parquet(hourly_output_path)

    orig_hourly_count = hourly_grid_summary.count()
    rt_hourly_count = parquet_hourly_df.count()

    print(f"Original hourly row count   : {orig_hourly_count}")
    print(f"Round-trip hourly row count : {rt_hourly_count}")
    assert orig_hourly_count == rt_hourly_count, "SP6 FAILED: Hourly row count mismatch after round trip!"

    distinct_rt_count = parquet_hourly_df.select("grid_id", "timestamp").distinct().count()
    duplicate_count = rt_hourly_count - distinct_rt_count
    print(f"Duplicate (grid_id, timestamp) combinations: {duplicate_count}")
    assert duplicate_count == 0, "SP6 FAILED: Duplicates found on (grid_id, timestamp) after round trip!"

    assert not any(c.lower() in ["geometry", "polygon", "geom"] for c in parquet_hourly_df.columns), \
        "SP6 FAILED: Geometry exists in hourly_grid_summary Parquet!"
    print("Hourly summary round-trip & duplicate assertion: PASS")


    # ========================================================
    # 7. WRITE DASHBOARD SUMMARY (SINGLE CSV)
    # ========================================================

    print("\n===== 6. WRITE DASHBOARD SUMMARY (CSV) =====")
    dashboard_summary = (
        daily_traffic_summary
        .groupBy("date")
        .agg(
            F.sum("sms_in").alias("sms_in"),
            F.sum("sms_out").alias("sms_out"),
            F.sum("call_in").alias("call_in"),
            F.sum("call_out").alias("call_out"),
            F.sum("internet_activity").alias("internet_activity"),
            F.sum("total_sms").alias("total_sms"),
            F.sum("total_calls").alias("total_calls"),
            F.sum("daily_activity").alias("total_activity"),  # <-- Fixed column name reference
            F.countDistinct("grid_id").alias("active_grids")
        )
        .orderBy("date")
    )

    dashboard_csv_temp = os.path.join(ANALYTICS_DIR, "_dashboard_summary_csv")
    dashboard_csv_path = os.path.join(ANALYTICS_DIR, "dashboard_summary.csv")

    if os.path.exists(dashboard_csv_temp):
        shutil.rmtree(dashboard_csv_temp)
    if os.path.exists(dashboard_csv_path):
        os.remove(dashboard_csv_path)

    (
        dashboard_summary
        .coalesce(1)
        .write
        .mode("overwrite")
        .option("header", True)
        .csv(dashboard_csv_temp)
    )

    csv_part = next((os.path.join(dashboard_csv_temp, f) for f in os.listdir(dashboard_csv_temp) if f.startswith("part-") and f.endswith(".csv")), None)
    if not csv_part:
        raise FileNotFoundError("Dashboard CSV part file was not created.")
    shutil.move(csv_part, dashboard_csv_path)
    shutil.rmtree(dashboard_csv_temp)
    print(f"Dashboard summary CSV written: {dashboard_csv_path}")


    # ========================================================
    # 8. RETAIN STATIC GEOJSON REFERENCE
    # ========================================================

    print("\n===== 7. STATIC GEOJSON REFERENCE =====")
    geojson_src = os.path.join(DATA_DIR, "milano-grid.geojson")
    geojson_dst = os.path.join(REFERENCE_DIR, "milano-grid.geojson")

    if os.path.exists(geojson_src) and os.path.abspath(geojson_src) != os.path.abspath(geojson_dst):
        shutil.copy2(geojson_src, geojson_dst)
    print(f"Static GeoJSON reference stored at: {geojson_dst}")


    # ========================================================
    # 9. FILE SIZE COMPARISON & COLUMNAR STORAGE
    # ========================================================

    print("\n===== 8. FILE SIZE & COLUMNAR STORAGE COMPARISON =====")
    raw_csv_files = glob.glob(os.path.join(DATA_DIR, "sms-call-internet-mi-*.csv"))
    raw_csv_size = sum(os.path.getsize(f) for f in raw_csv_files)
    
    activity_parquet_size = get_directory_size(activity_output_path)
    hourly_parquet_size = get_directory_size(hourly_output_path)
    dashboard_csv_size = os.path.getsize(dashboard_csv_path)

    print(f"Total Raw CSV files size         : {format_size(raw_csv_size)}")
    print(f"Cleaned Activity Parquet size    : {format_size(activity_parquet_size)} (Partitioned)")
    print(f"Hourly Grid Summary Parquet size : {format_size(hourly_parquet_size)}")
    print(f"Dashboard Summary CSV size       : {format_size(dashboard_csv_size)}")

    if raw_csv_size > 0:
        savings = (1.0 - (activity_parquet_size / raw_csv_size)) * 100.0
        print(f"Storage Reduction via Parquet   : {savings:.2f}%")

    print("\nSP6 completed successfully.")


# ============================================================
# 4. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("SP6_Write_Processed_Analytics_Data")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.executor.memory", "4g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "10")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        run_sp6(spark)
    finally:
        spark.stop() 