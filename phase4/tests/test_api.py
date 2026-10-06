r"""
Combined Acceptance Test Suite for API1 and API2.
Location: D:\project1\phase4\test_api.py
"""

from fastapi.testclient import TestClient
from main import app
from db import get_db_connection

client = TestClient(app)


def test_suite():
    print("\n" + "=" * 60)
    print("RUNNING API1 & API2 ACCEPTANCE TESTS")
    print("=" * 60)

    # ------------------------------------------------------------------------
    # API1 TESTS
    # ------------------------------------------------------------------------
    print("\n--- Testing API1: GET /network/summary ---")
    resp1 = client.get("/network/summary")
    assert resp1.status_code == 200, f"API1 Failed: {resp1.text}"
    summary = resp1.json()

    print(f"Summary Output: {summary}")
    assert summary["active_grids"] == 10000
    assert summary["top_grid"] == 5161
    assert summary["peak_hour"] == 17
    assert summary["total_activity"] > 0
    assert "as_of" in summary
    print("API1 Acceptance Tests: ALL PASSED")

    # ------------------------------------------------------------------------
    # API2 TESTS
    # ------------------------------------------------------------------------
    print("\n--- Testing API2: GET /network/grid/{grid_id} ---")

    # 1. Grid 4821 default trailing 24 hours
    resp2 = client.get("/network/grid/4821")
    assert resp2.status_code == 200, f"API2 Grid 4821 Failed: {resp2.text}"
    grid_data = resp2.json()
    assert grid_data["grid_id"] == 4821
    assert grid_data["data_points_count"] == 24
    assert len(grid_data["series"]) == 24
    print("Criterion 1 (Grid 4821 returns exactly 24 points): PASS")

    # 2. 404 bounds validation
    resp_0 = client.get("/network/grid/0")
    resp_10001 = client.get("/network/grid/10001")
    assert resp_0.status_code == 404, "Expected 404 for grid 0"
    assert resp_10001.status_code == 404, "Expected 404 for grid 10001"
    print("Criterion 2 (Grid 0 and 10001 return 404): PASS")

    # 3. Duplicate timestamp assertion
    ts_list = [p["timestamp"] for p in grid_data["series"]]
    assert len(ts_list) == len(set(ts_list)), "Duplicate timestamps found in series!"
    print("Criterion 3 (Zero duplicate timestamps in series): PASS")

    # 4. Spot check with MySQL warehouse
    latest_pt = grid_data["series"][-1]
    ts_query = latest_pt["timestamp"].replace("T", " ")

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ROUND(f.total_activity, 4) AS db_total
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE f.grid_id = 4821 AND t.timestamp = %s;
        """, (ts_query,))
        row = cursor.fetchone()
        cursor.close()

    assert row is not None
    assert abs(float(row["db_total"]) - float(latest_pt["total_activity"])) < 0.001
    print(f"Criterion 4 (Warehouse spot check matched at {ts_query}): PASS")

    print("\n" + "=" * 60)
    print("ALL API1 & API2 ACCEPTANCE CRITERIA PASSED SUCCESSFULLY.")
    print("=" * 60)


if __name__ == "__main__":
    test_suite()