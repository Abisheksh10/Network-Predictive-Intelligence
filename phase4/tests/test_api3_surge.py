#c5 done by claude code
from fastapi.testclient import TestClient
from main import app
from schemas import SurgeGridItem

client = TestClient(app)


def test_api3_surge_acceptance():
    print("\n" + "=" * 60)
    print("RUNNING API3 SURGE ACCEPTANCE TESTS")
    print("=" * 60)

    # ------------------------------------------------------------------------
    # 1. LIMIT RESPECTED EXACTLY
    # ------------------------------------------------------------------------
    print("\n--- Test 1: Limit Enforcement ---")
    for req_limit in [5, 10, 20]:
        resp = client.get(f"/network/hotspots/surge?limit={req_limit}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["grids"]) == req_limit
        assert data["total_grids_returned"] == req_limit
    print("Criterion 1 (limit parameter respected exactly): PASS")

    resp_bounds_low = client.get("/network/hotspots/surge?limit=0")
    resp_bounds_high = client.get("/network/hotspots/surge?limit=1001")
    assert resp_bounds_low.status_code == 422
    assert resp_bounds_high.status_code == 422
    print("Criterion 1b (out-of-bounds limit rejected with 422): PASS")

    # ------------------------------------------------------------------------
    # 2. NO BANNED TERMINOLOGY IN RESPONSES OR SCHEMA
    # ------------------------------------------------------------------------
    print("\n--- Test 2: Banned Terminology Check ---")
    surge_raw_text = client.get("/network/hotspots/surge?limit=50").text.lower()
    openapi_spec_text = client.get("/openapi.json").text.lower()

    for banned in ["congestion", "calls", "messages"]:
        assert banned not in surge_raw_text, f"Banned word '{banned}' found in surge output!"
    assert "congestion" not in openapi_spec_text, "Banned word 'congestion' found in OpenAPI schema!"
    print("Criterion 2 (Banned vocabulary appears nowhere): PASS")

    # ------------------------------------------------------------------------
    # 3. DETERMINISTIC ORDERING: surge_score DESC, grid_id ASC on ties
    # ------------------------------------------------------------------------
    print("\n--- Test 3: Deterministic Ordering ---")
    call_1 = client.get("/network/hotspots/surge?limit=25").json()["grids"]
    call_2 = client.get("/network/hotspots/surge?limit=25").json()["grids"]

    assert [g["grid_id"] for g in call_1] == [g["grid_id"] for g in call_2], "Surge ordering is non-deterministic!"
    scores = [g["surge_score"] for g in call_1]
    assert scores == sorted(scores, reverse=True), "Surge scores are not sorted descending!"

    for a, b in zip(call_1, call_1[1:]):
        if a["surge_score"] == b["surge_score"]:
            assert a["grid_id"] < b["grid_id"], "Tie-break by grid_id ascending violated!"
    print("Criterion 3 (Deterministic surge_score DESC / grid_id ASC ordering verified): PASS")

    for idx, g in enumerate(call_1):
        assert g["rank"] == idx + 1, "Rank must be assigned 1..N in output order!"
    print("Criterion 3b (Rank assigned 1..N in output order): PASS")

    # ------------------------------------------------------------------------
    # 4. BASELINE SAFETY: no divide-by-zero blowups, zero baseline -> score 0.0
    # ------------------------------------------------------------------------
    print("\n--- Test 4: Baseline Safety ---")
    for g in call_1:
        assert g["baseline_activity"] >= 0.0
        if g["baseline_activity"] <= 0.0:
            assert g["surge_score"] == 0.0, "Zero/negative baseline must yield surge_score 0.0!"
    print("Criterion 4 (Non-positive baseline safely yields surge_score 0.0): PASS")

    # ------------------------------------------------------------------------
    # 5. SPATIAL BOUNDS AND GRAIN (ONE ROW PER GRID_ID)
    # ------------------------------------------------------------------------
    print("\n--- Test 5: Spatial Bounds & Grain Validation ---")
    grid_ids = [g["grid_id"] for g in call_1]
    assert len(grid_ids) == len(set(grid_ids)), "Duplicate grid_id in surge response violates one-row-per-grid grain!"
    for g in call_1:
        assert 1 <= g["grid_id"] <= 10000, f"Invalid grid_id {g['grid_id']} out of Milan bounds!"
    print("Criterion 5 (Unique grid_ids strictly within [1, 10000]): PASS")

    # ------------------------------------------------------------------------
    # 6. AS_OF RESOLVES DYNAMICALLY (NOT HARDCODED WALL-CLOCK DATE)
    # ------------------------------------------------------------------------
    print("\n--- Test 6: AS_OF Dynamic Resolution ---")
    import service
    expected_as_of = service.get_latest_available_timestamp()
    data = client.get("/network/hotspots/surge?limit=5").json()
    assert data["as_of"].startswith(expected_as_of.strftime("%Y-%m-%dT%H:%M:%S"))
    print(f"Criterion 6 (as_of resolved dynamically to warehouse MAX(timestamp): {data['as_of']}): PASS")

    # ------------------------------------------------------------------------
    # 7. FORWARD-COMPATIBLE SCHEMA PARSES CLEANLY
    # ------------------------------------------------------------------------
    print("\n--- Test 7: Schema Parity ---")
    mock_surge_payload = {
        "grid_id": 5161,
        "centroid_lon": 9.193381,
        "centroid_lat": 45.465461,
        "current_activity": 5200.5,
        "baseline_activity": 4000.0,
        "surge_score": 0.3001,
        "rank": 1
    }
    parsed_item = SurgeGridItem(**mock_surge_payload)
    assert parsed_item.surge_score == 0.3001
    print("Criterion 7 (SurgeGridItem deserializes seamlessly): PASS")

    print("\n" + "=" * 60)
    print("ALL API3 SURGE ACCEPTANCE CRITERIA PASSED SUCCESSFULLY.")
    print("=" * 60)


if __name__ == "__main__":
    test_api3_surge_acceptance()
