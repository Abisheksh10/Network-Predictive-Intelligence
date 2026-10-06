from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from anomaly import (
    compute_dynamic_baseline,
    score_anomalies,
    extract_historical_and_current_data
)
from features import get_warehouse_max_timestamp, get_db_connection


def test_ml4_acceptance():
    print("\n" + "=" * 65)
    print("RUNNING ML4 ACCEPTANCE TESTS")
    print("=" * 65)

    cutoff_ts = get_warehouse_max_timestamp()

    # ------------------------------------------------------------------------
    # 1. Multi-Day History & Bucket Count Verification
    # ------------------------------------------------------------------------
    print("\n--- Test 1: Multi-Day History in Hour-of-Day Buckets ---")
    hist_df, curr_df = extract_historical_and_current_data(cutoff_ts, history_days=7)
    
    baseline_df = compute_dynamic_baseline(
        df=hist_df,
        group_keys=["grid_id", "hour"],
        metric_col="total_activity"
    )

    avg_bucket_count = baseline_df["bucket_count"].mean()
    max_bucket_count = baseline_df["bucket_count"].max()
    print(f"Average history samples per [grid_id, hour] bucket: {avg_bucket_count:.2f} days")
    print(f"Max history samples per [grid_id, hour] bucket:     {max_bucket_count} days")

    assert avg_bucket_count > 1.0, f"Expected >1 day of history, got {avg_bucket_count}"
    print("Criterion 1 (Hour-of-day baseline uses >1 day of history): PASS")

    # ------------------------------------------------------------------------
    # 2. Shared Baseline Function Invariant
    # ------------------------------------------------------------------------
    print("\n--- Test 2: Single Baseline Implementation Invariant ---")
    # Verify the same function works for within-day (grid_id only) and hour-of-day (grid_id + hour)
    within_day_base = compute_dynamic_baseline(hist_df, group_keys=["grid_id"])
    hour_of_day_base = compute_dynamic_baseline(hist_df, group_keys=["grid_id", "hour"])

    assert "baseline_mean" in within_day_base.columns and "baseline_std" in within_day_base.columns
    assert "baseline_mean" in hour_of_day_base.columns and "baseline_std" in hour_of_day_base.columns
    print("Criterion 2 (One generalized baseline implementation for within-day & hour-of-day): PASS")

    # ------------------------------------------------------------------------
    # 3. Dual-Directional Anomalies (HIGH and LOW)
    # ------------------------------------------------------------------------
    print("\n--- Test 3: Dual Directional Anomalies (HIGH & LOW) ---")
    scored_df = score_anomalies(cutoff_ts)

    high_count = (scored_df["direction"] == "HIGH").sum()
    low_count = (scored_df["direction"] == "LOW").sum()
    normal_count = (scored_df["direction"] == "NORMAL").sum()

    print(f"Flagged HIGH Anomalies:   {high_count:,}")
    print(f"Flagged LOW Anomalies:    {low_count:,}")
    print(f"Evaluated NORMAL:        {normal_count:,}")

    assert high_count > 0, "Expected at least one HIGH anomaly!"
    assert low_count > 0, "Expected at least one LOW anomaly!"
    print("Criterion 3 (Both HIGH and LOW anomalies produced with direction recorded): PASS")

    # ------------------------------------------------------------------------
    # 4. Spot Check Ground Truth for a HIGH and a LOW Case
    # ------------------------------------------------------------------------
    print("\n--- Test 4: Anomaly Spot-Check Ground Truth ---")
    high_sample = scored_df[scored_df["direction"] == "HIGH"].iloc[0]
    low_sample = scored_df[scored_df["direction"] == "LOW"].iloc[0]

    print(f"Sample HIGH: Grid {int(high_sample['grid_id'])} at {int(high_sample['hour']):02d}:00 | "
          f"Current={high_sample['total_activity']:.1f} vs Baseline={high_sample['baseline_mean']:.1f} | "
          f"Score={high_sample['anomaly_score']} | Reason={high_sample['reason']}")

    print(f"Sample LOW:  Grid {int(low_sample['grid_id'])} at {int(low_sample['hour']):02d}:00 | "
          f"Current={low_sample['total_activity']:.1f} vs Baseline={low_sample['baseline_mean']:.1f} | "
          f"Score={low_sample['anomaly_score']} | Reason={low_sample['reason']}")

    assert high_sample["total_activity"] > high_sample["baseline_mean"]
    assert low_sample["total_activity"] < low_sample["baseline_mean"]
    print("Ground-truth directional sanity check: PASS")

    print("\n" + "=" * 65)
    print("ALL ML4 ACCEPTANCE CRITERIA PASSED SUCCESSFULLY.")
    print("=" * 65)


if __name__ == "__main__":
    test_ml4_acceptance()