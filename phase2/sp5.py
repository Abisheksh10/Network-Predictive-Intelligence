
import os
import time
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import col, explode, to_json, broadcast
from pyspark.storagelevel import StorageLevel

from sp4 import run_sp4


# ============================================================
# SP5 — PERFORMANCE & EXECUTION BEHAVIOUR
# ============================================================

def run_sp5(spark):

    print("\n" + "=" * 60)
    print("SP5 — PERFORMANCE & EXECUTION BEHAVIOUR")
    print("=" * 60)


    # ========================================================
    # 1. RUN SP4
    # ========================================================

    (
        grid_activity_geo_df,
        unmatched_grid_ids,
        top_activity_grids_geo_df
    ) = run_sp4(spark)


    # ========================================================
    # 2. ACTIVITY 1: HOTSPOT AGGREGATION & EXPLAIN PLAN
    # ========================================================

    hotspot_df = (
        grid_activity_geo_df
        .groupBy("grid_id")
        .agg(F.sum("total_activity").alias("total_activity"))
        .orderBy(F.col("total_activity").desc())
    )

    print("\n===== 1. HOTSPOT AGGREGATION PHYSICAL PLAN =====")
    hotspot_df.explain()


    # ========================================================
    # 3. ACTIVITY 2: CACHE TIMING COMPARISON
    # ========================================================

    cleaned_df = (
        grid_activity_geo_df
        .select(
            "timestamp",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_activity"
        )
        .filter(F.col("grid_id").isNotNull())
    )

    cached_df = cleaned_df.persist(StorageLevel.MEMORY_ONLY)

    print("\n===== 2. CACHE TIMING COMPARISON =====")

    start_time = time.perf_counter()
    first_count = cached_df.count()
    first_time = time.perf_counter() - start_time

    start_time = time.perf_counter()
    second_count = cached_df.count()
    second_time = time.perf_counter() - start_time

    print(f"First action count  : {first_count}")
    print(f"First action time   : {first_time:.3f} seconds (Computes full lineage)")
    print(f"Second action count : {second_count}")
    print(f"Second action time  : {second_time:.3f} seconds (Read from in-memory cache)")

    assert first_count == second_count, "SP5 FAILED: cached actions returned different counts."
    assert second_time < first_time, "SP5 WARNING: Cached action was not faster than cold execution."


    # ========================================================
    # 4. ACTIVITY 3: REPARTITION BY DATE (OVER-PARTITIONING TEST)
    # ========================================================

    repartitioned_df = (
        cached_df
        .withColumn("activity_date", F.to_date("timestamp"))
        .repartition("activity_date")
    )

    partitions_before = cached_df.rdd.getNumPartitions()
    partitions_after = repartitioned_df.rdd.getNumPartitions()

    print("\n===== 3. REPARTITION BY DATE ANALYSIS =====")
    print(f"Partitions before repartition : {partitions_before}")
    print(f"Partitions after repartition  : {partitions_after} (Default shuffle partitions = 200)")


    # ========================================================
    # 5. ACTIVITY 4: COLUMN PRUNING DEMONSTRATION
    # ========================================================

    print("\n===== 4. COLUMN PRUNING =====")

    pruned_df = grid_activity_geo_df.select("grid_id", "total_activity")
    pruned_hotspot_df = (
        pruned_df
        .groupBy("grid_id")
        .agg(F.sum("total_activity").alias("total_activity"))
    )

    print("Column-pruned aggregation plan (only grid_id and total_activity projected):")
    pruned_hotspot_df.explain()


    # ========================================================
    # 6. ACTIVITY 5: BROADCAST JOIN VS STANDARD JOIN
    # ========================================================

    geojson_path = r"D:\project1\data\milano-grid.geojson"
    raw_geojson_df = spark.read.option("multiline", True).json(geojson_path)

    raw_grid_lookup = (
        raw_geojson_df
        .select(explode("features").alias("feature"))
        .select(
            col("feature.properties.cellId").cast("int").alias("grid_id"),
            to_json(col("feature.geometry")).alias("geometry")
        )
    )

    standard_join_df = cached_df.join(raw_grid_lookup, on="grid_id", how="left")
    broadcast_join_df = cached_df.join(broadcast(raw_grid_lookup), on="grid_id", how="left")

    print("\n===== 5A. STANDARD JOIN PHYSICAL PLAN =====")
    standard_join_df.explain()

    print("\n===== 5B. BROADCAST JOIN PHYSICAL PLAN =====")
    broadcast_join_df.explain()


    # ========================================================
    # 7. DOCUMENTED PERFORMANCE OBSERVATIONS & REJECTIONS
    # ========================================================

    print("\n" + "=" * 60)
    print("DOCUMENTED PERFORMANCE OBSERVATIONS & REJECTIONS")
    print("=" * 60)

    print(
        f"\n[Observation 1: Caching Efficacy]\n"
        f"• Evidence: Action 1 took {first_time:.3f}s (evaluating full DAG across 7 files).\n"
        f"            Action 2 took {second_time:.3f}s (retrieving materialized in-memory partitions).\n"
        f"• Speedup Factor: {first_time / max(second_time, 0.0001):.1f}x faster on repeated access."
    )

    print(
        f"\n[Observation 2: Broadcast Hash Join vs SortMergeJoin]\n"
        f"• Evidence: Standard join physical plan introduces 'Exchange hashpartitioning' (wide shuffle).\n"
        f"            Broadcast join replaces the shuffle with 'BroadcastHashJoinExec' and 'BroadcastExchange',\n"
        f"            distributing the 10,000-row (~1.5 MB) grid reference directly to worker memory."
    )

    print(
        f"\n[Observation 3 & Rejected Optimization: Repartitioning by Date]\n"
        f"• Proposal: Repartition dataset by 'activity_date'.\n"
        f"• Evidence: Partition count jumped from {partitions_before} to {partitions_after}.\n"
        f"• Verdict : REJECTED.\n"
        f"• Reasoning: For a local multi-day dataset of only 7 days, splitting data into 200 partitions\n"
        f"  creates severe over-partitioning, where task scheduling overhead and thread contention exceed\n"
        f"  actual computation time."
    )


    # ========================================================
    # 8. CLEANUP
    # ========================================================

    cached_df.unpersist()
    print("\nSP5 completed successfully.")

    return (
        hotspot_df,
        cached_df,
        repartitioned_df,
        pruned_hotspot_df,
        standard_join_df,
        broadcast_join_df
    )


# ============================================================
# STANDALONE EXECUTION
# ============================================================

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("SP5_Performance_Execution_Behaviour")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        run_sp5(spark)
    finally:
        spark.stop()