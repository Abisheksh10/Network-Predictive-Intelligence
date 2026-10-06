import logging
from pathlib import Path

import pandas as pd


# ============================================================
# LOGGING CONFIGURATION
# ============================================================
project_root = Path(__file__).resolve().parent.parent

logs_directory = project_root / "logs"

logs_directory.mkdir(
    parents=True,
    exist_ok=True
)

log_file = logs_directory / "usage_processor.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class UsageProcessor:

    # --------------------------------------------------------
    # PROJECT SCHEMA
    # --------------------------------------------------------

    COLUMN_MAPPING = {
        "datetime": "timestamp",
        "CellID": "grid_id",
        "countrycode": "country_code",
        "smsin": "sms_in",
        "smsout": "sms_out",
        "callin": "call_in",
        "callout": "call_out",
        "internet": "internet_activity"
    }

    REQUIRED_COLUMNS = [
        "timestamp",
        "grid_id",
        "country_code",
        "sms_in",
        "sms_out",
        "call_in",
        "call_out",
        "internet_activity"
    ]

    ACTIVITY_COLUMNS = [
        "sms_in",
        "sms_out",
        "call_in",
        "call_out",
        "internet_activity"
    ]

    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    def __init__(self, file_path=None, dataframe=None):

        if file_path is None and dataframe is None:
            raise ValueError(
                "Either file_path or dataframe must be provided."
            )

        if file_path is not None and dataframe is not None:
            raise ValueError(
                "Provide either file_path or dataframe, not both."
            )

        self.file_path = file_path

        # Original raw data
        self.raw_df = None

        # Canonical / cleaned data
        self.canonical_df = None

        # Grid/hour analytics data
        self.analytics_df = None

        # Summary tables
        self.daily_summary = None
        self.grid_summary = None

        # Metrics used for logging/reporting
        self.input_rows = 0
        self.rejected_rows = 0
        self.nulls_handled = 0
        self.output_rows = 0

        # If DataFrame was supplied
        if dataframe is not None:

            self.raw_df = dataframe.copy()

            logger.info(
                "Initialized processor with DataFrame: %d rows",
                len(self.raw_df)
            )

    # ========================================================
    # 1. LOAD DATA
    # ========================================================

    def load_data(self):

        if self.raw_df is not None:
            logger.info(
                "Using supplied DataFrame: %d rows",
                len(self.raw_df)
            )
            return self.raw_df.copy()

        if not Path(self.file_path).exists():
            raise FileNotFoundError(
                f"File not found: {self.file_path}"
            )

        self.raw_df = pd.read_csv(self.file_path)

        self.input_rows = len(self.raw_df)

        logger.info(
            "Loaded file: %s | rows=%d",
            self.file_path,
            self.input_rows
        )

        return self.raw_df.copy()

    # ========================================================
    # 2. CLEAN DATA
    # ========================================================

    def clean_data(self):

        if self.raw_df is None:
            raise RuntimeError(
                "Call load_data() before clean_data()."
            )

        # Never modify raw_df
        df = self.raw_df.copy()

        # ----------------------------------------------------
        # Rename raw columns to canonical names
        # ----------------------------------------------------

        df = df.rename(columns=self.COLUMN_MAPPING)

        # ----------------------------------------------------
        # Check required columns
        # ----------------------------------------------------

        missing_columns = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        # ----------------------------------------------------
        # Convert timestamp
        # ----------------------------------------------------

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce"
        )

        # ----------------------------------------------------
        # Missing timestamp / grid_id
        # ----------------------------------------------------

        invalid_key_mask = (
            df["timestamp"].isna()
            | df["grid_id"].isna()
        )

        rejected = invalid_key_mask.sum()

        if rejected > 0:

            logger.warning(
                "Rejecting %d rows with missing timestamp/grid_id",
                rejected
            )

            df = df.loc[~invalid_key_mask].copy()

            self.rejected_rows += rejected

        # ----------------------------------------------------
        # Check negative activity values
        # ----------------------------------------------------

        negative_mask = (
            df[self.ACTIVITY_COLUMNS] < 0
        ).any(axis=1)

        negative_rows = negative_mask.sum()

        if negative_rows > 0:

            raise ValueError(
                f"Found {negative_rows} rows containing "
                "negative activity values."
            )

        # ----------------------------------------------------
        # Curated-layer NULL → ZERO rule
        # ----------------------------------------------------

        null_count = (
            df[self.ACTIVITY_COLUMNS]
            .isna()
            .sum()
            .sum()
        )

        self.nulls_handled = int(null_count)

        if null_count > 0:

            logger.info(
                "Handling %d activity nulls using "
                "curated-layer null-to-zero rule",
                null_count
            )

            df[self.ACTIVITY_COLUMNS] = (
                df[self.ACTIVITY_COLUMNS]
                .fillna(0)
            )

        logger.info(
            "Cleaned data: input=%d rejected=%d remaining=%d",
            self.input_rows,
            self.rejected_rows,
            len(df)
        )

        self.canonical_df = df

        return self.canonical_df.copy()

    # ========================================================
    # 3. DERIVE TIME FEATURES
    # ========================================================

    def derive_time_features(self):

        if self.canonical_df is None:
            raise RuntimeError(
                "Call clean_data() before derive_time_features()."
            )

        df = self.canonical_df.copy()

        df["date"] = df["timestamp"].dt.date
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = (
            df["timestamp"].dt.day_name()
        )

        self.canonical_df = df

        logger.info(
            "Derived date, hour and day_of_week."
        )

        return self.canonical_df.copy()

    # ========================================================
    # 4. AGGREGATE TO GRID / HOUR
    # ========================================================

    def aggregate_to_grid_time(self):

        if self.canonical_df is None:
            raise RuntimeError(
                "Call derive_time_features() before "
                "aggregate_to_grid_time()."
            )

        df = self.canonical_df.copy()

        # ----------------------------------------------------
        # Aggregate country-code rows
        # ----------------------------------------------------

        aggregation_columns = {
            "sms_in": "sum",
            "sms_out": "sum",
            "call_in": "sum",
            "call_out": "sum",
            "internet_activity": "sum"
        }

        analytics_df = (
            df.groupby(
                ["timestamp", "grid_id"],
                as_index=False
            )
            .agg(aggregation_columns)
        )

        # ----------------------------------------------------
        # Add time features to aggregated data
        # ----------------------------------------------------

        analytics_df["date"] = (
            analytics_df["timestamp"].dt.date
        )

        analytics_df["hour"] = (
            analytics_df["timestamp"].dt.hour
        )

        analytics_df["day_of_week"] = (
            analytics_df["timestamp"].dt.day_name()
        )

        self.analytics_df = analytics_df

        self.output_rows = len(analytics_df)

        logger.info(
            "Aggregated grid/hour data: input=%d output=%d",
            len(df),
            self.output_rows
        )

        # ----------------------------------------------------
        # Defensive validation
        # ----------------------------------------------------

        duplicates = (
            analytics_df
            .duplicated(
                subset=["grid_id", "timestamp"]
            )
            .sum()
        )

        if duplicates > 0:

            raise ValueError(
                f"Aggregation produced {duplicates} "
                "duplicate grid/hour records."
            )

        if "country_code" in analytics_df.columns:

            raise ValueError(
                "country_code must not exist in "
                "grid/hour analytics output."
            )

        return self.analytics_df.copy()

    # ========================================================
    # 5. DERIVE ACTIVITY FEATURES
    # ========================================================

    def derive_activity_features(self):

        if self.analytics_df is None:
            raise RuntimeError(
                "Call aggregate_to_grid_time() before "
                "derive_activity_features()."
            )

        df = self.analytics_df.copy()

        df["total_sms"] = (
            df["sms_in"]
            + df["sms_out"]
        )

        df["total_calls"] = (
            df["call_in"]
            + df["call_out"]
        )

        df["total_activity"] = (
            df["total_sms"]
            + df["total_calls"]
            + df["internet_activity"]
        )

        self.analytics_df = df

        logger.info(
            "Derived total_sms, total_calls and total_activity."
        )

        return self.analytics_df.copy()

    # ========================================================
    # 6. COMPUTE KPIs
    # ========================================================

    def compute_kpis(self):

        if self.analytics_df is None:
            raise RuntimeError(
                "Call derive_activity_features() before "
                "compute_kpis()."
            )

        df = self.analytics_df

        # ----------------------------------------------------
        # Daily summary
        # ----------------------------------------------------

        self.daily_summary = (
            df.groupby("date", as_index=False)
            .agg(
                total_sms=("total_sms", "sum"),
                total_calls=("total_calls", "sum"),
                total_activity=("total_activity", "sum"),
                active_grids=("grid_id", "nunique")
            )
        )

        # ----------------------------------------------------
        # Grid summary
        # ----------------------------------------------------

        self.grid_summary = (
            df.groupby("grid_id", as_index=False)
            .agg(
                total_sms=("total_sms", "sum"),
                total_calls=("total_calls", "sum"),
                total_activity=("total_activity", "sum"),
                active_hours=("timestamp", "nunique")
            )
        )

        logger.info(
            "Computed daily summary: %d rows",
            len(self.daily_summary)
        )

        logger.info(
            "Computed grid summary: %d rows",
            len(self.grid_summary)
        )

        return {
            "daily_summary": self.daily_summary.copy(),
            "grid_summary": self.grid_summary.copy()
        }

    # ========================================================
    # 7. EXPORT SUMMARY
    # ========================================================

    def export_summary(self, output_directory="outputs"):

        if self.daily_summary is None:
            raise RuntimeError(
                "Call compute_kpis() before export_summary()."
            )

        output_directory = Path(output_directory)

        output_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        daily_path = (
            output_directory / "daily_summary.csv"
        )

        grid_path = (
            output_directory / "grid_summary.csv"
        )

        self.daily_summary.to_csv(
            daily_path,
            index=False
        )

        self.grid_summary.to_csv(
            grid_path,
            index=False
        )

        logger.info(
            "Daily summary exported: %s",
            daily_path
        )

        logger.info(
            "Grid summary exported: %s",
            grid_path
        )

        return {
            "daily_summary": str(daily_path),
            "grid_summary": str(grid_path)
        }