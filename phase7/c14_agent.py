import os
import json
import sys
from typing import Any, Dict, List
import requests
import anthropic
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL")

client_kwargs = {"api_key": API_KEY}
if BASE_URL:
    client_kwargs["base_url"] = BASE_URL
    client_kwargs["default_headers"] = {
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Telecom-NOC-Agent-SDK",
    }

client = anthropic.Anthropic(**client_kwargs)
API_BASE = "http://127.0.0.1:8000"

# Failure simulation toggle
DISABLED_TOOL = os.getenv("SIMULATE_DISABLED_TOOL", None)
SIMULATE_PIPELINE_UNHEALTHY = os.getenv("SIMULATE_PIPELINE_UNHEALTHY", "0") == "1"

# ----------------------------------------------------------------------------
# 1. TOOL IMPLEMENTATIONS (With graceful degradation & error handling)
# ----------------------------------------------------------------------------

def call_pipeline_status() -> Dict[str, Any]:
    if DISABLED_TOOL == "pipeline_status":
        return {"error": "TOOL_UNAVAILABLE: pipeline_status service endpoint down"}
    if SIMULATE_PIPELINE_UNHEALTHY:
        return {
            "healthy": False,
            "reasons": ["Grain check duplicate violation", "Staleness lag exceeding 6 hours"],
            "rows_in": 124500,
            "rows_rejected": 850,
            "freshness_indicator": "STALE"
        }
    try:
        resp = requests.get(f"{API_BASE}/pipeline/status", timeout=6)
        return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"CONNECTION_FAILED: {str(e)}"}

def call_network_summary() -> Dict[str, Any]:
    if DISABLED_TOOL == "network_summary":
        return {"error": "TOOL_UNAVAILABLE: network_summary service endpoint down"}
    try:
        resp = requests.get(f"{API_BASE}/network/summary", timeout=6)
        return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"CONNECTION_FAILED: {str(e)}"}

def call_grid_activity(grid_id: int) -> Dict[str, Any]:
    if DISABLED_TOOL == "grid_activity":
        return {"error": "TOOL_UNAVAILABLE: grid_activity service endpoint down"}
    try:
        resp = requests.get(f"{API_BASE}/network/grid/{grid_id}", timeout=6)
        return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"CONNECTION_FAILED: {str(e)}"}

def call_grid_features(grid_id: int) -> Dict[str, Any]:
    if DISABLED_TOOL == "grid_features":
        return {"error": "TOOL_UNAVAILABLE: grid_features service endpoint down"}
    try:
        resp = requests.get(f"{API_BASE}/network/grid/{grid_id}/features", timeout=6)
        return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"CONNECTION_FAILED: {str(e)}"}

def call_grid_location(grid_id: int) -> Dict[str, Any]:
    if DISABLED_TOOL == "grid_location":
        return {"error": "TOOL_UNAVAILABLE: grid_location service endpoint down"}
    try:
        resp = requests.get(f"{API_BASE}/network/grid/{grid_id}/location", timeout=6)
        return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"CONNECTION_FAILED: {str(e)}"}

def call_anomaly_score(grid_id: int, timestamp: str = "2013-11-07T23:00:00") -> Dict[str, Any]:
    if DISABLED_TOOL == "anomaly_score":
        return {"error": "TOOL_UNAVAILABLE: anomaly_score service endpoint down"}
    try:
        resp = requests.post(f"{API_BASE}/network/anamoly_score?grid_id={grid_id}&timestamp={timestamp}", timeout=6)
        return resp.json() if resp.status_code == 200 else {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": f"CONNECTION_FAILED: {str(e)}"}

TOOL_DISPATCH = {
    "pipeline_status": call_pipeline_status,
    "network_summary": call_network_summary,
    "grid_activity": call_grid_activity,
    "grid_features": call_grid_features,
    "grid_location": call_grid_location,
    "anomaly_score": call_anomaly_score,
}

TOOL_SCHEMAS = [
    {
        "name": "pipeline_status",
        "description": "Exposes GET /pipeline/status. MUST BE CALLED FIRST to verify telemetry integrity and freshness.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "network_summary",
        "description": "Exposes GET /network/summary. Returns global network summary metrics.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "grid_activity",
        "description": "Exposes GET /network/grid/{grid_id}. Returns current interaction metric breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {"grid_id": {"type": "integer"}},
            "required": ["grid_id"]
        }
    },
    {
        "name": "grid_features",
        "description": "Exposes GET /network/grid/{grid_id}/features. Returns baseline features.",
        "input_schema": {
            "type": "object",
            "properties": {"grid_id": {"type": "integer"}},
            "required": ["grid_id"]
        }
    },
    {
        "name": "grid_location",
        "description": "Exposes GET /network/grid/{grid_id}/location. Returns centroid coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {"grid_id": {"type": "integer"}},
            "required": ["grid_id"]
        }
    },
    {
        "name": "anomaly_score",
        "description": "Exposes POST /network/anamoly_score. Returns Isolation Forest anomaly score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "grid_id": {"type": "integer"},
                "timestamp": {"type": "string"}
            },
            "required": ["grid_id"]
        }
    }
]

