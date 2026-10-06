import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from main import app
import service

client = TestClient(app)


def test_get_grid_location_valid():
    """Verify centroid for Grid 4821 is inside Milan bounding box and contains no polygon."""
    response = client.get("/network/grid/4821/location")
    assert response.status_code == 200
    data = response.json()

    assert data["grid_id"] == 4821
    # Milan Bounding Box roughly: Lat [45.35, 45.55], Lon [9.05, 9.30]
    assert 45.0 <= data["centroid_lat"] <= 46.0
    assert 9.0 <= data["centroid_lon"] <= 10.0
    assert "geometry_ref" in data
    # Criterion: No polygon array emitted
    assert "coordinates" not in data
    assert "geometry" not in data


def test_get_grid_location_not_found():
    """Test non-existent grid cell ID returns 404."""
    response = client.get("/network/grid/99999/location")
    assert response.status_code == 404


def test_pipeline_status_healthy():
    """Verify pipeline status returns healthy=True with matching AS_OF."""
    response = client.get("/pipeline/status")
    assert response.status_code == 200
    data = response.json()

    assert "healthy" in data
    assert "metrics" in data
    assert "as_of" in data["metrics"]
    assert data["metrics"]["as_of"].startswith("2013-11-07")


def test_pipeline_status_unhealthy_injected(tmp_path, monkeypatch):
    """
    Acceptance Criterion: /pipeline/status returns healthy: false with
    reasons after an injected DE8 failure.
    """
    fake_status = tmp_path / "pipeline_status.json"
    fake_status.write_text(json.dumps({
        "run_id": "test_failure_run",
        "run_timestamp": "2026-09-05T12:00:00",
        "pipeline_status": "FAILED",
        "healthy": False,
        "tasks": {
            "ingest_raw": "PASS",
            "validate_raw": "FAIL",
            "spark_processing": "SKIPPED"
        },
        "metrics": {
            "rows_in": 100,
            "rows_rejected": 100,
            "nulls_handled": 0,
            "rows_published": 0,
            "as_of": "2013-11-07T23:00:00"
        },
        "reasons": ["Negative activity values detected in internet column (DE8 Injected Fault)"]
    }), encoding="utf-8")

    monkeypatch.setattr(service, "STATUS_FILE_PATH", fake_status)

    response = client.get("/pipeline/status")
    assert response.status_code == 200
    data = response.json()

    assert data["healthy"] is False
    assert len(data["reasons"]) > 0
    assert any("Negative activity" in r for r in data["reasons"])


def test_neighbours_endpoint():
    """Verify spatial neighbours for cluster checks."""
    response = client.get("/network/grid/4821/neighbours?limit=4")
    assert response.status_code == 200
    data = response.json()
    assert data["grid_id"] == 4821
    assert len(data["neighbours"]) == 4
    assert data["neighbours"][0]["distance_km"] > 0