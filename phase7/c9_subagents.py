import json
import os
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
        "X-Title": "Telecom-NOC-Subagents",
    }

client = anthropic.Anthropic(**client_kwargs)
API_BASE = "http://127.0.0.1:8000"

# ----------------------------------------------------------------------------
# 1. SPECIALIST DATA FETCHERS (Direct deterministic API calls - 0 tokens)
# ----------------------------------------------------------------------------

def fetch_data_pipeline_evidence():
    r = requests.get(f"{API_BASE}/pipeline/status", timeout=5)
    return r.json() if r.status_code == 200 else {"error": "Pipeline status unavailable"}

def fetch_network_evidence(grid_id: int):
    activity = requests.get(f"{API_BASE}/network/grid/{grid_id}", timeout=5).json()
    neighbours = requests.get(f"{API_BASE}/network/grid/{grid_id}/neighbours?limit=4", timeout=5).json()
    location = requests.get(f"{API_BASE}/network/grid/{grid_id}/location", timeout=5).json()
    return {"activity": activity, "neighbours": neighbours, "location": location}

def fetch_ml_evidence(grid_id: int, timestamp: str = "2013-11-07T23:00:00"):
    features = requests.get(f"{API_BASE}/network/grid/{grid_id}/features", timeout=5).json()
    anomaly = requests.post(f"{API_BASE}/network/anamoly_score?grid_id={grid_id}&timestamp={timestamp}", timeout=5).json()
    risk = requests.post(f"{API_BASE}/model/predict_risk", json={"grid_id": grid_id}, timeout=5).json()
    return {"features": features, "anomaly": anomaly, "risk": risk}

def fetch_api_health_evidence(grid_id: int):
    endpoints = [
        f"/pipeline/status",
        f"/network/grid/{grid_id}",
        f"/network/grid/{grid_id}/features",
        f"/network/grid/{grid_id}/location"
    ]
    results = {}
    for ep in endpoints:
        resp = requests.get(f"{API_BASE}{ep}", timeout=5)
        results[ep] = {"status_code": resp.status_code, "latency_ms": round(resp.elapsed.total_seconds() * 1000, 1)}
    return results

# ----------------------------------------------------------------------------
# 2. SPECIALIST SUBAGENTS (Each runs 1 focused evaluation prompt)
# ----------------------------------------------------------------------------

def run_subagent(name: str, scope_prompt: str, evidence: dict) -> str:
    print(f"  --> Running {name}...")
    prompt = f"{scope_prompt}\n\nEVIDENCE:\n{json.dumps(evidence, indent=2)}\n\nReport strictly within your scope in 2-3 sentences. State findings and your specific uncertainty."
    
    resp = client.messages.create(
        model=MODEL,
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text.strip()

# ----------------------------------------------------------------------------
# 3. SUPERVISOR SYNTHESIZER
# ----------------------------------------------------------------------------

def run_supervisor(specialist_reports: dict, grid_id: int) -> str:
    print("  --> Supervisor synthesizing specialist findings...")
    
    supervisor_prompt = f"""You are the NOC Lead Supervisor. You have received reports from 4 narrow specialists regarding Grid {grid_id}.
    
SPECIALIST REPORTS:
{json.dumps(specialist_reports, indent=2)}

Synthesize into ONE final brief with EXACTLY these four sections:
1. FINAL SEVERITY: [Must be strictly NORMAL, ATTENTION, HIGH, or INSUFFICIENT EVIDENCE]
2. SPECIALIST EVIDENCE ATTRIBUTION: Bulleted summary citing which specialist provided each fact.
3. CONFLICTS & DISAGREEMENTS: Explicitly highlight any tension or disagreement between specialists (e.g. ML anomaly score says NORMAL while rule alerts/activity surges show ATTENTION, or pipeline staleness limits ML confidence). Do NOT smooth over disagreements.
4. RECOMMENDED NEXT CHECKS: Concrete human diagnostic steps.

RULES: Telemetry measures are interaction units (never counts or MB). NEVER claim congestion.
"""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": supervisor_prompt}]
    )
    return resp.content[0].text.strip()

def main():
    grid_id = 4821
    print("=" * 70)
    print(f"C9: MULTI-AGENT INVESTIGATION FOR GRID {grid_id}")
    print("=" * 70)

    # 1. Collect evidence deterministically
    p_data = fetch_data_pipeline_evidence()
    n_data = fetch_network_evidence(grid_id)
    m_data = fetch_ml_evidence(grid_id)
    a_data = fetch_api_health_evidence(grid_id)

    # 2. Execute 4 Specialists
    reports = {}
    reports["Data Pipeline Agent"] = run_subagent(
        "Data Pipeline Agent",
        "Role: Data Pipeline Specialist. Evaluate pipeline status, row quality, and whether data is trustworthy. Do NOT comment on activity trends.",
        p_data
    )
    reports["Network Analysis Agent"] = run_subagent(
        "Network Analysis Agent",
        "Role: Network Trend Specialist. Evaluate activity vs historical baseline and neighbouring cells. Do NOT claim congestion. Activity is in interaction units.",
        n_data
    )
    reports["ML Analysis Agent"] = run_subagent(
        "ML Analysis Agent",
        "Role: ML Specialist. Evaluate Isolation Forest anomaly score, model risk score, and feature metrics. State if model detects an anomaly.",
        m_data
    )
    reports["API Health Agent"] = run_subagent(
        "API Health Agent",
        "Role: API Infrastructure Specialist. Evaluate latency, status codes, and serving layer availability.",
        a_data
    )

    # 3. Run Supervisor Aggregator
    print("\n" + "-" * 70)
    final_report = run_supervisor(reports, grid_id)
    print(f"\n{final_report}\n")

if __name__ == "__main__":
    main()