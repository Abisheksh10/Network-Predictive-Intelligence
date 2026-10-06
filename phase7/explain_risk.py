import os
import json
from pathlib import Path
from typing import Dict, Any
import joblib
from dotenv import load_dotenv

# Search and load .env (check phase7/.env first, then root .env)
PHASE7_DIR = Path(__file__).resolve().parent
ROOT_DIR = PHASE7_DIR.parent

env_paths = [PHASE7_DIR / ".env", ROOT_DIR / ".env"]
for ep in env_paths:
    if ep.exists():
        load_dotenv(dotenv_path=ep, override=True)
        break

API_KEY = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY")
RAW_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "").strip()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

if not API_KEY:
    raise RuntimeError("No API key found in phase7/.env or root .env")

API_KEY = API_KEY.strip().strip("'\"")

is_openrouter = (
    API_KEY.startswith("sk-or-") or 
    "openrouter" in RAW_BASE_URL.lower() or 
    "openrouter" in MODEL.lower() or
    "meta-llama" in MODEL.lower()
)

# Load production model feature coefficients
MODEL_PATH = ROOT_DIR / "phase4" / "artifacts" / "baseline_risk_model.joblib"
if not MODEL_PATH.exists():
    MODEL_PATH = ROOT_DIR / "artifacts" / "baseline_risk_model.joblib"

COEFFICIENTS = {}
if MODEL_PATH.exists():
    try:
        artifact = joblib.load(MODEL_PATH)
        lr_model = artifact.get("model")
        feat_names = artifact.get("features", [
            "avg_activity", "activity_growth", "active_hours", 
            "peak_ratio", "variability", "internet_share"
        ])
        if hasattr(lr_model, "coef_"):
            for name, coef in zip(feat_names, lr_model.coef_[0]):
                COEFFICIENTS[name] = round(float(coef), 4)
    except Exception:
        COEFFICIENTS = {
            "peak_ratio": 0.3145,
            "activity_growth": 0.2350,
            "variability": 0.2056,
            "avg_activity": 0.0431,
            "active_hours": 0.0313,
            "internet_share": -0.0014
        }
else:
    COEFFICIENTS = {
        "peak_ratio": 0.3145,
        "activity_growth": 0.2350,
        "variability": 0.2056,
        "avg_activity": 0.0431,
        "active_hours": 0.0313,
        "internet_share": -0.0014
    }

SYSTEM_PROMPT = f"""You are the Telecom NOC Predictive Intelligence Lead and Root Cause Diagnostic Engine.

PROJECT & DOMAIN CONTEXT:
1. Milan Spatial Telemetry: Grids (1-10,000) are 235m x 235m geographic cells, NOT cell towers or hardware nodes.
2. Units: Proportional interaction units (NOT counts, NOT MB/GB, NOT bandwidth).
3. Terminology Guardrail: NEVER use the word "congestion". Refer to "elevated localized demand", "traffic surge", or "statistical anomalies".
4. Model Architecture: Logistic Regression risk classifier trained to predict t+1 demand alerts.
5. Trained Feature Coefficients (Log-Odds Impact):
{json.dumps(COEFFICIENTS, indent=2)}

DIAGNOSTIC CONTRACT:
You must synthesize the evaluated features against the model's coefficients.
Explain why the model assigned this specific risk level (e.g., if peak_ratio or activity_growth is high, show how their positive coefficients drove the classification).

Format your response strictly using these 4 exact markdown sections:

### SEVERITY
<CRITICAL | ATTENTION | NORMAL> - <One-sentence clear diagnostic verdict including the probability percentage>

### EVIDENCE
- **Peak-to-Mean Ratio**: <value>x (Model Weight: {COEFFICIENTS.get('peak_ratio', '+0.3145')})
- **Growth Velocity**: <value> (Model Weight: {COEFFICIENTS.get('activity_growth', '+0.2350')})
- **Activity Variability**: <value> (Model Weight: {COEFFICIENTS.get('variability', '+0.2056')})
- **Internet Share**: <value>%
- **24h Rolling Volume**: <value> interaction units
- **Active Operational Hours**: <value>/24 hours

### INTERPRETATION
<Provide a 2-paragraph technical explanation. First paragraph: explain which specific mathematical features drove the log-odds up or down based on their weights. Second paragraph: explain the real-world operational pattern (e.g. sudden localized burst despite normal base volume, or mobile data heavy surge).>

### NEXT CHECKS
1. <Specific operational dispatch or verification check 1>
2. <Specific operational dispatch or verification check 2>
3. <Specific operational dispatch or verification check 3>
"""

def generate_risk_explanation(grid_id: int, timestamp: str, risk_score: float, risk_level: str, features: Dict[str, Any]) -> Dict[str, Any]:
    user_prompt = f"""Generate the root-cause diagnostic for Grid {grid_id} at cutoff {timestamp}.

EVALUATION PAYLOAD:
- Classified Risk Level: {risk_level}
- Risk Probability: {risk_score * 100:.1f}%
- Evaluated Feature Values:
  * avg_activity: {features.get('avg_activity', 0.0)}
  * activity_growth: {features.get('activity_growth', 0.0)}
  * active_hours: {features.get('active_hours', 24)}
  * peak_ratio: {features.get('peak_ratio', 1.0)}
  * variability: {features.get('variability', 0.0)}
  * internet_share: {features.get('internet_share', 0.0)}

Synthesize the evidence against our model weights and output the 4 sections: SEVERITY, EVIDENCE, INTERPRETATION, NEXT CHECKS.
"""

    if is_openrouter:
        # Use OpenAI SDK or requests for OpenRouter endpoint
        from openai import OpenAI
        oa_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Telecom-NOC-RCA"
            }
        )
        completion = oa_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000
        )
        narrative = completion.choices[0].message.content.strip()
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=API_KEY)
        resp = client.messages.create(
            model=MODEL,
            system=SYSTEM_PROMPT,
            max_tokens=1000,
            messages=[{"role": "user", "content": user_prompt}]
        )
        text_blocks = [getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"]
        narrative = "\n".join(text_blocks).strip()

    return {
        "grid_id": grid_id,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "narrative": narrative,
        "coefficients_used": COEFFICIENTS
    }

if __name__ == "__main__":
    print("=" * 70)
    print(f"Provider mode : {'OpenRouter (OpenAI SDK)' if is_openrouter else 'Anthropic Direct'}")
    print(f"Active Model  : {MODEL}")
    print("=" * 70)

    sample_feats = {
        "avg_activity": 12754.14,
        "activity_growth": 0.42,
        "active_hours": 24,
        "peak_ratio": 2.85,
        "variability": 0.72,
        "internet_share": 0.82
    }
    
    print("\nExecuting test diagnostic for Grid 5259...")
    out = generate_risk_explanation(5259, "2013-11-07 23:00:00", 0.7998, "CRITICAL", sample_feats)
    
    print("\n--- GENERATED C8 4-SECTION DIAGNOSTIC REPORT ---\n")
    print(out["narrative"])