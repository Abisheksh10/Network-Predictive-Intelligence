import os
import glob
from pyspark.sql import functions as F
from sp2 import run_sp2


# ============================================================
# SP3 — NETWORK ACTIVITY AGGREGATIONS
# ============================================================

def run_sp3(spark):

    # ========================================================
    # 1. RUN SP2 (LOADS ALL 7 DAILY FILES)
    # ========================================================

    clean_network_df = run_sp2(spark)

    print("\n============================================================")
    print("SP3 — NETWORK ACTIVITY AGGREGATIONS")
    print("============================================================")

    # Detect number of days/files (D) for boundary checks
    project_root = r"D:\project1"
    input_directory = os.path.join(project_root, "data")
    file_list = glob.glob(os.path.join(input_directory, "sms-call-internet-mi-*.csv"))
    num_days = len(file_list) if len(file_list) > 0 else 7

    # ========================================================
    # 2. VERIFY INPUT DATAFRAME
    # ========================================================

    input_count = clean_network_df.count()
    print("Input clean_network_df record count:", input_count)


    # ========================================================
    # 3. HAND-CHECK VERIFICATION FIXTURE
    # ========================================================

    sample_row = clean_network_df.select("timestamp", "grid_id").first()
    sample_ts = sample_row["timestamp"]
    sample_grid = sample_row["grid_id"]

    raw_sample_sum = (
        clean_network_df
        .filter((F.col("timestamp") == sample_ts) & (F.col("grid_id") == sample_grid))
        .agg(
            F.sum("sms_in").alias("sms_in"),
            F.sum("sms_out").alias("sms_out"),
            F.sum("call_in").alias("call_in"),
            F.sum("call_out").alias("call_out"),
            F.sum("internet_activity").alias("internet_activity")
        )
        .collect()[0]
    )


    # ========================================================
    # 4. COLLAPSE COUNTRY CODE GRAIN -> (timestamp, grid_id)
    # ========================================================

    grid_hour_df = (
        clean_network_df
        .groupBy(
            "timestamp",
            "grid_id"
        )
        .agg(
            F.sum("sms_in").alias("sms_in"),
            F.sum("sms_out").alias("sms_out"),
            F.sum("call_in").alias("call_in"),
            F.sum("call_out").alias("call_out"),
            F.sum("internet_activity").alias("internet_activity")
        )
    )


    # ========================================================
    # 5. DERIVE ACTIVITY KPIS & COMPOSITES
    # ========================================================

    grid_hour_df = (
        grid_hour_df
        .withColumn("total_sms", F.col("sms_in") + F.col("sms_out"))
        .withColumn("total_calls", F.col("call_in") + F.col("call_out"))
        .withColumn(
            "total_activity",
            F.col("total_sms") + F.col("total_calls") + F.col("internet_activity")
        )
        .withColumn(
            "internet_share",
            F.when(
                F.col("total_activity") > 0,
                F.col("internet_activity") / F.col("total_activity")
            ).otherwise(0.0)
        )
        .withColumn("date", F.to_date("timestamp"))
        .withColumn("hour", F.hour("timestamp"))
    )


    # ========================================================
    # 6. CREATE HOURLY GRID SUMMARY (CANONICAL DOWNSTREAM TABLE)
    # ========================================================

    hourly_grid_summary = (
        grid_hour_df
        .select(
            "timestamp",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_sms",
            "total_calls",
            "total_activity",
            "internet_share",
            "date",
            "hour"
        )
    )


    # ========================================================
    # 7. ACCEPTANCE CRITERIA VALIDATIONS
    # ========================================================

    print("\n===== GRAIN & ACCEPTANCE CRITERIA VALIDATIONS =====")

    total_hourly_records = hourly_grid_summary.count()
    distinct_grid_hour_records = hourly_grid_summary.select("timestamp", "grid_id").distinct().count()
    duplicate_count = total_hourly_records - distinct_grid_hour_records

    print("Hourly grid summary records:", total_hourly_records)
    print("Distinct (grid_id, timestamp) records:", distinct_grid_hour_records)
    print("Duplicate records:", duplicate_count)

    # Acceptance Criterion 1: Zero duplicates on (grid_id, timestamp)
    assert duplicate_count == 0, "SP3 FAILED: Duplicates found on (grid_id, timestamp)."
    print("Criterion 1 (Zero duplicates): PASS")

    # Acceptance Criterion 2: Strictly less than clean_network_df count
    assert total_hourly_records < input_count, "SP3 FAILED: hourly_grid_summary count is not strictly less than clean_network_df count."
    print("Criterion 2 (Count < clean_network_df): PASS")

    # Acceptance Criterion 3: Row count <= D x 24 x 10000
    max_allowed_records = num_days * 24 * 10000
    assert total_hourly_records <= max_allowed_records, f"SP3 FAILED: Row count exceeds upper bound {max_allowed_records}."
    print(f"Criterion 3 (Count <= {num_days}x24x10000 = {max_allowed_records}): PASS")

    # Acceptance Criterion 4: country_code removed from canonical summary
    assert "country_code" not in hourly_grid_summary.columns, "SP3 FAILED: country_code column is still present in summary."
    print("Criterion 4 (country_code omitted): PASS")

    # Acceptance Criterion 5: Hand-check validation reproduces aggregated values exactly
    aggregated_sample = (
        hourly_grid_summary
        .filter((F.col("timestamp") == sample_ts) & (F.col("grid_id") == sample_grid))
        .collect()[0]
    )
    assert round(aggregated_sample["sms_in"], 4) == round(raw_sample_sum["sms_in"], 4), "Hand-check sum mismatch on sms_in!"
    assert round(aggregated_sample["internet_activity"], 4) == round(raw_sample_sum["internet_activity"], 4), "Hand-check sum mismatch on internet_activity!"
    print(f"Criterion 5 (Hand-check grid {sample_grid} @ {sample_ts}): PASS")


    # ========================================================
    # 8. DAILY TRAFFIC SUMMARY
    # ========================================================

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


    # ========================================================
    # 9. TOP 10 HIGH-ACTIVITY GRIDS (SELECTED WINDOW)
    # ========================================================

    selected_date = "2013-11-01"
    hotspot_ranking = (
        daily_traffic_summary
        .filter(F.col("date") == selected_date)
        .select("date", "grid_id", "daily_activity")
        .orderBy(F.col("daily_activity").desc())
        .limit(10)
    )


    # ========================================================
    # 10. PEAK ACTIVITY HOUR (DIURNAL PROFILE 0-23)
    # ========================================================

    hourly_activity_profile = (
        hourly_grid_summary
        .groupBy("hour")
        .agg(F.sum("total_activity").alias("total_activity"))
    )

    peak_activity_hour = (
        hourly_activity_profile
        .orderBy(F.col("total_activity").desc())
        .limit(1)
    )


    # ========================================================
    # 11. DISPLAY OUTPUT SECTIONS
    # ========================================================

    print("\n--- SP3 Q1: Country-Code Consolidation ---")
    print("--- Hourly Grid Summary ---")
    (
        hourly_grid_summary
        .select(
            "timestamp",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "date",
            "hour"
        )
        .show(5, truncate=False)
    )

    print("\n--- SP3 Q2: Activity KPIs ---")
    print("--- Hourly Activity KPIs ---")
    (
        hourly_grid_summary
        .select(
            "timestamp",
            "grid_id",
            "total_sms",
            "total_calls",
            "internet_activity",
            "total_activity"
        )
        .show(5, truncate=False)
    )

    print("--- Daily Traffic Summary ---")
    (
        daily_traffic_summary
        .select("date", "grid_id", "daily_activity")
        .show(5, truncate=False)
    )

    print(f"\n--- SP3 Q3: Top 10 High-Activity Grids ---")
    print(f"Selected date: {selected_date}")
    hotspot_ranking.show(10, truncate=False)

    print("\n--- SP3 Q4: Peak Activity Hour ---")
    peak_activity_hour.show(truncate=False)

    print("\n--- SP3 Q5: Internet Share of Total Activity ---")
    (
        hourly_grid_summary
        .select(
            "timestamp",
            "grid_id",
            "internet_activity",
            "total_activity",
            "internet_share"
        )
        .show(10, truncate=False)
    )

    print("\nSP3 completed successfully.")


    # ========================================================
    # 12. RETURN TUPLE (INTERFACE CONTRACT FOR SP4)
    # ========================================================

    return (
        hourly_grid_summary,
        daily_traffic_summary,
        hotspot_ranking,
        peak_activity_hour
    )


# ============================================================
# STANDALONE EXECUTION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder
        .appName("SP3_Network_Activity_Aggregations")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        run_sp3(spark)
    finally:
        spark.stop()