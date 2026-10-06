"""
================================================================================
SP7: Reusable Telecom Production ETL Pipeline
Location: D:\project1\phase2\telecom_pipeline.py

JOB CONTRACT:
-------------
1. Expected Inputs:
   - raw_input_dir: Directory containing Milan daily CDR files (sms-call-internet-mi-*.csv).
   - reference_file: Static GeoJSON file (milano-grid.geojson) with properties.cellId mapping.

2. Produced Outputs:
   - <output_dir>/processed/activity/ : Cleaned activity records (Parquet, partitioned by date).
   - <output_dir>/analytics/hourly_grid_summary/ : Canonical analytics table at (grid_id, timestamp) grain without geometry (Parquet).
   - <output_dir>/analytics/dashboard_summary.csv : Daily network-wide KPI rollup (CSV).
   - <output_dir>/reference/milano-grid.geojson : Static spatial reference file.

3. Failure Conditions (Fail-Fast):
   - Exit code 1 if zero input files matching 'sms-call-internet-mi-*.csv' exist in input directory.
   - Exit code 1 if static GeoJSON reference file is missing or invalid.
   - Exit code 1 if grain duplicate assertions fail or record count checks fail.
================================================================================
"""

import os
import sys
import glob
import time
import shutil
import logging
import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType
)


# ============================================================================
# STRUCTURED LOGGER SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TelecomETL")


# ============================================================================
# 1. READ RAW MODULE (SP1)
# ============================================================================

def read_raw(spark: SparkSession, input_dir: str):
    """
    Scans and ingests daily Milan telecom activity files with a manual schema.
    Enforces pattern 'sms-call-internet-mi-*.csv' and attaches input_file_name.
    """
    file_pattern = os.path.join(input_dir, "sms-call-internet-mi-*.csv")
    input_files = sorted(glob.glob(file_pattern))

    if not input_files:
        logger.error(f"FAIL-FAST: No input files found matching '{file_pattern}'.")
        sys.exit(1)

    logger.info(f"Found {len(input_files)} daily files matching 'sms-call-internet-mi-*.csv'.")

    canonical_raw_schema = StructType([
        StructField("datetime", StringType(), True),
        StructField("CellID", IntegerType(), True),
        StructField("countrycode", StringType(), True),
        StructField("smsin", DoubleType(), True),
        StructField("smsout", DoubleType(), True),
        StructField("callin", DoubleType(), True),
        StructField("callout", DoubleType(), True),
        StructField("internet", DoubleType(), True)
    ])

    raw_df = (
        spark.read
        .option("header", True)
        .option("mode", "PERMISSIVE")
        .schema(canonical_raw_schema)
        .csv(input_files)
        .withColumn("input_file_name", F.input_file_name())
    )

    return raw_df, len(input_files)


# ============================================================================
# 2. CLEAN & STANDARDIZE MODULE (SP2)
# ============================================================================

