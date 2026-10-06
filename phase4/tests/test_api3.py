
from fastapi.testclient import TestClient
from main import app
from models import HotspotItem, NetworkAlertItem

client = TestClient(app)


def test_api3_acceptance():
    print("\n" + "=" * 60)
    print("RUNNING API3 ACCEPTANCE TESTS")
    print("=" * 60)

    # ------------------------------------------------------------------------
    # 1. LIMIT RESPECTED EXACTLY
    # ------------------------------------------------------------------------
    print("\n--- Test 1: Limit Enforcement ---")
    for req_limit in [5, 10, 20]:
        resp = client.get(f"/network/hotspots?limit={req_limit}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hotspots"]) == req_limit
        assert data["total_hotspots_returned"] == req_limit
    print("Criterion 1 (limit parameter respected exactly on hotspots): PASS")

    resp_alerts = client.get("/network/alerts?limit=15")
    assert resp_alerts.status_code == 200
    alerts_data = resp_alerts.json()
    assert len(alerts_data["alerts"]) <= 15
    print("Criterion 1b (limit parameter respected on alerts): PASS")

    # ------------------------------------------------------------------------
    # 2. NO 'CONGESTION' WORD IN RESPONSES OR SCHEMAS
    # ------------------------------------------------------------------------
    print("\n--- Test 2: Banned Terminology Check ('congestion') ---")
    hotspots_raw_text = client.get("/network/hotspots?limit=50").text.lower()
    alerts_raw_text = client.get("/network/alerts?limit=50").text.lower()
    openapi_spec_text = client.get("/openapi.json").text.lower()

    assert "congestion" not in hotspots_raw_text, "Banned word 'congestion' found in hotspots output!"
    assert "congestion" not in alerts_raw_text, "Banned word 'congestion' found in alerts output!"
    assert "congestion" not in openapi_spec_text, "Banned word 'congestion' found in OpenAPI schema!"
    print("Criterion 2 (The word 'congestion' appears nowhere): PASS")

    # ------------------------------------------------------------------------
    # 3. FORWARD-COMPATIBLE ML FIELDS DO NOT BREAK CLIENT
    # ------------------------------------------------------------------------
    print("\n--- Test 3: Forward-Compatible ML Extensibility ---")
    # Simulate an ML service adding risk fields dynamically
    mock_ml_hotspot_payload = {
        "grid_id": 5161,
        "centroid_lon": 9.193381,
        "centroid_lat": 45.465461,
        "total_activity": 274800.3,
        "internet_activity": 260000.0,
        "total_calls": 8000.0,
        "total_sms": 6800.3,
        "internet_share": 0.946,
        "rank": 1,
        "risk_score": 0.88,
        "risk_level": "ELEVATED_ATTENTION",
        "model_version": "v1.2-lightgbm"
    }

    # Validate that Pydantic deserializes this seamlessly
    parsed_item = HotspotItem(**mock_ml_hotspot_payload)
    assert parsed_item.risk_score == 0.88
    assert parsed_item.model_version == "v1.2-lightgbm"
    print("Criterion 3 (Nullable ML risk fields deserialize seamlessly): PASS")

    # ------------------------------------------------------------------------
    # 4. DETERMINISTIC ORDERING REPRODUCIBILITY
    # ------------------------------------------------------------------------
    print("\n--- Test 4: Deterministic Ordering ---")
    call_1 = client.get("/network/hotspots?limit=10").json()["hotspots"]
    call_2 = client.get("/network/hotspots?limit=10").json()["hotspots"]

    assert [h["grid_id"] for h in call_1] == [h["grid_id"] for h in call_2], "Hotspots ordering is non-deterministic!"
    assert [h["total_activity"] for h in call_1] == [h["total_activity"] for h in call_2], "Activity ordering differs!"
    print("Criterion 4 (Deterministic ordering verified across repeated calls): PASS")

    # ------------------------------------------------------------------------
    # 5. ALL RETURNED GRIDS EXIST IN MILAN GRID [1, 10000]
    # ------------------------------------------------------------------------
    print("\n--- Test 5: Spatial Bounds Validation ---")
    for h in call_1:
        assert 1 <= h["grid_id"] <= 10000, f"Invalid grid_id {h['grid_id']} out of Milan bounds!"
    for a in alerts_data["alerts"]:
        assert 1 <= a["grid_id"] <= 10000, f"Invalid grid_id {a['grid_id']} out of Milan bounds!"
    print("Criterion 5 (All grid_ids strictly within [1, 10000]): PASS")

    # ------------------------------------------------------------------------
    # 6. SEVERITY FILTERING
    # ------------------------------------------------------------------------
    print("\n--- Test 6: Severity Filtering on Alerts ---")
    crit_resp = client.get("/network/alerts?severity=CRITICAL&limit=10")
    assert crit_resp.status_code == 200
    crit_data = crit_resp.json()
    for a in crit_data["alerts"]:
        assert a["severity"] == "CRITICAL"
    print("Severity Filter (CRITICAL): PASS")

    print("\n" + "=" * 60)
    print("ALL API3 ACCEPTANCE CRITERIA PASSED SUCCESSFULLY.")
    print("=" * 60)


if __name__ == "__main__":
    test_api3_acceptance()