import json
import requests
from typing import Any, Dict

API_BASE = "http://127.0.0.1:8000"
TIMEOUT = 15

def safe_get(endpoint: str, params: dict = None) -> Dict[str, Any]:
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"API returned status {resp.status_code}", "detail": resp.text}
    except requests.exceptions.RequestException as e:
        return {"error": f"Network/Timeout error reaching {endpoint}", "detail": str(e)}

def tool_network_summary() -> Dict[str, Any]:
    return safe_get("/network/summary")

def tool_grid_activity(grid_id: int) -> Dict[str, Any]:
    if not isinstance(grid_id, int) or grid_id < 1 or grid_id > 10000:
        return {"error": "Invalid grid_id: must be an integer between 1 and 10000"}
    return safe_get(f"/network/grid/{grid_id}")

def tool_grid_features(grid_id: int) -> Dict[str, Any]:
    if not isinstance(grid_id, int) or grid_id < 1 or grid_id > 10000:
        return {"error": "Invalid grid_id: must be an integer between 1 and 10000"}
    return safe_get(f"/network/grid/{grid_id}/features")

def tool_grid_location(grid_id: int) -> Dict[str, Any]:
    if not isinstance(grid_id, int) or grid_id < 1 or grid_id > 10000:
        return {"error": "Invalid grid_id: must be an integer between 1 and 10000"}
    return safe_get(f"/network/grid/{grid_id}/location")

def tool_hotspots(limit: int = 10) -> Dict[str, Any]:
    limit = max(1, min(limit, 100))
    return safe_get("/network/hotspots", params={"limit": limit})

def tool_alerts() -> Dict[str, Any]:
    return safe_get("/network/alerts")

def tool_pipeline_status() -> Dict[str, Any]:
    return safe_get("/pipeline/status")

TOOL_REGISTRY = {
    "network_summary": tool_network_summary,
    "grid_activity": tool_grid_activity,
    "grid_features": tool_grid_features,
    "grid_location": tool_grid_location,
    "hotspots": tool_hotspots,
    "alerts": tool_alerts,
    "pipeline_status": tool_pipeline_status,
}

MCP_TOOL_SCHEMAS = [
    {
        "name": "network_summary",
        "description": "Exposes GET /network/summary. Returns global network summary metrics.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "grid_activity",
        "description": "Exposes GET /network/grid/{grid_id}. Returns current activity breakdown for a grid.",
        "input_schema": {
            "type": "object",
            "properties": {"grid_id": {"type": "integer", "description": "Milan Grid Cell ID (1-10000)"}},
            "required": ["grid_id"]
        }
    },
    {
        "name": "grid_features",
        "description": "Exposes GET /network/grid/{grid_id}/features. Returns baseline features and metrics for a grid.",
        "input_schema": {
            "type": "object",
            "properties": {"grid_id": {"type": "integer", "description": "Milan Grid Cell ID (1-10000)"}},
            "required": ["grid_id"]
        }
    },
    {
        "name": "grid_location",
        "description": "Exposes GET /network/grid/{grid_id}/location. Returns centroid coordinates for a grid.",
        "input_schema": {
            "type": "object",
            "properties": {"grid_id": {"type": "integer", "description": "Milan Grid Cell ID (1-10000)"}},
            "required": ["grid_id"]
        }
    },
    {
        "name": "hotspots",
        "description": "Exposes GET /network/hotspots. Returns the top grids ranked by anomaly scores, activity surge, and risk alerts.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max count of items to return (default 10)"}},
            "required": []
        }
    },
    {
        "name": "alerts",
        "description": "Exposes GET /network/alerts. Returns current active operational rule alerts.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "pipeline_status",
        "description": "Exposes GET /pipeline/status. Returns ETL health, freshness, and rejected row counts.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    }
]

def handle_mcp_call(tool_name: str, arguments: dict = None) -> Any:
    if arguments is None:
        arguments = {}
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Tool {tool_name} not found in MCP registry"}
    return TOOL_REGISTRY[tool_name](**arguments)