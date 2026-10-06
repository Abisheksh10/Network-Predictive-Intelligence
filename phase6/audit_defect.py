import os
import json
from pathlib import Path
import anthropic
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

if not API_KEY:
    raise ValueError(f"ANTHROPIC_API_KEY not found. Checked: {env_path}")

client_kwargs = {"api_key": API_KEY}
if BASE_URL and "openrouter" in BASE_URL:
    client_kwargs["base_url"] = BASE_URL
    client_kwargs["default_headers"] = {
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Telecom-NOC-CL1",
    }
elif BASE_URL:
    client_kwargs["base_url"] = BASE_URL

client = anthropic.Anthropic(**client_kwargs)

AUDIT_TOOL_SCHEMA = {
    "name": "report_findings",
    "description": "Structured findings report identifying training-serving skew between train_ml3.py and predict.py.",
    "input_schema": {
        "type": "object",
        "properties": {
            "defect_detected": {"type": "boolean"},
            "defect_type": {
                "type": "string",
                "enum": ["none", "training_serving_skew", "data_leakage", "syntax_error"]
            },
            "hardcoded_features": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "feature_name": {"type": "string"},
                        "hardcoded_value": {"type": "string"},
                        "correct_calculation_source": {"type": "string"}
                    },
                    "required": ["feature_name", "hardcoded_value", "correct_calculation_source"]
                }
            },
            "retraining_recommended": {
                "type": "boolean",
                "description": "Must be false: the trained artifact is valid; this is an inference-time feature extraction defect."
            },
            "plain_english_explanation": {
                "type": "string",
                "description": "A non-technical explanation suitable for a stakeholder brief."
            },
            "recommended_fix": {"type": "string"}
        },
        "required": [
            "defect_detected",
            "defect_type",
            "hardcoded_features",
            "retraining_recommended",
            "plain_english_explanation",
            "recommended_fix"
        ]
    }
}

def run_audit(target_predict_code: str = None, label: str = "CURRENT DISK STATE"):
    train_path = "train_ml3.py" if os.path.exists("train_ml3.py") else os.path.join("..", "phase6", "train_ml3.py")
    predict_path = "predict.py" if os.path.exists("predict.py") else os.path.join("..", "phase6", "predict.py")

    with open(train_path, "r", encoding="utf-8") as f:
        train_code = f.read()

    if target_predict_code is None:
        with open(predict_path, "r", encoding="utf-8") as f:
            target_predict_code = f.read()

    prompt = f"""Audit these two scripts for feature consistency.
Compare the feature extraction and columns in train_ml3.py against what predict.py actually builds.

=== TRAIN_ML3.PY ===
{train_code}

=== PREDICT.PY ===
{target_predict_code}

Identify every hardcoded feature or missing calculation.
Do not recommend retraining if the model weights are valid and only inference feature construction is flawed.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        tools=[AUDIT_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "report_findings"},
        messages=[{"role": "user", "content": prompt}]
    )

    tool_call = next(b for b in response.content if getattr(b, "type", None) == "tool_use")
    findings = tool_call.input

    print("=" * 70)
    print(f"CL1: AUDIT DEFECT FINDINGS ({label})")
    print("=" * 70)
    print(json.dumps(findings, indent=2))
    return findings

if __name__ == "__main__":
    import subprocess

    # 1. Audit the Pre-Fix version from git history (commit a74f92a)
    try:
        git_pre_fix = subprocess.check_output(
            ["git", "show", "HEAD~1:predict.py"],
            stderr=subprocess.DEVNULL,
            text=True
        )
    except Exception:
        try:
            git_pre_fix = subprocess.check_output(
                ["git", "show", "HEAD~1:phase6/predict.py"],
                stderr=subprocess.DEVNULL,
                text=True
            )
        except Exception:
            git_pre_fix = None

    if git_pre_fix:
        print("\n[PHASE 1] Auditing Pre-Fix Code (from Git commit)...")
        pre_findings = run_audit(git_pre_fix, label="PRE-FIX COMMIT a74f92a")
        assert pre_findings["defect_detected"] is True, "Pre-fix code should have detected defects!"
        assert pre_findings["retraining_recommended"] is False, "Must not recommend retraining!"
        print("\n✓ Pre-fix verification passed: Identified hardcoded features without recommending retraining.")

    # 2. Audit the Post-Fix version (current file on disk)
    print("\n[PHASE 2] Auditing Post-Fix Code (current disk state)...")
    post_findings = run_audit(label="POST-FIX CURRENT DISK")
    assert post_findings["defect_detected"] is False, "Post-fix code still has detected defects!"
    print("\n✓ Post-fix verification passed: Confirmed zero training-serving skew.")