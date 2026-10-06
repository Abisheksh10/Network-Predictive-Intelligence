import os
import glob
import pandas as pd
import numpy as np

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType
)
from pyspark.sql.functions import (
    col,
    to_timestamp,
    when,
    lit,
    to_date,
    hour,
    dayofweek,
    min,
    max,
    input_file_name,
    date_trunc
)


# ============================================================
# HELPER: PANDAS VS SPARK COMPARISON TEST
# ============================================================

def run_pandas_vs_spark_comparison(spark, sample_file_path):
    print("\n============================================================")
    print("RUNNING PANDAS VS SPARK COMPARISON TEST (SINGLE DAY)")
    print("Sample file:", os.path.basename(sample_file_path))
    print("============================================================")

    # ----------------- 1. Pandas Implementation -----------------
    pdf = pd.read_csv(sample_file_path)
    
    # Rename
    pdf = pdf.rename(columns={
        "datetime": "timestamp",
        "CellID": "grid_id",
        "countrycode": "country_code",
        "smsin": "sms_in",
        "smsout": "sms_out",
        "callin": "call_in",
        "callout": "call_out",
        "internet": "internet_activity"
    })
    
    # Cast types
    pdf["timestamp"] = pd.to_datetime(pdf["timestamp"])
    pdf["grid_id"] = pdf["grid_id"].astype("Int64")
    pdf["country_code"] = pdf["country_code"].astype(str)
    
    activity_cols = ["sms_in", "sms_out", "call_in", "call_out", "internet_activity"]
    for c in activity_cols:
        pdf[c] = pd.to_numeric(pdf[c], errors="coerce")

    # Quarantine / Filter
    valid_mask = pdf["grid_id"].notna() & pdf["timestamp"].notna()
    for c in activity_cols:
        valid_mask = valid_mask & ((pdf[c].isna()) | (pdf[c] >= 0))
    pdf_clean = pdf[valid_mask].copy()

    # Null to zero
    pdf_clean[activity_cols] = pdf_clean[activity_cols].fillna(0.0)

    # Composites
    pdf_clean["total_sms"] = pdf_clean["sms_in"] + pdf_clean["sms_out"]
    pdf_clean["total_calls"] = pdf_clean["call_in"] + pdf_clean["call_out"]
    pdf_clean["total_activity"] = (
        pdf_clean["total_sms"] + pdf_clean["total_calls"] + pdf_clean["internet_activity"]
    )

    # ----------------- 2. Spark Implementation -----------------
    sdf = (
        spark.read
        .option("header", True)
        .csv(sample_file_path)
    )

    sdf = (
        sdf
        .withColumnRenamed("CellID", "grid_id")
        .withColumnRenamed("countrycode", "country_code")
        .withColumnRenamed("smsin", "sms_in")
        .withColumnRenamed("smsout", "sms_out")
        .withColumnRenamed("callin", "call_in")
        .withColumnRenamed("callout", "call_out")
        .withColumnRenamed("internet", "internet_activity")
    )

    sdf = (
        sdf
        .withColumn("timestamp", to_timestamp(col("datetime"), "yyyy-MM-dd HH:mm:ss"))
        .withColumn("grid_id", col("grid_id").cast("int"))
        .withColumn("country_code", col("country_code").cast("string"))
        .withColumn("sms_in", col("sms_in").cast("double"))
        .withColumn("sms_out", col("sms_out").cast("double"))
        .withColumn("call_in", col("call_in").cast("double"))
        .withColumn("call_out", col("call_out").cast("double"))
        .withColumn("internet_activity", col("internet_activity").cast("double"))
    )

    sdf_clean = sdf.filter(
        col("grid_id").isNotNull()
        & col("timestamp").isNotNull()
        & (col("sms_in").isNull() | (col("sms_in") >= 0))
        & (col("sms_out").isNull() | (col("sms_out") >= 0))
        & (col("call_in").isNull() | (col("call_in") >= 0))
        & (col("call_out").isNull() | (col("call_out") >= 0))
        & (col("internet_activity").isNull() | (col("internet_activity") >= 0))
    )

    for c in activity_cols:
        sdf_clean = sdf_clean.withColumn(
            c,
            when(col(c).isNull(), lit(0.0)).otherwise(col(c))
        )

    sdf_clean = (
        sdf_clean
        .withColumn("total_sms", col("sms_in") + col("sms_out"))
        .withColumn("total_calls", col("call_in") + col("call_out"))
        .withColumn("total_activity", col("total_sms") + col("total_calls") + col("internet_activity"))
    )

    # ----------------- 3. Assertions & Validation -----------------
    pandas_row_count = len(pdf_clean)
    spark_row_count = sdf_clean.count()

    pandas_total_activity = round(float(pdf_clean["total_activity"].sum()), 4)
    spark_total_activity = round(float(sdf_clean.selectExpr("sum(total_activity)").collect()[0][0]), 4)

    print(f"Pandas clean rows : {pandas_row_count}")
    print(f"Spark clean rows  : {spark_row_count}")
    print(f"Pandas total sum  : {pandas_total_activity}")
    print(f"Spark total sum   : {spark_total_activity}")

    assert pandas_row_count == spark_row_count, "Row count mismatch between Pandas and Spark!"
    assert np.isclose(pandas_total_activity, spark_total_activity, rtol=1e-4), "Total activity metric mismatch!"

    print("Result: Single-Day Pandas vs. Spark Comparison PASSED.")


