import os
import glob

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType
)
from pyspark.sql.functions import (
    input_file_name,
    hour,
    col,
    min,
    max
)


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = r"D:\project1"

DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# IMPORTANT:
# Use only Milan files.
# Do NOT use sms-call-internet-*.csv
INPUT_PATTERN = os.path.join(
    DATA_DIR,
    "sms-call-internet-mi-*.csv"
)

WINUTILS_PATH = os.path.join(
    PROJECT_ROOT,
    "bin",
    "winutils.exe"
)


# ============================================================
# 2. HADOOP CONFIGURATION
# ============================================================

os.environ["HADOOP_HOME"] = PROJECT_ROOT
os.environ["PATH"] = os.path.join(PROJECT_ROOT, "bin") + os.pathsep + os.environ["PATH"]


# ============================================================
# 3. CHECK WINUTILS
# ============================================================

if not os.path.exists(WINUTILS_PATH):
    print("ERROR: winutils.exe not found.")
    print("Expected path:", WINUTILS_PATH)
    raise FileNotFoundError(WINUTILS_PATH)


# ============================================================
# 4. FIND INPUT FILES USING PYTHON
# ============================================================

input_files = sorted(glob.glob(INPUT_PATTERN))

print("Input files found:", len(input_files))

if len(input_files) == 0:
    print("ERROR: No input files found.")
    raise FileNotFoundError(INPUT_PATTERN)

for file in input_files:
    print(os.path.basename(file))


# ============================================================
# 5. CREATE SPARK SESSION
# ============================================================

spark = (
    SparkSession.builder
    .appName("SP1_Telecom_Milan")
    .master("local[*]")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")


# ============================================================
# 6. MANUAL SCHEMA
# ============================================================
#
# Keep the ORIGINAL CSV column names.
#
# CSV:
# datetime,CellID,countrycode,smsin,smsout,callin,callout,internet
#
# datetime      -> String initially
# CellID        -> Integer
# countrycode   -> String
# smsin         -> Double
# smsout        -> Double
# callin        -> Double
# callout       -> Double
# internet      -> Double
#
# datetime is kept as String so that we can explicitly
# convert it later.

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
# 7. READ ALL CSV FILES
# ============================================================
#
# IMPORTANT:
# We pass the actual list of files instead of:
#
# D:\project1\data\sms-call-internet-mi-*.csv
#
# This avoids the FileStreamSink wildcard warning that
# appeared in your previous execution.

raw_source_df = (
    spark.read
    .option("header", True)
    .option("mode", "PERMISSIVE") #if a row contains corrupted data or fewer/extra columns, spark sets the unparseable fields to null instead of throwing an error and failing the job.
    .schema(manual_schema)
    .csv(input_files)
)


# ============================================================
# 8. ADD SOURCE FILE NAME
# ============================================================

raw_source_df = raw_source_df.withColumn(
    "input_file_name",
    input_file_name()
)


# ============================================================
# 9. CONVERT DATETIME
# ============================================================

from pyspark.sql.functions import to_timestamp

raw_source_df = raw_source_df.withColumn(
    "datetime",
    to_timestamp("datetime", "yyyy-MM-dd HH:mm:ss")
)


# ============================================================
# 10. DISPLAY SCHEMA
# ============================================================

print("\n========== SCHEMA ==========")

raw_source_df.printSchema()


# ============================================================
# 11. DISPLAY SAMPLE DATA
# ============================================================

print("\n========== SAMPLE DATA ==========")

raw_source_df.show(10, truncate=False) #spark truncate any value longer that 20 characters and appends ... setting it to false ensures long strings particularly full file path strings in the input_file_name column are printed without being cut off.


# ============================================================
# 12. TOTAL RAW ROWS
# ============================================================

total_rows = raw_source_df.count()

print("\nTotal raw rows:", total_rows)


# ============================================================
# 13. DISTINCT SOURCE FILES
# ============================================================

distinct_files = (
    raw_source_df
    .select("input_file_name")
    .distinct()
    .count()
)

print("Distinct source files reported by Spark:", distinct_files)


# ============================================================
# 14. UNIQUE GRID COUNT
# ============================================================

unique_grids = (
    raw_source_df
    .select("CellID")
    .distinct()
    .count()
)

print("Unique grids:", unique_grids)


# ============================================================
# 15. GRID ID RANGE
# ============================================================

grid_range = raw_source_df.select(
    min("CellID").alias("min_grid"),
    max("CellID").alias("max_grid")
).collect()[0]

print(
    "Grid ID range:",
    grid_range["min_grid"],
    "-",
    grid_range["max_grid"]
)


# ============================================================
# 16. INVALID GRID IDs
# ============================================================

invalid_grid_rows = (
    raw_source_df
    .filter(
        (col("CellID").isNull()) |
        (col("CellID") < 1) |
        (col("CellID") > 10000)
    )
    .count()
)

print("Invalid grid_id rows:", invalid_grid_rows)


# ============================================================
# 17. COUNTRY CODE CATEGORIES
# ============================================================

country_code_count = (
    raw_source_df
    .select("countrycode")
    .distinct()
    .count()
)

print("Country-code categories:", country_code_count)

print("\nCountry-code values:")

raw_source_df.select(
    "countrycode"
).distinct().orderBy(
    "countrycode"
).show(50, truncate=False)

from pyspark.sql.functions import date_trunc
# ============================================================
# 18. DISTINCT HOURLY TIMESTAMPS
# ============================================================

# distinct_timestamps = (
#     raw_source_df
#     .select(hour("datetime"))
#     .distinct()
#     .count()
# )
distinct_timestamps = (
    raw_source_df
    .select(date_trunc("hour", col("datetime")).alias("hourly_interval")) # it performs operation such that every time within a hour are grouped in that hourlike 00:10:00,00:20:00 into single entry 00:00:000
    .distinct()
    .count()
)

print("Distinct hourly timestamps:", distinct_timestamps)

EXPECTED_TIMESTAMP_COUNT = 7 * 24

print("Expected timestamp count:", EXPECTED_TIMESTAMP_COUNT)


# ============================================================
# 19. TIMESTAMP RANGE
# ============================================================

timestamp_range = raw_source_df.select(
    min("datetime").alias("min_datetime"),
    max("datetime").alias("max_datetime")
).collect()[0]

print("Timestamp range:",
    timestamp_range["min_datetime"],
    "to",
    timestamp_range["max_datetime"]
)


# ============================================================
# 20. INPUT FILE TRACEABILITY
# ============================================================

missing_file_name_rows = (
    raw_source_df
    .filter(col("input_file_name").isNull())
    .count()
)

print("Rows missing input_file_name:", missing_file_name_rows)


# ============================================================
# 21. FILE-LEVEL ROW COUNTS
# ============================================================

print("\n========== FILE-LEVEL ROW COUNTS ==========")

file_counts = (
    raw_source_df
    .groupBy("input_file_name")
    .count()
    .orderBy("input_file_name")
)

file_counts.show(
    file_counts.count(),
    truncate=False
)


# ============================================================
# 22. DISTINCT GRID / HOUR / COUNTRY RECORDS
# ============================================================

distinct_grain_records = (
    raw_source_df
    .select(
        "datetime",
        "CellID",
        "countrycode"
    )
    .distinct()
    .count()
)

print(
    "Distinct grid/hour/country records:",
    distinct_grain_records
)


# ============================================================
# 23. DUPLICATE GRID / HOUR / COUNTRY RECORDS
# ============================================================

duplicate_groups = (
    raw_source_df
    .groupBy(
        "datetime",
        "CellID",
        "countrycode"
    )
    .count()
    .filter(col("count") > 1)
    .count()
)

print(
    "Duplicate timestamp/grid/country records:",
    duplicate_groups
)


# ============================================================
# 24. SPARK PARTITION COUNT
# ============================================================

partition_count = raw_source_df.rdd.getNumPartitions()

print("Spark partition count:", partition_count)


# ============================================================
# 25. INFERRED SCHEMA COMPARISON
# ============================================================
#
# This is only for demonstrating the difference between
# manual schema and inferSchema.
#
# We use the actual file list again, so the wildcard
# FileStreamSink warning does not occur.

print("\n========== INFERRED SCHEMA COMPARISON ==========")

inferred_df = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(input_files)
)

