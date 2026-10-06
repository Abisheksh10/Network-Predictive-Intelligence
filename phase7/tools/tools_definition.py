from datetime import datetime
import requests

BACKEND_URL = "http://localhost:8000"


def get_network_summary(as_of: str | None = None):
    params = {}

    if as_of:
        params["as_of"] = as_of

    response = requests.get(
        f"{BACKEND_URL}/network/summary",
        params=params,
        timeout=10
    )

    response.raise_for_status()

    return {
        "tool": "get_network_summary",
        "status": "success",
        "data": response.json()
    }


def get_grid_activity(
    grid_id: int,
    date: str | None = None,
    hour: int | None = None,
    as_of: str | None = None
):
    if grid_id < 1 or grid_id > 10000:
        return {
            "tool": "get_grid_activity",
            "status": "failed",
            "error": "grid_id must be between 1 and 10000"
        }

    if hour is not None and (hour < 0 or hour > 23):
        return {
            "tool": "get_grid_activity",
            "status": "failed",
            "error": "hour must be between 0 and 23"
        }

    params = {
        "grid_id": grid_id
    }

    if date:
        params["date"] = date

    if hour is not None:
        params["hour"] = hour

    if as_of:
        params["as_of"] = as_of

    response = requests.get(
        f"{BACKEND_URL}/network/grid/{grid_id}",
        params=params,
        timeout=10
    )

    response.raise_for_status()

    return {
        "tool": "get_grid_activity",
        "status": "success",
        "data": response.json()
    }


def get_grid_features(
    grid_id: int,
    as_of: str | None = None
):
    if grid_id < 1 or grid_id > 10000:
        return {
            "tool": "get_grid_features",
            "status": "failed",
            "error": "grid_id must be between 1 and 10000"
        }

    params = {}

    if as_of:
        params["as_of"] = as_of

    response = requests.get(
        f"{BACKEND_URL}/network/grid/{grid_id}/features",
        params=params,
        timeout=10
    )

    response.raise_for_status()

    return {
        "tool": "get_grid_features",
        "status": "success",
        "data": response.json()
    }


def get_anomaly_score(
    grid_id: int,
    timestamp: str
):
    if grid_id < 1 or grid_id > 10000:
        return {
            "tool": "get_anomaly_score",
            "status": "failed",
            "error": "grid_id must be between 1 and 10000"
        }

    try:
        datetime.fromisoformat(timestamp)
    except ValueError:
        return {
            "tool": "get_anomaly_score",
            "status": "failed",
            "error": (
                "Invalid timestamp. Use ISO format such as "
                "2026-09-03T14:00:00"
            )
        }

    try:
        response = requests.post(
            f"{BACKEND_URL}/network/anamoly_score",
            params={
                "grid_id": grid_id,
                "timestamp": timestamp
            },
            timeout=10
        )

        response.raise_for_status()

        return {
            "tool": "get_anomaly_score",
            "status": "success",
            "data": response.json()
        }

    except requests.RequestException as error:
        return {
            "tool": "get_anomaly_score",
            "status": "failed",
            "error": str(error)
        }


def get_total_activity(
    grid_id: int
):
    if grid_id < 1 or grid_id > 10000:
        return {
            "tool": "get_total_activity",
            "status": "failed",
            "error": "grid_id must be between 1 and 10000"
        }

    try:
        response = requests.post(
            f"{BACKEND_URL}/network/total_activity",
            params={
                "grid_id": grid_id
            },
            timeout=10
        )

        response.raise_for_status()

        return {
            "tool": "get_total_activity",
            "status": "success",
            "data": response.json()
        }

    except requests.RequestException as error:
        return {
            "tool": "get_total_activity",
            "status": "failed",
            "error": str(error)
        }