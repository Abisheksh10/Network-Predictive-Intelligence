import os
import json
from datetime import datetime
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
        "X-Title": "Telecom-NOC-Operations",
    }

client = anthropic.Anthropic(**client_kwargs)

SYSTEM_PROMPT = """You are an analytical assistant embedded inside a Telecom Network Operations Centre (NOC).
Answer the user's investigation query strictly according to the provided instructions.

CRITICAL RULES:
- Never use the word 'congestion' as an assertion.
- Activity metrics are proportional interaction units, not call counts, SMS quantities, or MB/GB.
- Structure your answer in EXACTLY three sections:
  CURRENT EVIDENCE
  HISTORICAL EVIDENCE
  UNCERTAINTY
- In UNCERTAINTY, evaluate how data pipeline quality and unobserved variables constrain your conclusions.
"""

# ============================================================================
# CONTEXT PAYLOADS
# ============================================================================

# 1. DUMP-EVERYTHING CONTEXT (Uncurated, raw rows, logs, full noise)
DUMP_EVERYTHING_CONTEXT = """
Raw telemetry rows for Grid 4821 and surrounding cells:
datetime,CellID,countrycode,smsin,smsout,callin,callout,internet
2013-11-01 00:00:00,4821,39,0.12,0.45,0.01,0.00,12.4
2013-11-01 01:00:00,4821,39,0.05,0.10,0.00,0.00,8.1
2013-11-01 02:00:00,4821,39,0.01,0.00,0.00,0.00,4.2
2013-11-01 03:00:00,4821,39,0.00,0.02,0.00,0.00,2.1
... [simulated 1,500 lines of hourly unaggregated raw rows across country codes 0, 39, 44, 49] ...
2013-11-07 22:00:00,4821,39,1.45,3.20,0.85,1.10,210.4
2013-11-07 23:00:00,4821,39,1.80,3.90,1.12,1.40,246.74

Database dump logs:
[2026-09-05 12:00:01] INFO Connection pool initialized max_size=10
[2026-09-05 12:00:02] DEBUG Executing SQL SELECT * FROM fact_network_activity
[2026-09-05 12:00:03] DEBUG Row fetch complete 124500 rows returned

Current Anomaly score: -0.7138. Risk: 0.12.
"""

# 2. CURATED EVIDENCE PACKAGE (Pre-aggregated, structured, healthy pipeline)
CURATED_HEALTHY_CONTEXT = """
EVIDENCE PACKAGE: Grid 4821 Investigation
Window AS_OF: 2013-11-07T23:00:00

1. CURRENT INTERVAL METRICS:
- Grid ID: 4821 (Milan Central-West Sector, lat: 45.4593, lon: 9.0731)
- Timestamp: 2013-11-07T23:00:00
- Total Activity: 254.97 interaction units
- Internet Share: 82.67% (210.78 units)
- Calls Total: 28.52 interaction units | SMS Total: 15.67 interaction units
- Baseline Average Activity: 360.25 interaction units
- Growth Rate vs Baseline: -0.0225 (-2.25%)
- Peak Ratio: 1.8508 | Activity Variability: 0.4183

2. SUMMARIZED RECENT HISTORY (Last 7 Days / 168 Hours):
- Mean Hourly Activity: 360.25 units (Min: 42.10 at 04:00, Max: 666.82 at 19:00)
- Historical Intervals in Similar Range (240 - 270 units): Occurred 22 times (13.1% of all hours, typical for late-evening wind-down).
- Historical Trend: Activity follows a regular diurnal cycle with no unexplained step-level shifts.

3. PRIOR ALERTS & MODEL SCORES:
- Historical Rule Alerts (Last 7 days): 0 alerts for Grid 4821.
- Current Isolation Forest Anomaly Score: -0.7138 (Classification: NORMAL, well above threshold -0.15).
- Predicted Risk Score: 0.12 (LOW RISK).

4. DATA PIPELINE QUALITY STATUS (API 6 / DE7):
- Run ID: manual__2026-09-05T12:00:00 (Run at: 2026-09-05T12:05:00)
- Pipeline Health: HEALTHY (Status: SUCCESS)
- Ingested: 124,500 rows | Quarantined/Rejected: 0 rows | Nulls Handled: 0 | Published: 124,500 rows
- Analytics Layer Freshness: NOMINAL (Synced with AS_OF: 2013-11-07T23:00:00)
- Reasons: None
"""

# 3. CURATED EVIDENCE PACKAGE (Unhealthy Pipeline — Injected DE8 Fault)
CURATED_UNHEALTHY_CONTEXT = """
EVIDENCE PACKAGE: Grid 4821 Investigation
Window AS_OF: 2013-11-07T23:00:00

1. CURRENT INTERVAL METRICS:
- Grid ID: 4821
- Timestamp: 2013-11-07T23:00:00
- Total Activity: 254.97 interaction units
- Baseline Average Activity: 360.25 interaction units
- Anomaly Score: -0.7138 (NORMAL)

2. SUMMARIZED RECENT HISTORY:
- Mean Hourly Activity: 360.25 units
- Diurnal cycle normal.

3. PRIOR ALERTS:
- Prior Rule Alerts: 0

4. DATA PIPELINE QUALITY STATUS (API 6 / DE8 INJECTED FAULT):
- Run ID: test_failure_run (Run at: 2026-09-05T12:00:00)
- Pipeline Health: UNHEALTHY (Status: FAILED)
- Ingested: 124,500 rows | Quarantined/Rejected: 18,200 rows | Handled Nulls: 4,120
- Analytics Layer Freshness: STALE (Pipeline aborted before warehouse reconciliation)
- Failure Reasons:
  * "Negative activity values detected in internet telemetry column for batch 2013-11-07"
  * "Task 'spark_processing' failed with status 'SKIPPED'"
"""

INVESTIGATION_PROMPT = """Investigate an unusual activity pattern at Grid 4821.
I am providing an evidence package.

Answer in exactly three sections:
CURRENT EVIDENCE      what is true right now, with figures
HISTORICAL EVIDENCE   whether this has happened before, and how often
UNCERTAINTY           what you do NOT know, including anything the pipeline status makes doubtful

If the pipeline status indicates rejected rows, handled nulls or a stale analytics layer, treat that as material and say how it limits the conclusion.

Do not restate raw rows back to me. Do not claim congestion.
"""

def run_experiment(title: str, context_text: str):
    print("\n" + "=" * 80)
    print(f"EXPERIMENT RUN: {title}")
    print("=" * 80)

    prompt = f"{context_text}\n\n---\n\n{INVESTIGATION_PROMPT}"
    
    response = client.messages.create(
        model=MODEL,
        system=SYSTEM_PROMPT,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    result_text = ""
    for block in response.content:
        if isinstance(block, dict) and block.get("type") == "text":
            result_text += block.get("text", "")
        elif getattr(block, "type", None) == "text":
            result_text += getattr(block, "text", "")

    print(result_text.strip())
    return result_text


if __name__ == "__main__":
    # Run 1: Dump-Everything
    run_experiment("1. DUMP EVERYTHING (UNSTRUCTURED RAW NOISE)", DUMP_EVERYTHING_CONTEXT)

    # Run 2: Curated Context (Healthy Pipeline)
    run_experiment("2. CURATED EVIDENCE PACKAGE (HEALTHY PIPELINE)", CURATED_HEALTHY_CONTEXT)

    # Run 3: Curated Context (Unhealthy Pipeline - DE8 Fault Injected)
    run_experiment("3. CURATED EVIDENCE PACKAGE (UNHEALTHY PIPELINE - FAULT INJECTED)", CURATED_UNHEALTHY_CONTEXT)