
from fastapi.testclient import TestClient
from main import app
from db import get_db_connection

client = TestClient(app)

EXPECTED_ML2_FEATURES = [
    "avg_activity",
    "activity_growth",
    "active_hours",
    "peak_ratio",
    "variability",
    "internet_share"
]

def test_api4_acceptance():
    print("\n" + "=" * 60)
    print("RUNNING API4 ACCEPTANCE TESTS")
    print("=" * 60)

    # ------------------------------------------------------------------------
    # 1. EXACT ML2 FEATURE NAMES MATCH
    # ------------------------------------------------------------------------
    print("\n--- Test 1: ML2 Feature Names Parity ---")
    resp = client.get("/network/grid/5161/features")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()

    for feat in EXPECTED_ML2_FEATURES:
        assert feat in data, f"Missing required ML2 feature: {feat}"
    print(f"Criterion 1 (All 6 ML2 features present character-for-character): PASS -> {EXPECTED_ML2_FEATURES}")

    # ------------------------------------------------------------------------
    # 2. STORED FEATURE TABLE VALUE SPOT-CHECK
    # ------------------------------------------------------------------------
    print("\n--- Test 2: Value Parity with Stored Feature Store ---")
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM grid_features WHERE grid_id = 5161;")
        db_row = cursor.fetchone()
        cursor.close()

    assert db_row is not None, "Grid 5161 not found in MySQL grid_features table!"
    assert abs(data["avg_activity"] - float(db_row["avg_activity"])) < 0.001
    assert abs(data["peak_ratio"] - float(db_row["peak_ratio"])) < 0.001
    assert abs(data["variability"] - float(db_row["variability"])) < 0.001
    assert abs(data["internet_share"] - float(db_row["internet_share"])) < 0.001
    assert data["active_hours"] == db_row["active_hours"]
    print("Criterion 2 (Values match stored feature table exactly): PASS")

    # ------------------------------------------------------------------------
    # 3. FEATURE TIMESTAMP & FRESHNESS INDICATOR
    # ------------------------------------------------------------------------
    print("\n--- Test 3: Freshness & Quality Metadata ---")
    assert "feature_timestamp" in data
    assert "freshness_status" in data
    assert "freshness_hours" in data
    assert "data_quality_status" in data
    assert data["freshness_status"] in ["FRESH", "STALE", "DEGRADED"]
    print(f"Criterion 3 (Freshness status: {data['freshness_status']}, Freshness hours: {data['freshness_hours']}h): PASS")

    # ------------------------------------------------------------------------
    # 4. MISSING GRID / INVALID BOUNDS ERROR (NO SILENT ZEROS)
    # ------------------------------------------------------------------------
    print("\n--- Test 4: Missing Grid / Bounds Returns 404 ---")
    resp_0 = client.get("/network/grid/0/features")
    resp_10001 = client.get("/network/grid/10001/features")
    assert resp_0.status_code == 404, "Grid 0 must return 404"
    assert resp_10001.status_code == 404, "Grid 10001 must return 404"
    print("Criterion 4 (Missing grid or out-of-bounds returns clear 404 error rather than zeros): PASS")

    print("\n" + "=" * 60)
    print("ALL API4 ACCEPTANCE CRITERIA PASSED SUCCESSFULLY.")
    print("=" * 60)

if __name__ == "__main__":
    test_api4_acceptance()