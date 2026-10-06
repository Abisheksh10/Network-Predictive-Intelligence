from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)


def test_predict_risk_real_model():
    print("\n--- Test 1: Real Model Inference Endpoint ---")
    payload = {
        "grid_id": 5161,
        "avg_activity": 1065.38,
        "activity_growth": 0.35,
        "active_hours": 168,
        "peak_ratio": 2.85,
        "variability": 0.45,
        "internet_share": 0.94
    }

    response = client.post("/network/predict-risk", json=payload)
    assert response.status_code == 200, f"Error: {response.text}"
    
    data = response.json()
    print("Inference Response Payload:")
    print(data)

    # Acceptance Criteria Checks
    assert "model_version" in data
    assert data["model_version"] == "v1.0.0-logistic-baseline", f"Expected real model version, got {data['model_version']}"
    assert 0.0 <= data["risk_score"] <= 1.0
    assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert "feature_timestamp" in data
    assert "v0.1.0-stub" not in data["model_version"], "Stub version tag still present!"
    print("Criterion 1 (model_version reflects real model, not stub): PASS")
    print("Criterion 2 (Inference score and schema validated): PASS")


def test_predict_risk_boundary_validation():
    print("\n--- Test 2: Input Feature Boundary Validation ---")
    # Invalid grid_id out of bounds
    invalid_payload = {
        "grid_id": 99999,
        "avg_activity": 100.0,
        "activity_growth": 0.1,
        "active_hours": 24,
        "peak_ratio": 1.5,
        "variability": 0.2,
        "internet_share": 0.8
    }
    res = client.post("/network/predict-risk", json=invalid_payload)
    assert res.status_code == 422, "Expected Pydantic 422 Validation Error on out-of-bounds grid"
    print("Criterion 3 (Pydantic contract validation enforced): PASS")


if __name__ == "__main__":
    test_predict_risk_real_model()
    test_predict_risk_boundary_validation()
    print("\n✅ ALL ML5 REGRESSION TESTS PASSED.")