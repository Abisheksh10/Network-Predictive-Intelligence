import json
import requests
from mcp_server import handle_mcp_call, API_BASE

def verify_parity():
    checks = [
        ("pipeline_status", {}, f"{API_BASE}/pipeline/status"),
        ("alerts", {}, f"{API_BASE}/network/alerts"),
        ("hotspots", {"limit": 5}, f"{API_BASE}/network/hotspots?limit=5"),
        ("grid_activity", {"grid_id": 4821}, f"{API_BASE}/network/grid/4821"),
        ("grid_features", {"grid_id": 4821}, f"{API_BASE}/network/grid/4821/features"),
        ("grid_location", {"grid_id": 4821}, f"{API_BASE}/network/grid/4821/location"),
        ("network_summary", {}, f"{API_BASE}/network/summary"),
    ]

    print("=" * 70)
    print("VERIFYING MCP 1:1 API PARITY (CRITERION 1)")
    print("=" * 70)

    for tool_name, args, endpoint in checks:
        print(f"Testing {tool_name} -> {endpoint}...")
        mcp_res = handle_mcp_call(tool_name, args)
        api_res = requests.get(endpoint, timeout=20).json()
        assert mcp_res == api_res, f"Parity mismatch on {tool_name} vs {endpoint}"
        print(f"  [PARITY PASS] {tool_name} matches direct endpoint output.")

    print("\nSUCCESS: All 7 MCP tools pass 1:1 API parity. No intermediate logic found.")

if __name__ == "__main__":
    verify_parity()