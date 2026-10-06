import os
import re
from pathlib import Path
from typing import Dict, Any
from dotenv import dotenv_values
import anthropic

CL2_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = CL2_DIR / "prompts"
ENV_PATH = CL2_DIR.parent / ".env"

# Shared token cap
GLOBAL_MAX_TOKENS = 800

# ----------------------------------------------------------------------------
# 1. TEMPLATE LOADER (Versioned files only, never inlined)
# ----------------------------------------------------------------------------
def load_template(name: str, **kwargs: Any) -> str:
    template_file = PROMPTS_DIR / f"{name}.txt"
    if not template_file.exists():
        raise FileNotFoundError(f"Template '{name}' not found under {PROMPTS_DIR}")

    with open(template_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Validate all placeholders are supplied
    placeholders = re.findall(r"\{([a-zA-Z0-9_]+)\}", content)
    for p in placeholders:
        if p not in kwargs:
            raise ValueError(f"Missing required parameter '{p}' for template '{name}'")

    return content.format(**kwargs)

# ----------------------------------------------------------------------------
# 2. SECURITY CHECKLIST ENFORCEMENT
# ----------------------------------------------------------------------------
def check_for_secret_leakage(text: str) -> None:
    """Scans text against all active values in .env. Throws error if any leaked."""
    if not ENV_PATH.exists():
        return

    secrets = dotenv_values(ENV_PATH)
    for key, val in secrets.items():
        if val and len(str(val)) >= 6:
            if str(val) in text:
                raise PermissionError(
                    f"SECURITY ALERT: Blocked prompt containing secret value from .env (Key: {key})"
                )

def execute_safe_claude_call(system_prompt: str, user_prompt: str) -> str:
    """Executes call with secret check, token cap, and context prepend."""
    # 1. Enforce Secret Leakage Guard
    check_for_secret_leakage(system_prompt)
    check_for_secret_leakage(user_prompt)

    # 2. Load Client
    env_vars = dotenv_values(ENV_PATH)
    api_key = env_vars.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    base_url = env_vars.get("ANTHROPIC_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    model = env_vars.get("ANTHROPIC_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    client_kwargs = {"api_key": api_key}
    if base_url and "openrouter" in base_url:
        client_kwargs["base_url"] = base_url
        client_kwargs["default_headers"] = {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Telecom-NOC-CL2",
        }
    elif base_url:
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)

    # 3. Call with capped token usage
    resp = client.messages.create(
        model=model,
        max_tokens=GLOBAL_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return resp.content[0].text.strip()