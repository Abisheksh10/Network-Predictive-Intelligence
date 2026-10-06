import pandas as pd


# ============================================================
# 1. LOAD DATA
# ============================================================

FILE_PATH = "../data/landing/sms-call-internet-mi-2013-11-01.csv"
df = pd.read_csv(FILE_PATH)

print("=" * 60)
print("DATASET SHAPE")
print("=" * 60)
print(df.shape)
print("\n" + "=" * 60)
print("RAW COLUMNS")
print("=" * 60)
print(df.columns.tolist())
print("\n" + "=" * 60)
print("DATA TYPES")
print("=" * 60)
print(df.dtypes)


# ============================================================
# 2. RAW → CANONICAL COLUMN MAPPING
# ============================================================

column_mapping = {
    "datetime": "timestamp",
    "CellID": "grid_id",
    "countrycode": "country_code",
    "smsin": "sms_in",
    "smsout": "sms_out",
    "callin": "call_in",
    "callout": "call_out",
    "internet": "internet_activity"
}

print("\n" + "=" * 60)
print("RAW → CANONICAL MAPPING")
print("=" * 60)

for raw_column, canonical_column in column_mapping.items():
    print(f"{raw_column} -> {canonical_column}")

canonical_df = df.rename(columns=column_mapping).copy()


# ============================================================
# 3. PARSE TIMESTAMP AND VERIFY HOURLY CADENCE
# ============================================================

canonical_df["timestamp"] = pd.to_datetime(
    canonical_df["timestamp"],
    errors="coerce"
)

print("\n" + "=" * 60)
print("TIMESTAMP INFORMATION")
print("=" * 60)

print("Minimum timestamp:", canonical_df["timestamp"].min())
print("Maximum timestamp:", canonical_df["timestamp"].max())

distinct_timestamps = (
    canonical_df["timestamp"]
    .dropna()
    .sort_values()
    .drop_duplicates()
)

print("Number of distinct timestamps:", len(distinct_timestamps))

# Calculate the difference between consecutive timestamps
time_differences = distinct_timestamps.diff().dropna()

print("\nTime differences:")
print(time_differences.value_counts())

hourly_cadence = (
    len(distinct_timestamps) == 24
    and time_differences.eq(pd.Timedelta(hours=1)).all()
)

print("\nHourly cadence valid:", hourly_cadence)


# Derive time fields
canonical_df["date"] = canonical_df["timestamp"].dt.date
canonical_df["hour"] = canonical_df["timestamp"].dt.hour
canonical_df["day_of_week"] = canonical_df["timestamp"].dt.day_name()

print("\nDerived time columns:")
print(
    canonical_df[
        ["timestamp", "date", "hour", "day_of_week"]
    ].head()
)


# ============================================================
# 4. DATA QUALITY CHECKS
# ============================================================

print("\n" + "=" * 60)
print("DATA QUALITY CHECKS")
print("=" * 60)


# ---- Missing grid_id ----

missing_grid_id = canonical_df["grid_id"].isnull().sum()

print("Missing grid_id:", missing_grid_id)


# ---- Missing timestamp ----

missing_timestamp = canonical_df["timestamp"].isnull().sum()

print("Missing timestamp:", missing_timestamp)


# ---- Blank / missing activity measures ----

activity_columns = [
    "sms_in",
    "sms_out",
    "call_in",
    "call_out",
    "internet_activity"
]

print("\nBlank activity values:")

activity_null_counts = canonical_df[activity_columns].isnull().sum()
print(activity_null_counts)


# ---- Exact duplicate rows ----

duplicate_count = canonical_df.duplicated().sum()

print("\nExact duplicate rows:", duplicate_count)


# ---- Negative activity values ----

negative_counts = (
    canonical_df[activity_columns] < 0
).sum()

print("\nNegative activity values:")
print(negative_counts)


# ============================================================
# 5. COUNTRY-CODE / RAW GRAIN INVESTIGATION
# ============================================================

print("\n" + "=" * 60)
print("COUNTRY CODE ANALYSIS")
print("=" * 60)

print("Country-code categories:")
print(canonical_df["country_code"].value_counts(dropna=False))