# ============================================================
# MAIN SP2 PIPELINE
# ============================================================

def run_sp2(spark):

    # ============================================================
    # 1. INPUT FILES & HADOOP ENVIRONMENT
    # ============================================================

    project_root = r"D:\project1"
    input_directory = os.path.join(project_root, "data")

    # Set up Hadoop / WinUtils environment
    os.environ["HADOOP_HOME"] = project_root
    os.environ["PATH"] = os.path.join(project_root, "bin") + os.pathsep + os.environ.get("PATH", "")

    input_files = sorted(
        glob.glob(
            os.path.join(
                input_directory,
                "sms-call-internet-mi-*.csv"
            )
        )
    )

    print("Number of input files:", len(input_files))
    if len(input_files) == 0:
        raise FileNotFoundError(f"No files matching pattern found in {input_directory}")


    # ============================================================
    # 2. RUN PANDAS VS SPARK PARITY TEST ON 1 FILE
    # ============================================================

    run_pandas_vs_spark_comparison(spark, input_files[0])


    # ============================================================
    # 3. MANUAL SCHEMA DEFINITION
    # ============================================================

    manual_schema = StructType([
        StructField("datetime", StringType(), True),
        StructField("CellID", IntegerType(), True),
        StructField("countrycode", StringType(), True),
        StructField("smsin", DoubleType(), True),
        StructField("smsout", DoubleType(), True),
        StructField("callin", DoubleType(), True),
        StructField("callout", DoubleType(), True),
        StructField("internet", DoubleType(), True)
    ])


    # ============================================================
    # 4. READ ALL DAILY FILES
    # ============================================================

    raw_source_df = (
        spark.read
        .option("header", True)
        .option("mode", "PERMISSIVE")
        .schema(manual_schema)
        .csv(input_files)
    )

    # Attach source file name for traceability
    raw_source_df = raw_source_df.withColumn("input_file_name", input_file_name())


    # ============================================================
    # 5. RECORD COUNT BEFORE CLEANING
    # ============================================================

    before_count = raw_source_df.count()

    print("\n===== BEFORE CLEANING =====")
    print("Raw record count:", before_count)


    # ============================================================
    # 6. RENAME RAW COLUMNS
    # ============================================================

    clean_network_df = (
        raw_source_df
        .withColumnRenamed("CellID", "grid_id")
        .withColumnRenamed("countrycode", "country_code")
        .withColumnRenamed("smsin", "sms_in")
        .withColumnRenamed("smsout", "sms_out")
        .withColumnRenamed("callin", "call_in")
        .withColumnRenamed("callout", "call_out")
        .withColumnRenamed("internet", "internet_activity")
    )


    # ============================================================
    # 7. CAST timestamp AND ACTIVITY MEASURES
    # ============================================================

    clean_network_df = (
        clean_network_df
        .withColumn(
            "timestamp",
            to_timestamp(
                col("datetime"),
                "yyyy-MM-dd HH:mm:ss"
            )
        )
        .withColumn("grid_id", col("grid_id").cast("int"))
        .withColumn("country_code", col("country_code").cast("string"))
        .withColumn("sms_in", col("sms_in").cast("double"))
        .withColumn("sms_out", col("sms_out").cast("double"))
        .withColumn("call_in", col("call_in").cast("double"))
        .withColumn("call_out", col("call_out").cast("double"))
        .withColumn(
            "internet_activity",
            col("internet_activity").cast("double")
        )
    )


    # ============================================================
    # 8. RAW HOURLY CADENCE VALIDATION
    # ============================================================

    print("\n===== PRE-CLEAN HOURLY CADENCE VALIDATION =====")

    pre_clean_distinct_hours = (
        clean_network_df
        .select(date_trunc("hour", col("timestamp")).alias("hourly_interval"))
        .distinct()
        .count()
    )

    expected_hours = len(input_files) * 24

    print("Distinct hourly intervals (pre-clean):", pre_clean_distinct_hours)
    print("Expected hourly intervals:", expected_hours)

    timestamp_range = clean_network_df.select(
        min("timestamp").alias("min_timestamp"),
        max("timestamp").alias("max_timestamp")
    ).collect()[0]

    print("Minimum timestamp:", timestamp_range["min_timestamp"])
    print("Maximum timestamp:", timestamp_range["max_timestamp"])

    if pre_clean_distinct_hours == expected_hours:
        print("Pre-clean cadence validation: PASS")
    else:
        print("Pre-clean cadence validation: FAIL")


    # ============================================================
    # 9. NULL PROFILE
    # ============================================================

    print("\n===== ACTIVITY NULL PROFILE =====")

    activity_columns = [
        "sms_in",
        "sms_out",
        "call_in",
        "call_out",
        "internet_activity"
    ]

    for column_name in activity_columns:
        null_count = (
            clean_network_df
            .filter(col(column_name).isNull())
            .count()
        )
        print(column_name, "nulls:", null_count)


    # ============================================================
    # 10. REJECTED RECORDS IDENTIFICATION & BREAKDOWN
    # ============================================================

    rejected_df = clean_network_df.filter(
        col("grid_id").isNull()
        | col("timestamp").isNull()
        | (col("sms_in") < 0)
        | (col("sms_out") < 0)
        | (col("call_in") < 0)
        | (col("call_out") < 0)
        | (col("internet_activity") < 0)
    )

    rejected_count = rejected_df.count()

    print("\n===== REJECTED RECORD SUMMARY =====")
    print("Total rejected records:", rejected_count)

    missing_grid_count = clean_network_df.filter(col("grid_id").isNull()).count()
    missing_timestamp_count = clean_network_df.filter(col("timestamp").isNull()).count()
    negative_activity_count = clean_network_df.filter(
        (col("sms_in") < 0)
        | (col("sms_out") < 0)
        | (col("call_in") < 0)
        | (col("call_out") < 0)
        | (col("internet_activity") < 0)
    ).count()

    print("Missing grid_id:", missing_grid_count)
    print("Missing timestamp:", missing_timestamp_count)
    print("Rows containing negative activity:", negative_activity_count)


    # ============================================================
    # 11. FILTER VALID RECORDS (QUARANTINE)
    # ============================================================

    clean_network_df = clean_network_df.filter(
        col("grid_id").isNotNull()
        & col("timestamp").isNotNull()
        & (col("sms_in").isNull() | (col("sms_in") >= 0))
        & (col("sms_out").isNull() | (col("sms_out") >= 0))
        & (col("call_in").isNull() | (col("call_in") >= 0))
        & (col("call_out").isNull() | (col("call_out") >= 0))
        & (col("internet_activity").isNull() | (col("internet_activity") >= 0))
    )


    # ============================================================
    # 12. NULL → ZERO HANDLING (CURATED LAYER ONLY)
    # ============================================================

    print("\n===== NULL-TO-ZERO HANDLING =====")

    null_handled_counts = {}

    for column_name in activity_columns:
        null_count = clean_network_df.filter(col(column_name).isNull()).count()
        null_handled_counts[column_name] = null_count

        clean_network_df = clean_network_df.withColumn(
            column_name,
            when(col(column_name).isNull(), lit(0.0)).otherwise(col(column_name))
        )
        #lit is used to create a spark literal value representing the float 0.0. spark requires lit() to treat plain python constants as column-compatible values.

        print(column_name, "nulls converted to zero:", null_count)

    total_nulls_handled = sum(null_handled_counts.values())
    print("Total activity nulls handled:", total_nulls_handled)


    # ============================================================
    # 13. DERIVE COMPOSITES & TIME COLUMNS
    # ============================================================

    # Composites
    clean_network_df = clean_network_df.withColumn("total_sms", col("sms_in") + col("sms_out"))
    clean_network_df = clean_network_df.withColumn("total_calls", col("call_in") + col("call_out"))
    clean_network_df = clean_network_df.withColumn(
        "total_activity",
        col("total_sms") + col("total_calls") + col("internet_activity")
    )

    # Derived temporal columns
    clean_network_df = clean_network_df.withColumn("date", to_date(col("timestamp")))
    clean_network_df = clean_network_df.withColumn("hour", hour(col("timestamp")))
    clean_network_df = clean_network_df.withColumn("day_of_week", dayofweek(col("timestamp")))


    # ============================================================
    # 14. POST-CLEANING HOURLY CADENCE VALIDATION (CRITERIA: D x 24)
    # ============================================================

    print("\n===== POST-CLEAN HOURLY CADENCE VALIDATION =====")

    post_clean_distinct_hours = (
        clean_network_df
        .select(date_trunc("hour", col("timestamp")).alias("hourly_interval"))
        .distinct()
        .count()
    )

    print("Post-clean distinct hourly intervals:", post_clean_distinct_hours)
    print("Expected hourly intervals:", expected_hours)

    if post_clean_distinct_hours == expected_hours:
        print("Post-clean hourly cadence validation: PASS")
    else:
        print("Post-clean hourly cadence validation: FAIL")


    # ============================================================
    # 15. RECORD COUNT COMPARISON & AUDIT
    # ============================================================

    after_count = clean_network_df.count()

    print("\n===== RECORD COUNT COMPARISON =====")
    print("Before cleaning:", before_count)
    print("After cleaning:", after_count)
    print("Rejected:", rejected_count)

    if before_count - rejected_count == after_count:
        print("Record count balance validation: PASS")
    else:
        print("Record count balance validation: FAIL")


    # ============================================================
    # 16. SCHEMA & SAMPLE DISPLAY
    # ============================================================

    print("\n===== CLEAN NETWORK DATAFRAME SCHEMA =====")
    clean_network_df.printSchema()

    print("\n===== SAMPLE CLEAN DATA =====")
    clean_network_df.show(10, truncate=False)


    # ============================================================
    # 17. FINAL SUMMARY
    # ============================================================

    print("\n===== SP2 SUMMARY =====")
    print("Input files:", len(input_files))
    print("Records before cleaning:", before_count)
    print("Records rejected:", rejected_count)
    print("Records after cleaning:", after_count)
    print("Activity nulls converted to zero:", total_nulls_handled)
    print("Distinct timestamp intervals preserved:", post_clean_distinct_hours)
    print("\nSP2 completed successfully.")

    return clean_network_df


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    spark = (
        SparkSession.builder
        .appName("SP2_Cleaning_Standardization")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        clean_network_df = run_sp2(spark)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()