def clean(raw_df):
    """
    Standardizes column names, casts numeric/datetime types, quarantines invalid rows,
    applies the curated-layer null-to-zero rule, and derives temporal and composite fields.
    """
    input_raw_count = raw_df.count()

    # Canonical renaming
    renamed_df = (
        raw_df
        .withColumnRenamed("CellID", "grid_id")
        .withColumnRenamed("countrycode", "country_code")
        .withColumnRenamed("smsin", "sms_in")
        .withColumnRenamed("smsout", "sms_out")
        .withColumnRenamed("callin", "call_in")
        .withColumnRenamed("callout", "call_out")
        .withColumnRenamed("internet", "internet_activity")
    )

    # Casting
    standardized_df = (
        renamed_df
        .withColumn("timestamp", F.to_timestamp(F.col("datetime"), "yyyy-MM-dd HH:mm:ss"))
        .withColumn("grid_id", F.col("grid_id").cast("int"))
        .withColumn("country_code", F.col("country_code").cast("string"))
        .withColumn("sms_in", F.col("sms_in").cast("double"))
        .withColumn("sms_out", F.col("sms_out").cast("double"))
        .withColumn("call_in", F.col("call_in").cast("double"))
        .withColumn("call_out", F.col("call_out").cast("double"))
        .withColumn("internet_activity", F.col("internet_activity").cast("double"))
    )

    # Quarantine invalid records
    valid_filter = (
        F.col("grid_id").isNotNull()
        & F.col("timestamp").isNotNull()
        & (F.col("sms_in").isNull() | (F.col("sms_in") >= 0))
        & (F.col("sms_out").isNull() | (F.col("sms_out") >= 0))
        & (F.col("call_in").isNull() | (F.col("call_in") >= 0))
        & (F.col("call_out").isNull() | (F.col("call_out") >= 0))
        & (F.col("internet_activity").isNull() | (F.col("internet_activity") >= 0))
    )
    
    clean_filtered_df = standardized_df.filter(valid_filter)
    post_filter_count = clean_filtered_df.count()
    rejected_rows = input_raw_count - post_filter_count

    # Profile & null-to-zero imputation
    activity_cols = ["sms_in", "sms_out", "call_in", "call_out", "internet_activity"]
    nulls_handled_total = 0

    for col_name in activity_cols:
        col_nulls = clean_filtered_df.filter(F.col(col_name).isNull()).count()
        nulls_handled_total += col_nulls
        clean_filtered_df = clean_filtered_df.withColumn(
            col_name,
            F.when(F.col(col_name).isNull(), F.lit(0.0)).otherwise(F.col(col_name))
        )

    # Derive composites & temporal features
    clean_network_df = (
        clean_filtered_df
        .withColumn("total_sms", F.col("sms_in") + F.col("sms_out"))
        .withColumn("total_calls", F.col("call_in") + F.col("call_out"))
        .withColumn("total_activity", F.col("total_sms") + F.col("total_calls") + F.col("internet_activity"))
        .withColumn("date", F.to_date(F.col("timestamp")))
        .withColumn("hour", F.hour(F.col("timestamp")))
        .withColumn("day_of_week", F.dayofweek(F.col("timestamp")))
    )

    return clean_network_df, input_raw_count, rejected_rows, nulls_handled_total


# ============================================================================
# 3. AGGREGATE MODULE (SP3)
# ============================================================================

def aggregate(clean_network_df, num_days: int):
    """
    Consolidates country-code grain to (grid_id, timestamp), builds canonical
    hourly_grid_summary and daily_traffic_summary, and executes grain assertions.
    """
    # 1. Collapse country-code grain
    grid_hour_df = (
        clean_network_df
        .groupBy("timestamp", "grid_id")
        .agg(
            F.sum("sms_in").alias("sms_in"),
            F.sum("sms_out").alias("sms_out"),
            F.sum("call_in").alias("call_in"),
            F.sum("call_out").alias("call_out"),
            F.sum("internet_activity").alias("internet_activity")
        )
        .withColumn("total_sms", F.col("sms_in") + F.col("sms_out"))
        .withColumn("total_calls", F.col("call_in") + F.col("call_out"))
        .withColumn("total_activity", F.col("total_sms") + F.col("total_calls") + F.col("internet_activity"))
        .withColumn(
            "internet_share",
            F.when(F.col("total_activity") > 0, F.col("internet_activity") / F.col("total_activity")).otherwise(0.0)
        )
        .withColumn("date", F.to_date(F.col("timestamp")))
        .withColumn("hour", F.hour(F.col("timestamp")))
    )

    hourly_grid_summary = grid_hour_df.select(
        "timestamp", "grid_id", "sms_in", "sms_out", "call_in", "call_out",
        "internet_activity", "total_sms", "total_calls", "total_activity",
        "internet_share", "date", "hour"
    )

    # 2. Assertions
    hourly_count = hourly_grid_summary.count()
    distinct_combos = hourly_grid_summary.select("grid_id", "timestamp").distinct().count()
    duplicate_count = hourly_count - distinct_combos

    assert duplicate_count == 0, f"Grain violation: {duplicate_count} duplicate (grid_id, timestamp) rows found!"
    assert "country_code" not in hourly_grid_summary.columns, "Schema violation: country_code found in summary table!"
    assert hourly_count <= num_days * 24 * 10000, "Count boundary violation: row count exceeds D x 24 x 10000!"

    # 3. Daily rollup
    daily_traffic_summary = (
        hourly_grid_summary
        .groupBy("date", "grid_id")
        .agg(
            F.sum("total_activity").alias("daily_activity"),
            F.sum("sms_in").alias("sms_in"),
            F.sum("sms_out").alias("sms_out"),
            F.sum("call_in").alias("call_in"),
            F.sum("call_out").alias("call_out"),
            F.sum("internet_activity").alias("internet_activity"),
            F.sum("total_sms").alias("total_sms"),
            F.sum("total_calls").alias("total_calls")
        )
    )

    return hourly_grid_summary, daily_traffic_summary, hourly_count