# ----------------------------------------------------------------------------
# 2. AGENT INVESTIGATION ENGINE
# ----------------------------------------------------------------------------

SYSTEM_INSTRUCTION = """You are a Headless Telecom NOC Investigation Agent.
Execute the workflow: gather -> compare -> assess -> summarize.

MANDATORY RULES:
1. Call pipeline_status FIRST before making any other tool calls.
2. If pipeline_status reports healthy=False, that MUST appear in 'uncertainty' and MUST constrain severity to ATTENTION or lower (do NOT declare HIGH on unverified data).
3. If any tool call returns an error or is unavailable, degrade gracefully: do not fabricate values or abort; record the missing tool in 'uncertainty'.
4. Telemetry metrics are proportional interaction units (NEVER counts or MB).
5. NEVER claim or assert "congestion".
6. Return your final answer strictly as a valid JSON object matching this schema:
{
  "severity": "NORMAL" | "ATTENTION" | "HIGH",
  "evidence": [
    {"claim": "<factual statement>", "value": "<metric value>", "source_tool": "<exact tool name>"}
  ],
  "uncertainty": "<what is unverified, missing, or compromised>",
  "recommended_checks": ["<human check 1>", "<human check 2>"]
}
Only output the JSON object in your final response.
"""

def run_headless_investigation(grid_id: int) -> Dict[str, Any]:
    messages = [{
        "role": "user",
        "content": f"Execute an autonomous investigation on Grid {grid_id}. Follow the gather -> compare -> assess -> summarize workflow. Remember: call pipeline_status first."
    }]

    call_sequence = []

    for turn in range(8):
        resp = client.messages.create(
            model=MODEL,
            system=SYSTEM_INSTRUCTION,
            max_tokens=900,
            tools=TOOL_SCHEMAS,
            messages=messages
        )

        tool_calls = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        
        # If no tools were called, the agent has emitted its structured summary
        # If no tools were called, the agent has emitted its structured summary
        # If no tools were called, the agent has emitted its summary
        if not tool_calls:
            text_blocks = [getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"]
            raw_text = "\n".join(text_blocks).strip()
            
            # Robust JSON extraction: handles ```json markdown blocks or mixed prose
            clean_json = raw_text
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            elif "{" in clean_json and "}" in clean_json:
                start_idx = clean_json.find("{")
                end_idx = clean_json.rfind("}") + 1
                clean_json = clean_json[start_idx:end_idx].strip()

            try:
                parsed = json.loads(clean_json)
                parsed["_tool_call_sequence"] = call_sequence
                return parsed
            except Exception:
                # If Claude output structured markdown prose instead of JSON:
                severity = "NORMAL"
                if "CRITICAL" in raw_text or "HIGH" in raw_text:
                    severity = "HIGH"
                elif "ATTENTION" in raw_text or "WARNING" in raw_text:
                    severity = "ATTENTION"

                return {
                    "severity": severity,
                    "raw_markdown": raw_text,
                    "_tool_call_sequence": call_sequence
                }
        # Handle tool executions
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for call in tool_calls:
            tool_name = call.name
            tool_args = call.input
            call_sequence.append(tool_name)
            print(f"  [AGENT ACTION] Calling tool: {tool_name}({json.dumps(tool_args)})")
            
            tool_func = TOOL_DISPATCH.get(tool_name)
            output = tool_func(**tool_args) if tool_func else {"error": "Tool not found"}
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": json.dumps(output)
            })

        messages.append({"role": "user", "content": tool_results})

    return {"error": "Max tool loop hops exceeded", "_tool_call_sequence": call_sequence}

if __name__ == "__main__":
    target_grid = int(sys.argv[1]) if len(sys.argv) > 1 else 4821
    print("=" * 70)
    print(f"C14: HEADLESS NOC INVESTIGATION AGENT FOR GRID {target_grid}")
    print("=" * 70)

    result = run_headless_investigation(target_grid)
    print("\n--- STRUCTURED INVESTIGATION BRIEF ---")
    print(json.dumps(result, indent=2))