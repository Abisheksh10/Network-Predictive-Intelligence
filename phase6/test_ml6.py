from datetime import datetime
import pandas as pd
import pytest
from batch_score import run_batch_scoring, get_db_connection, MODEL_VERSION
from features import get_warehouse_max_timestamp


def test_ml6_acceptance():
    print("\n" + "=" * 65)
    print("RUNNING ML6 ACCEPTANCE TEST SUITE")
    print("=" * 65)

    cutoff_ts = get_warehouse_max_timestamp()

    # 1. Run batch scoring
    scored_df = run_batch_scoring(cutoff_ts)

    # ------------------------------------------------------------------------
    # Criterion 1: One row per grid/timestamp, no duplicates
    # ------------------------------------------------------------------------
    print("\n--- Test 1: Uniqueness & Coverage ---")
    assert len(scored_df) == 10000, f"Expected 10,000 scored grids, got {len(scored_df)}"
    assert not scored_df.duplicated(subset=["grid_id", "score_timestamp"]).any(), "Duplicates detected!"
    print("Criterion 1 (One row per grid and interval, no duplicates): PASS")

    # ------------------------------------------------------------------------
    # Criterion 2: Every score carries model_version
    # ------------------------------------------------------------------------
    print("\n--- Test 2: Model Version Invariant ---")
    assert (scored_df["model_version"] == MODEL_VERSION).all(), "Missing or mismatched model_version!"
    print(f"Criterion 2 (Every score carries model_version '{MODEL_VERSION}'): PASS")

    # ------------------------------------------------------------------------
    # Criterion 3: Database Materialization & API Enriched Fields
    # ------------------------------------------------------------------------
    print("\n--- Test 3: API3 Additive Integration Parity ---")
    conn = get_db_connection()
    db_df = pd.read_sql(
        "SELECT * FROM network_risk_scores WHERE timestamp = %s LIMIT 10;",
        conn,
        params=(cutoff_ts.strftime("%Y-%m-%d %H:%M:%S"),)
    )
    conn.close()

    assert not db_df.empty, "Failed to find materialized records in network_risk_scores table."
    assert "risk_score" in db_df.columns and "risk_level" in db_df.columns
    print("Criterion 3 (network_risk_scores table materialized and ready for API3): PASS")

    # ------------------------------------------------------------------------
    # Criterion 4: Clean Dependency Guard
    # ------------------------------------------------------------------------
    print("\n--- Test 4: Upstream Feature Dependency Failure Guard ---")
    fake_future = cutoff_ts.replace(year=2099)
    try:
        run_batch_scoring(fake_future)
        pytest.fail("Should have failed when scoring non-existent features!")
    except RuntimeError as e:
        print(f"Criterion 4 (Pipeline fails cleanly if features are missing): PASS -> Caught expected: {e}")

    print("\n" + "=" * 65)
    print("ALL ML6 ACCEPTANCE CRITERIA PASSED SUCCESSFULLY.")
    print("=" * 65)


if __name__ == "__main__":
    test_ml6_acceptance()