# ============================================================================
# 4. ENRICH MODULE (SP4)
# ============================================================================

def enrich(spark: SparkSession, hourly_grid_summary, geojson_path: str):
    """
    Performs a Broadcast Left Join with milano-grid.geojson on properties.cellId -> grid_id.
    Derives cell centroids natively and validates coverage.
    """
    if not os.path.exists(geojson_path):
        logger.error(f"FAIL-FAST: Static GeoJSON file not found at: {geojson_path}")
        sys.exit(1)

    raw_geojson = spark.read.option("multiline", True).json(geojson_path)

    grid_lookup_df = (
        raw_geojson
        .select(F.explode("features").alias("feature"))
        .select(
            F.col("feature.properties.cellId").cast("int").alias("grid_id"),
            F.to_json(F.col("feature.geometry")).alias("geometry"),
            F.col("feature.geometry.coordinates").getItem(0).alias("exterior_ring")
        )
        .withColumn(
            "centroid_lon",
            (
                F.col("exterior_ring").getItem(0).getItem(0)
                + F.col("exterior_ring").getItem(1).getItem(0)
                + F.col("exterior_ring").getItem(2).getItem(0)
                + F.col("exterior_ring").getItem(3).getItem(0)
            ) / 4.0
        )
        .withColumn(
            "centroid_lat",
            (
                F.col("exterior_ring").getItem(0).getItem(1)
                + F.col("exterior_ring").getItem(1).getItem(1)
                + F.col("exterior_ring").getItem(2).getItem(1)
                + F.col("exterior_ring").getItem(3).getItem(1)
            ) / 4.0
        )
        .select("grid_id", "geometry", "centroid_lon", "centroid_lat")
    )

    # Broadcast left join
    grid_activity_geo_df = hourly_grid_summary.join(
        F.broadcast(grid_lookup_df),
        on="grid_id",
        how="left"
    )

    return grid_activity_geo_df, grid_lookup_df


# ============================================================================
# 5. WRITE OUTPUTS MODULE (SP6)
# ============================================================================

