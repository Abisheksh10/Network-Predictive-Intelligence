import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import (
    col,
    explode,
    to_json,
    broadcast
)

from sp3 import run_sp3


# ============================================================
# SP4 — GEOSPATIAL ENRICHMENT USING THE MILAN GRID
# ============================================================

def run_sp4(spark):

    # ========================================================
    # 1. RUN SP3 (AGGREGATED HOURLY GRID ACTIVITY)
    # ========================================================

    (
        hourly_grid_summary,
        daily_traffic_summary,
        hotspot_ranking,
        peak_activity_hour
    ) = run_sp3(spark)

    print("\n" + "=" * 60)
    print("SP4 — GEOSPATIAL ENRICHMENT USING THE MILAN GRID")
    print("=" * 60)


    # ========================================================
    # 2. INPUT RECORD AUDIT
    # ========================================================

    activity_record_count = hourly_grid_summary.count()
    activity_grid_count = hourly_grid_summary.select("grid_id").distinct().count()

    print("Input activity records:", activity_record_count)
    print("Distinct activity grids:", activity_grid_count)


    # ========================================================
    # 3. LOAD & FLATTEN MILANO-GRID GEOJSON
    # ========================================================

    geojson_path = r"D:\project1\data\milano-grid.geojson"

    geojson_df = (
        spark.read
        .option("multiline", True)
        .option("mode", "PERMISSIVE")
        .json(geojson_path)
    )

    # Flatten features: extract properties.cellId -> grid_id, geometry, coordinates
    features_df = (
        geojson_df
        .select(explode("features").alias("feature"))
        .select(
            col("feature.properties.cellId").cast("int").alias("grid_id"),
            to_json(col("feature.geometry")).alias("geometry"),
            col("feature.geometry.type").alias("geometry_type"),
            col("feature.geometry.coordinates").getItem(0).alias("exterior_ring")
        )
    )

    # Compute centroid using native Spark SQL array indexing across the 4 unique box corners
    # (Avoids Python UDF worker socket timeouts on Windows)
    grid_lookup_df = (
        features_df
        .withColumn(
            "centroid_lon",
            (
                col("exterior_ring").getItem(0).getItem(0)
                + col("exterior_ring").getItem(1).getItem(0)
                + col("exterior_ring").getItem(2).getItem(0)
                + col("exterior_ring").getItem(3).getItem(0)
            ) / 4.0
        )
        .withColumn(
            "centroid_lat",
            (
                col("exterior_ring").getItem(0).getItem(1)
                + col("exterior_ring").getItem(1).getItem(1)
                + col("exterior_ring").getItem(2).getItem(1)
                + col("exterior_ring").getItem(3).getItem(1)
            ) / 4.0
        )
        .select("grid_id", "geometry", "geometry_type", "centroid_lon", "centroid_lat")
    )


    # ========================================================
    # 4. GEOJSON REFERENCE LOOKUP VALIDATION
    # ========================================================

    grid_lookup_count = grid_lookup_df.count()
    lookup_distinct_count = grid_lookup_df.select("grid_id").distinct().count()
    duplicate_grid_count = grid_lookup_count - lookup_distinct_count

    print("GeoJSON grid reference records:", grid_lookup_count)
    print("Duplicate grid IDs in lookup:", duplicate_grid_count)

    assert duplicate_grid_count == 0, "SP4 FAILED: Duplicate grid_id values exist in GeoJSON lookup."
    assert grid_lookup_count == 10000, f"SP4 FAILED: Expected 10000 Milan cells, found {grid_lookup_count}."
    print("Reference lookup validation: PASS")


    # ========================================================
    # 5. GEOMETRY TYPE VALIDATION
    # ========================================================

    polygon_count = grid_lookup_df.filter(col("geometry_type") == "Polygon").count()
    non_polygon_count = grid_lookup_df.filter(col("geometry_type") != "Polygon").count()

    print(f"Polygon geometries: {polygon_count}")
    print(f"Non-polygon geometries: {non_polygon_count}")

    assert non_polygon_count == 0, "SP4 FAILED: non-polygon geometries found."
    print("Geometry validation: PASS")


    # ========================================================
    # 6. GEOGRAPHIC SPOT-CHECK & ADJACENCY VALIDATION
    # ========================================================

    print("\n--- Geographic Spot-Check (Centroid Inspection) ---")

    test_cells = (
        grid_lookup_df
        .filter(col("grid_id").isin(1, 2, 5161))
        .select("grid_id", "centroid_lon", "centroid_lat")
        .orderBy("grid_id")
        .collect()
    )

    cell_map = {row["grid_id"]: (row["centroid_lon"], row["centroid_lat"]) for row in test_cells}

    for gid, (lon, lat) in cell_map.items():
        print(f"Grid {gid} Centroid: Longitude={lon:.6f}, Latitude={lat:.6f}")

    # 1. Milan Metropolitan Coordinates Bounding Box Check (approx 9.0 - 9.4 E, 45.3 - 45.6 N)
    g1_lon, g1_lat = cell_map[1]
    g2_lon, g2_lat = cell_map[2]
    assert 9.0 <= g1_lon <= 9.5 and 45.3 <= g1_lat <= 45.6, "Grid 1 coordinates land outside Milan region!"
    
    # 2. Adjacency Check: Grid 1 and Grid 2 must be adjacent (~0.002 to 0.004 degrees apart)
    lon_diff = abs(g1_lon - g2_lon)
    lat_diff = abs(g1_lat - g2_lat)
    assert 0.001 <= (lon_diff + lat_diff) <= 0.01, "Grid 1 and Grid 2 are not adjacent cells!"
    print("Geographic spot-check and cell adjacency: PASS")


    # ========================================================
    # 7. BROADCAST LEFT JOIN ENRICHMENT
    # ========================================================

    # Trim lookup for the join
    join_lookup_df = grid_lookup_df.select("grid_id", "geometry", "centroid_lon", "centroid_lat")

    grid_activity_geo_df = (
        hourly_grid_summary
        .join(
            broadcast(join_lookup_df),
            on="grid_id",
            how="left"
        )
        .select(
            "timestamp",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_activity",
            "geometry",
            "centroid_lon",
            "centroid_lat"
        )
    )


    # ========================================================
    # 8. JOIN INTEGRITY & COVERAGE VALIDATION
    # ========================================================

    joined_record_count = grid_activity_geo_df.count()
    assert joined_record_count == activity_record_count, "SP4 FAILED: Left join altered activity row count!"

    missing_geometry_df = grid_activity_geo_df.filter(col("geometry").isNull())
    missing_geometry_count = missing_geometry_df.count()
    unmatched_grid_ids = missing_geometry_df.select("grid_id").distinct().orderBy("grid_id")

    enrichment_percentage = ((activity_grid_count - unmatched_grid_ids.count()) / activity_grid_count) * 100.0

    print(f"\nJoin Record Count: {joined_record_count} (Preserved)")
    print(f"Enrichment Coverage: {enrichment_percentage:.2f}%")
    print(f"Unmatched Grids Count: {unmatched_grid_ids.count()}")

    assert missing_geometry_count == 0, "SP4 FAILED: Unmatched activity grids found with missing geometry."
    assert enrichment_percentage == 100.0, "SP4 FAILED: Coverage is less than 100%."
    print("Coverage and row-count validation: PASS")


    # ========================================================
    # 9. TOP HIGH-ACTIVITY GRIDS WITH GEOMETRY RETAINED
    # ========================================================

    top_activity_grids_geo_df = (
        hotspot_ranking
        .join(broadcast(join_lookup_df), on="grid_id", how="left")
        .select("grid_id", "daily_activity", "centroid_lon", "centroid_lat", "geometry")
        .orderBy(col("daily_activity").desc())
        .limit(10)
    )

    print("\n===== TOP 10 HIGH-ACTIVITY GRIDS WITH GEOMETRY =====")
    top_activity_grids_geo_df.select("grid_id", "daily_activity", "centroid_lon", "centroid_lat").show(10, truncate=False)


    # ========================================================
    # 10. FINAL SCHEMA & SAMPLE
    # ========================================================

    print("\n===== ENRICHED GEOSPATIAL DATAFRAME SCHEMA =====")
    grid_activity_geo_df.printSchema()

    print("\n===== ENRICHED DATA SAMPLE =====")
    grid_activity_geo_df.select("timestamp", "grid_id", "total_activity", "centroid_lon", "centroid_lat").show(5, truncate=False)

    print("\nSP4 completed successfully.")

    return (
        grid_activity_geo_df,
        unmatched_grid_ids,
        top_activity_grids_geo_df
    )


# ============================================================
# STANDALONE EXECUTION
# ============================================================

if __name__ == "__main__":
    spark = (
        SparkSession.builder
        .appName("SP4_Geospatial_Enrichment")
        .master("local[*]")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        run_sp4(spark)
    finally:
        spark.stop()