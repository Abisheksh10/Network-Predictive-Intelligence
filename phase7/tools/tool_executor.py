import requests

BACKEND_BASE_URL = "http://127.0.0.1:8000"

def execute_tool(tool_name: str, tool_input: dict) -> dict:
    session = requests.Session()

    try:
        if tool_name == "get_pipeline_status":
            resp = session.get(f"{BACKEND_BASE_URL}/pipeline/status", timeout=10)

        elif tool_name == "get_network_summary":
            resp = session.get(f"{BACKEND_BASE_URL}/network/summary", params=tool_input, timeout=10)

        elif tool_name == "get_hotspots":
            resp = session.get(f"{BACKEND_BASE_URL}/network/hotspots", params=tool_input, timeout=10)

        elif tool_name == "get_grid_activity":
            grid_id = tool_input.get("grid_id")
            params = {k: v for k, v in tool_input.items() if k != "grid_id"}
            resp = session.get(f"{BACKEND_BASE_URL}/network/grid/{grid_id}", params=params, timeout=10)

        elif tool_name == "get_grid_features":
            grid_id = tool_input.get("grid_id")
            params = {k: v for k, v in tool_input.items() if k != "grid_id"}
            resp = session.get(f"{BACKEND_BASE_URL}/network/grid/{grid_id}/features", params=params, timeout=10)

        elif tool_name == "get_anomaly_score":
            resp = session.post(f"{BACKEND_BASE_URL}/network/anamoly_score", params=tool_input, timeout=10)

        elif tool_name == "get_grid_location":
            grid_id = tool_input.get("grid_id")
            resp = session.get(f"{BACKEND_BASE_URL}/network/grid/{grid_id}/location", timeout=10)

        else:
            return {"error": f"Unknown tool: {tool_name}"}

        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.RequestException as exc:
        return {
            "error": f"Tool execution failed for {tool_name}",
            "details": str(exc),
            "status_code": getattr(exc.response, "status_code", None)
        }