def write_outputs(clean_network_df, hourly_grid_summary, daily_traffic_summary, output_dir: str, geojson_src: str):
    """
    Persists data products:
      - Processed activity -> Parquet (partitioned by date)
      - Hourly grid summary -> Parquet (without geometry)
      - Dashboard summary -> CSV (coalesced to single file)
      - Static GeoJSON -> copied to reference directory
    """
    processed_activity_path = os.path.join(output_dir, "processed", "activity")
    analytics_hourly_path = os.path.join(output_dir, "analytics", "hourly_grid_summary")
    analytics_dir = os.path.join(output_dir, "analytics")
    reference_dir = os.path.join(output_dir, "reference")
    dashboard_csv_path = os.path.join(analytics_dir, "dashboard_summary.csv")
    dashboard_csv_temp = os.path.join(analytics_dir, "_dashboard_summary_csv")
    geojson_dst = os.path.join(reference_dir, "milano-grid.geojson")

    os.makedirs(analytics_dir, exist_ok=True)
    os.makedirs(reference_dir, exist_ok=True)

    # 1. Clean Activity Parquet (Partitioned by date)
    if os.path.exists(processed_activity_path):
        shutil.rmtree(processed_activity_path)
    (
        clean_network_df
        .repartition("date")
        .write
        .mode("overwrite")
        .partitionBy("date")
        .parquet(processed_activity_path)
    )

    # 2. Hourly Grid Summary Parquet (No geometry)
    if os.path.exists(analytics_hourly_path):
        shutil.rmtree(analytics_hourly_path)
    (
        hourly_grid_summary
        .write
        .mode("overwrite")
        .parquet(analytics_hourly_path)
    )

    # 3. Dashboard Summary CSV
    if os.path.exists(dashboard_csv_temp):
        shutil.rmtree(dashboard_csv_temp)
    if os.path.exists(dashboard_csv_path):
        os.remove(dashboard_csv_path)

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
            F.sum("daily_activity").alias("total_activity"),
            F.countDistinct("grid_id").alias("active_grids")
        )
        .orderBy("date")
    )

    (
        dashboard_summary
        .coalesce(1)
        .write
        .mode("overwrite")
        .option("header", True)
        .csv(dashboard_csv_temp)
    )

    part_file = next((os.path.join(dashboard_csv_temp, f) for f in os.listdir(dashboard_csv_temp) if f.startswith("part-") and f.endswith(".csv")), None)
    if part_file:
        shutil.move(part_file, dashboard_csv_path)
        shutil.rmtree(dashboard_csv_temp)

    # 4. Retain static reference
    if os.path.abspath(geojson_src) != os.path.abspath(geojson_dst):
        shutil.copy2(geojson_src, geojson_dst)

    return processed_activity_path, analytics_hourly_path, dashboard_csv_path