print("\nSchema produced by inferSchema:")

inferred_df.printSchema()


print("Manual schema:")
print(manual_schema.simpleString())


# ============================================================
# 26. FIELD-LEVEL SCHEMA COMPARISON
# ============================================================

manual_fields = {
    field.name: field.dataType.simpleString()
    for field in manual_schema.fields
}

inferred_fields = {
    field.name: field.dataType.simpleString()
    for field in inferred_df.schema.fields
}

print("\n========== FIELD-LEVEL SCHEMA COMPARISON ==========")

for field_name in manual_fields:

    manual_type = manual_fields.get(field_name)
    inferred_type = inferred_fields.get(field_name)

    print(
        f"{field_name}: "
        f"manual={manual_type}, "
        f"inferred={inferred_type}"
    )


# ============================================================
# 27. NULL VALIDATION
# ============================================================

print("\n========== NULL VALIDATION ==========")

null_datetime = (
    raw_source_df
    .filter(col("datetime").isNull())
    .count()
)

null_cellid = (
    raw_source_df
    .filter(col("CellID").isNull())
    .count()
)

null_countrycode = (
    raw_source_df
    .filter(col("countrycode").isNull())
    .count()
)

print("Null datetime rows:", null_datetime)
print("Null CellID rows:", null_cellid)
print("Null countrycode rows:", null_countrycode)


# ============================================================
# 28. BASIC VALIDATIONS
# ============================================================

print("\n========== VALIDATION RESULTS ==========")

print(
    "File count validation:",
    "PASS" if distinct_files == len(input_files) else "FAIL"
)

print(
    "Grid ID validation:",
    "PASS" if invalid_grid_rows == 0 else "FAIL"
)

print(
    "Timestamp count validation:",
    "PASS"
    if distinct_timestamps == EXPECTED_TIMESTAMP_COUNT
    else "FAIL"
)

print(
    "Input file traceability validation:",
    "PASS" if missing_file_name_rows == 0 else "FAIL"
)

print(
    "Raw grain validation:",
    "PASS"
    if distinct_grain_records == total_rows
    else "FAIL"
)

print(
    "Duplicate validation:",
    "PASS" if duplicate_groups == 0 else "FAIL"
)


# ============================================================
# 29. FINAL SUMMARY
# ============================================================

print("\n========== SP1 SUMMARY ==========")

print("Input files found:", len(input_files))
print("Spark source files:", distinct_files)
print("Total rows:", total_rows)
print("Unique grids:", unique_grids)
print("Country-code categories:", country_code_count)
print("Distinct hourly timestamps:", distinct_timestamps)
print("Spark partitions:", partition_count)
print("Duplicate groups:", duplicate_groups)

print("\nSP1 completed.")


# ============================================================
# 30. STOP SPARK
# ============================================================

spark.stop()