# Find grid + timestamp combinations that have
# more than one country code.

grid_hour_country_counts = (
    canonical_df
    .groupby(["timestamp", "grid_id"])["country_code"]
    .nunique()
)

multiple_country_rows = (
    grid_hour_country_counts[
        grid_hour_country_counts > 1
    ]
)

print(
    "\nNumber of grid/hour combinations "
    "with multiple country codes:",
    len(multiple_country_rows)
)


# Show one concrete example
if not multiple_country_rows.empty:

    example_timestamp, example_grid = multiple_country_rows.index[0]

    print("\nExample:")
    print("Timestamp:", example_timestamp)
    print("Grid ID:", example_grid)

    example_rows = canonical_df[
        (canonical_df["timestamp"] == example_timestamp)
        & (canonical_df["grid_id"] == example_grid)
    ]

    print(
        example_rows[
            [
                "timestamp",
                "grid_id",
                "country_code",
                "sms_in",
                "sms_out",
                "call_in",
                "call_out",
                "internet_activity"
            ]
        ]
    )


# ============================================================
# 6. DERIVED ACTIVITY MEASURES
# ============================================================

canonical_df["total_sms"] = (
    canonical_df["sms_in"]
    + canonical_df["sms_out"]
)

canonical_df["total_calls"] = (
    canonical_df["call_in"]
    + canonical_df["call_out"]
)

canonical_df["total_activity"] = (
    canonical_df["total_sms"]
    + canonical_df["total_calls"]
    + canonical_df["internet_activity"]
)

print("\n" + "=" * 60)
print("DERIVED ACTIVITY MEASURES")
print("=" * 60)

print(
    canonical_df[
        [
            "total_sms",
            "total_calls",
            "total_activity"
        ]
    ].head()
)


# ============================================================
# 7. PROFILING FACTS
# ============================================================

print("\n" + "=" * 60)
print("PROFILING FACTS")
print("=" * 60)


# Unique grids
unique_grids = canonical_df["grid_id"].nunique()

print("Unique grids:", unique_grids)


# Time range
start_time = canonical_df["timestamp"].min()
end_time = canonical_df["timestamp"].max()

print("Time range:", start_time, "to", end_time)


# Cadence
if hourly_cadence:
    cadence = "Hourly"
else:
    cadence = "Invalid / Non-hourly"

print("Cadence:", cadence)


# Country-code categories
country_categories = (
    canonical_df["country_code"]
    .dropna()
    .unique()
)

print("Country-code categories:")
print(sorted(country_categories))


# Busiest hourly window
hourly_activity = (
    canonical_df
    .groupby("hour")["total_activity"]
    .sum()
)


busiest_hour = hourly_activity.idxmax()
busiest_hour_activity = hourly_activity.max()

print(f"Busiest hourly window: {busiest_hour}:00")
print("Activity during busiest hour:",busiest_hour_activity)


# Busiest grid
grid_activity = (
    canonical_df
    .groupby("grid_id")["total_activity"]
    .sum()
)

busiest_grid = grid_activity.idxmax()
busiest_grid_activity = grid_activity.max()

print("Busiest grid:", busiest_grid)
print(
    "Activity in busiest grid:",
    busiest_grid_activity
)


# Null counts per column
null_counts = canonical_df.isnull().sum()

print("\nNull counts per column:")
print(null_counts)


# ============================================================
# 8. FINAL DATAFRAME INFORMATION
# ============================================================

print("\n" + "=" * 60)
print("CANONICAL DATAFRAME")
print("=" * 60)

print(canonical_df.head())

print("\nCanonical columns:")
print(canonical_df.columns.tolist())


# ============================================================
# 9. CURATED-LAYER NULL POLICY
# ============================================================

print("\n" + "=" * 60)
print("CURATED-LAYER NULL POLICY")
print("=" * 60)

print("""
Activity-measure blanks:
    May be converted to zero in the curated layer,
    after profiling and documenting the number handled.

Missing grid_id:
    Data-quality failure.
    Do not default to zero.
    Quarantine the affected record.

Missing timestamp:
    Data-quality failure.
    Do not default to a value.
    Quarantine the affected record.

The raw input file remains unchanged.
""")