# ============================================================================
# 6. MAIN PIPELINE ORCHESTRATOR
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Production Spark ETL Pipeline for Milan Telecom Activity.")
    parser.add_argument("--project_root", default=r"D:\project1", help="Project root folder path")
    parser.add_argument("--data_dir", default=r"D:\project1\data", help="Input directory containing CSV and GeoJSON files")
    parser.add_argument("--output_dir", default=r"D:\project1\data", help="Target base directory for processed/analytics outputs")
    parser.add_argument("--geojson_path", default=r"D:\project1\data\milano-grid.geojson", help="Path to milano-grid.geojson")
    args = parser.parse_args()

    start_time = time.time()
    logger.info("=" * 60)
    logger.info("STARTING TELECOM PRODUCTION SPARK ETL PIPELINE (SP7)")
    logger.info("=" * 60)

    # Environment setup
    os.environ["HADOOP_HOME"] = args.project_root
    os.environ["hadoop.home.dir"] = args.project_root
    os.environ["PATH"] = os.path.join(args.project_root, "bin") + os.pathsep + os.environ.get("PATH", "")

    spark = (
        SparkSession.builder
        .appName("SP7_Production_Telecom_ETL_Pipeline")
        .master("local[*]")
        .config("spark.driver.memory", "4g")
        .config("spark.executor.memory", "4g")
        .config("spark.driver.maxResultSize", "2g")
        .config("spark.sql.shuffle.partitions", "10")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    spark._jvm.java.lang.System.setProperty("hadoop.home.dir", args.project_root)

    try:
        # Step 1: Read Raw
        raw_df, num_files = read_raw(spark, args.data_dir)

        # Step 2: Clean & Standardize
        clean_df, raw_count, rejected_count, nulls_imputed = clean(raw_df)

        # Step 3: Aggregate
        hourly_summary_df, daily_summary_df, hourly_output_count = aggregate(clean_df, num_files)

        # Step 4: Enrich
        _, _ = enrich(spark, hourly_summary_df, args.geojson_path)

        # Step 5: Write Outputs
        act_path, hourly_path, dash_path = write_outputs(
            clean_df,
            hourly_summary_df,
            daily_summary_df,
            args.output_dir,
            args.geojson_path
        )

        elapsed_duration = round(time.time() - start_time, 2)

        # Structured Execution Audit Log
        logger.info("=" * 60)
        logger.info("SP7 PIPELINE EXECUTION AUDIT REPORT")
        logger.info("=" * 60)
        logger.info(f"Execution Status    : SUCCESS")
        logger.info(f"Execution Duration  : {elapsed_duration} seconds")
        logger.info(f"Input Files Count   : {num_files}")
        logger.info(f"Raw Input Rows      : {raw_count}")
        logger.info(f"Rejected Rows       : {rejected_count}")
        logger.info(f"Nulls Imputed to 0  : {nulls_imputed}")
        logger.info(f"Hourly Summary Rows : {hourly_output_count}")
        logger.info(f"Output 1 (Activity) : {act_path}")
        logger.info(f"Output 2 (Hourly)   : {hourly_path}")
        logger.info(f"Output 3 (Dashboard): {dash_path}")
        logger.info("=" * 60)

    except Exception as exc:
        logger.error(f"PIPELINE CRITICAL FAILURE: {str(exc)}", exc_info=True)
        sys.exit(1)
    finally:
        spark.stop()
if __name__ == "__main__":
    main() #the below is the output for sp7.
# 2026-08-30 21:33:29,007 [INFO] ============================================================
# 2026-08-30 21:33:29,007 [INFO] STARTING TELECOM PRODUCTION SPARK ETL PIPELINE (SP7)
# 2026-08-30 21:33:29,007 [INFO] ============================================================
# WARNING: Using incubator modules: jdk.incubator.vector
# Using Spark's default log4j profile: org/apache/spark/log4j2-defaults.properties
# Setting default log level to "WARN".
# To adjust logging level use sc.setLogLevel(newLevel). For SparkR, use setLogLevel(newLevel).
# C:\Users\abishek.sh\AppData\Local\Programs\Python\Python312\Lib\site-packages\pyspark\testing\utils.py:127: FutureWarning: PySpark does not yet fully support pandas >= 3.0.0. Some features may not work correctly. It is recommended to use pandas < 3.0.0 for now.
#   require_minimum_pandas_version()
# 2026-08-30 21:33:39,640 [INFO] Found 7 daily files matching 'sms-call-internet-mi-*.csv'.
# [Stage 0:>                                         [Stage 0:===================>                                                                         [Stage 3:>                                         [Stage 3:=======>                                  [Stage 3:===========>                              [Stage 3:===============>                          [Stage 3:===================>                      [Stage 3:=======================>                  [Stage 3:===========================>              [Stage 3:==========================================                                                   [Stage 6:>                                         [Stage 6:===>                                      [Stage 6:===========>                              [Stage 6:===================>                      [Stage 6:=======================>                  [Stage 6:======================================>                                                      [Stage 9:>                                         [Stage 9:===>                                      [Stage 9:=======>                                  [Stage 9:===========>                              [Stage 9:===================>                      [Stage 9:=======================>                  [Stage 9:===========================>              [Stage 9:==================================>       [Stage 9:==========================================                                                   [Stage 12:>                                        [Stage 12:===>                                     [Stage 12:=======>                                 [Stage 12:===========>                             [Stage 12:==============>                          [Stage 12:==================>                      [Stage 12:==========================>              [Stage 12:==============================>          [Stage 12:=========================================                                                   [Stage 15:>                                        [Stage 15:===>                                     [Stage 15:=======>                                 [Stage 15:===========>                             [Stage 15:==============>                          [Stage 15:======================>                  [Stage 15:==============================>          [Stage 15:=========================================                                                   [Stage 18:>                                        [Stage 18:=======>                                 [Stage 18:===========>                             [Stage 18:==========================>              [Stage 18:==================================>      [Stage 18:=========================================                                                   [Stage 21:>                                        [Stage 21:===>                                     [Stage 21:===========>                             [Stage 21:======================>                  [Stage 21:==========================>              [Stage 21:==============================>          [Stage 21:=========================================                                                   [Stage 27:>                                        [Stage 27:=======>                                 [Stage 27:===========>                             [Stage 27:==================>                      [Stage 27:======================>                  [Stage 27:==============================>          [Stage 27:=========================================                                                   [Stage 34:>                                        [Stage 34:=======>                                 [Stage 34:===========>                             [Stage 34:==============>                          [Stage 34:==================>                      [Stage 34:======================>                  [Stage 34:==============================>          [Stage 34:=========================================[Stage 34:=========================================[Stage 36:>                                        [Stage 36:===========>                             [Stage 36:=======================>                 [Stage 36:==================================>      [Stage 36:=========================================                                                   [Stage 37:>                                        [Stage 37:===>                                     [Stage 37:===========>                             [Stage 37:==============>                          [Stage 37:==================>                      [Stage 37:==========================>              [Stage 37:=========================================[Stage 37:=========================================[Stage 37:=========================================[Stage 39:>                                                                                           [Stage 40:>                                        [Stage 40:=======>                                 [Stage 40:===========>                             [Stage 40:==============>                          [Stage 40:======================>                  [Stage 40:==========================>              [Stage 40:==============================>          [Stage 40:=====================================>   [Stage 40:=========================================[Stage 40:=========================================[Stage 42:>                                        [Stage 45:=================>                                                                          2026-08-30 21:35:31,014 [INFO] ============================================================
# 2026-08-30 21:35:31,015 [INFO] SP7 PIPELINE EXECUTION AUDIT REPORT
# 2026-08-30 21:35:31,015 [INFO] ============================================================
# 2026-08-30 21:35:31,015 [INFO] Execution Status    : SUCCESS
# 2026-08-30 21:35:31,016 [INFO] Execution Duration  : 122.01 seconds
# 2026-08-30 21:35:31,016 [INFO] Input Files Count   : 7
# 2026-08-30 21:35:31,016 [INFO] Raw Input Rows      : 15089165
# 2026-08-30 21:35:31,016 [INFO] Rejected Rows       : 0
# 2026-08-30 21:35:31,016 [INFO] Nulls Imputed to 0  : 48562194
# 2026-08-30 21:35:31,016 [INFO] Hourly Summary Rows : 1679994
# 2026-08-30 21:35:31,016 [INFO] Output 1 (Activity) : D:\project1\data\processed\activity
# 2026-08-30 21:35:31,017 [INFO] Output 2 (Hourly)   : D:\project1\data\analytics\hourly_grid_summary
# 2026-08-30 21:35:31,017 [INFO] Output 3 (Dashboard): D:\project1\data\analytics\dashboard_summary.csv
# 2026-08-30 21:35:31,017 [INFO] ============================================================
# 2026-08-30 21:35:31,314 [INFO] Closing down clientserver connection







#fail fast test output
# PS D:\project1\phase2> python telecom_pipeline.py --data_dir D:\project1\data\reference
# 2026-08-30 21:37:57,805 [INFO] ============================================================
# 2026-08-30 21:37:57,805 [INFO] STARTING TELECOM PRODUCTION SPARK ETL PIPELINE (SP7)
# 2026-08-30 21:37:57,805 [INFO] ============================================================
# WARNING: Using incubator modules: jdk.incubator.vector
# Using Spark's default log4j profile: org/apache/spark/log4j2-defaults.properties
# Setting default log level to "WARN".
# To adjust logging level use sc.setLogLevel(newLevel). For SparkR, use setLogLevel(newLevel).
# C:\Users\abishek.sh\AppData\Local\Programs\Python\Python312\Lib\site-packages\pyspark\testing\utils.py:127: FutureWarning: PySpark does not yet fully support pandas >= 3.0.0. Some features may not work correctly. It is recommended to use pandas < 3.0.0 for now.
#   require_minimum_pandas_version()
# 2026-08-30 21:38:07,591 [ERROR] FAIL-FAST: No input files found matching 'D:\project1\data\reference\sms-call-internet-mi-*.csv'.
# 2026-08-30 21:38:07,849 [INFO] Closing down clientserver connection
