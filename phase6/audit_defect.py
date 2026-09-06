import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
)
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

AUDIT_TOOL_SCHEMA = {
    "name": "report_findings",
    "description": "Structured findings report identifying training-serving skew between train_ml3.py and predict.py.",
    "input_schema": {
        "type": "object",
        "properties": {
            "defect_detected": {"type": "boolean"},
            "defect_type": {"type": "string", "enum": ["training_serving_skew", "data_leakage", "syntax_error"]},
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

def run_audit():
    # Adjust paths if files are in parent or current folder
    train_path = "train_ml3.py" if os.path.exists("train_ml3.py") else os.path.join("..", "phase6", "train_ml3.py")
    predict_path = "predict.py" if os.path.exists("predict.py") else os.path.join("..", "phase6", "predict.py")

    with open(train_path, "r", encoding="utf-8") as f:
        train_code = f.read()

    with open(predict_path, "r", encoding="utf-8") as f:
        predict_code = f.read()

    prompt = f"""Audit these two scripts for feature consistency.
Compare the feature extraction and columns in train_ml3.py against what predict.py actually builds.

=== TRAIN_ML3.PY ===
{train_code}

=== PREDICT.PY ===
{predict_code}

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
    print("CL1: AUDIT DEFECT FINDINGS (FORCED TOOL CHOICE)")
    print("=" * 70)
    print(json.dumps(findings, indent=2))

    assert findings["defect_detected"] is True
    assert findings["retraining_recommended"] is False
    print("\n✓ Tool-choice validation passed: Isolated inference skew without recommending retraining.")

if __name__ == "__main__":
    run_audit()