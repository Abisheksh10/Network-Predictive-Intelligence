from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_HIGH_SURGE_PAYLOAD = {
    "grid_id": 5161,
    "avg_activity": 9827.03,
    "activity_growth": 0.45,
    "active_hours": 24,
    "peak_ratio": 2.85,
    "variability": 0.45,
    "internet_share": 0.94
}

SAMPLE_LOW_ACTIVITY_PAYLOAD = {
    "grid_id": 100,
    "avg_activity": 12.50,
    "activity_growth": -0.15,
    "active_hours": 12,
    "peak_ratio": 1.10,
    "variability": 0.05,
    "internet_share": 0.30
}


def test_ml5_acceptance():
    print("\n" + "=" * 60)
    print("RUNNING ML5 REAL MODEL INFERENCE ACCEPTANCE TESTS")
    print("=" * 60)

    # 1. High Activity Payload produces high risk score and real model version
    resp_high = client.post("/network/predict-risk", json=SAMPLE_HIGH_SURGE_PAYLOAD)
    assert resp_high.status_code == 200, f"Expected 200, got {resp_high.status_code}"
    data_high = resp_high.json()

    print(f"High Surge Output: {data_high}")
    assert data_high["grid_id"] == 5161
    assert data_high["model_version"] == "v1.0.0-logistic-regression"
    assert "stub" not in data_high["model_version"].lower(), "model_version must NOT be a stub!"
    assert data_high["risk_level"] in ["HIGH", "CRITICAL"]
    assert "Real ML inference executed" in data_high["explanation_note"]
    print("Criterion 1 (High activity payload scored with real model version & attribution): PASS")

    # 2. Low Activity Payload produces LOW risk level
    resp_low = client.post("/network/predict-risk", json=SAMPLE_LOW_ACTIVITY_PAYLOAD)
    assert resp_low.status_code == 200
    data_low = resp_low.json()
    print(f"Low Activity Output: {data_low}")
    assert data_low["risk_level"] == "LOW"
    assert data_low["risk_score"] < 0.25
    print("Criterion 2 (Low activity payload accurately yields LOW risk classification): PASS")

    # 3. Missing Required Field Returns 422
    incomplete_payload = SAMPLE_HIGH_SURGE_PAYLOAD.copy()
    del incomplete_payload["avg_activity"]
    resp_missing = client.post("/network/predict-risk", json=incomplete_payload)
    assert resp_missing.status_code == 422
    print("Criterion 3 (Missing required field returns HTTP 422): PASS")

    print("\nALL ML5 ACCEPTANCE CRITERIA PASSED SUCCESSFULLY.")
    print("=" * 60)


if __name__ == "__main__":
    test_ml5_acceptance()