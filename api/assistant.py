import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import anthropic

# 1. Resolve environment from root .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

if not API_KEY:
    raise RuntimeError(f"ANTHROPIC_API_KEY not configured in {env_path}")

# 2. Construct Anthropic Client ONCE at module level
client_kwargs: Dict[str, Any] = {"api_key": API_KEY}
if BASE_URL and "openrouter" in BASE_URL:
    client_kwargs["base_url"] = BASE_URL
    client_kwargs["default_headers"] = {
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Telecom-Retention-Assistant",
    }
elif BASE_URL:
    client_kwargs["base_url"] = BASE_URL

anthropic_client = anthropic.Anthropic(**client_kwargs)

router = APIRouter(prefix="/assistant", tags=["Retention AI Assistant"])

# 3. Canonical Business System Prompt with Prompt Caching
# Must exceed cache breakpoint (~1,024 tokens on Sonnet/Opus) to enable ephemeral caching.
TELECOM_RETENTION_SYSTEM_PROMPT = """You are the Lead Telecom Retention Intelligence Specialist & Revenue Operations Architect.

================================================================================
SECTION 1: BUSINESS BASELINE & SUBSCRIBER DEMOGRAPHICS
================================================================================
- Customer Base: Exactly 7,043 enrolled subscribers in the active operational cohort.
- Historical Portfolio Churn Baseline: 26.5% portfolio churn rate across preceding fiscal periods.
- Average Monthly Revenue Per User (ARPU): $64.76 baseline across blended plans.
- Contract Distributions:
  * Month-to-Month: 55.0% of cohort (~3,874 subscribers, primary churn driver).
  * One-Year Contract: 20.9% of cohort (~1,472 subscribers).
  * Two-Year Contract: 24.1% of cohort (~1,697 subscribers, lowest churn tier).
- Payment Methods:
  * Electronic Check: Highest churn correlation (churn rate ~45.3%).
  * Mailed Check: Churn rate ~19.1%.
  * Bank Transfer (Automated): Low churn baseline (~16.7%).
  * Credit Card (Automated): Low churn baseline (~15.2%).

================================================================================
SECTION 2: PRODUCT CATALOG, SERVICES & BASELINE PRICING
================================================================================
1. Phone Services:
   - Single Line Service: $20.00/mo baseline.
   - Multiple Lines: $25.00/mo baseline increment.
2. Internet Access Technologies:
   - DSL: Copper-based service, average $35.00–$45.00/mo, lower churn risk due to limited local alternatives.
   - Fiber Optic: High-speed glass fiber, $70.00–$100.00/mo, highest churn risk due to price elasticity and local carrier competition.
   - No Internet Service: Voice-only legacy subscribers ($20.00/mo).
3. Value-Added Service Add-ons (VAS):
   - Online Security: $5.00/mo (antivirus, firewall, phishing defense).
   - Online Backup: $5.00/mo (cloud data vault).
   - Device Protection Plan: $5.00/mo (hardware replacement insurance).
   - Tech Support: $8.00/mo (24/7 dedicated tier-2 desk support).
   - Streaming TV: $12.00/mo (linear IPTV bundle).
   - Streaming Movies: $12.00/mo (on-demand library).

================================================================================
SECTION 3: RETENTION LEVERS, POLICIES & INTERVENTION GUIDELINES
================================================================================
1. Contract Transition Incentives:
   - Moving a Month-to-Month subscriber to a 1-Year commitment typically reduces 12-month churn likelihood by 55-65%.
   - Price elasticity allows for monthly billing concessions up to $15.00/mo if the lifetime value (LTV) gain from contract duration exceeds margin losses.
2. Payment Method Normalization:
   - Subscribers using Electronic Checks should be prioritized for migration to Automated ACH or Credit Card auto-pay.
   - Offering a one-time $10 bill credit for enabling Auto-Pay yields a high return on investment by preventing involuntary churn.
3. Tech Support Bundling:
   - Churn in Fiber Optic accounts frequently stems from perceived technical friction during the first 6 months.
   - Proactive complimentary 6-month Tech Support vouchers resolve customer friction without eroding base plan pricing.

================================================================================
SECTION 4: STRICT NON-NEGOTIABLE OPERATIONAL INVARIANTS
================================================================================
1. NEVER INVENT CUSTOMER DATA: Do not fabricate specific subscriber names, hypothetical IDs, tenure months, or billing amounts unless explicitly supplied in prompt context. If missing, specify that verified customer attributes are required.
2. VOCABULARY ENFORCEMENT: Never use the word "congestion" to describe service degradation or network activity. Refer to "elevated localized demand", "high interaction volume", or "statistical traffic anomalies".
3. METRIC INTEGRITY: All churn probabilities must be treated as statistical estimates derived from our verified ML baseline, never deterministic guarantees.
"""
# 4. Pydantic Request / Response Schemas
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")

class AssistantChatRequest(BaseModel):
    message: str = Field(..., description="The user's latest prompt or inquiry")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Prior conversational turns")
    enable_thinking: bool = Field(default=False, description="Toggle extended/adaptive thinking mode for complex reasoning")
    thinking_budget: int = Field(default=2048, description="Budget tokens allocated for thinking (must be < max_tokens)")

class UsageMetrics(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    thinking_tokens: Optional[int] = 0

class AssistantChatResponse(BaseModel):
    reply: str
    thinking: Optional[str] = None
    model: str
    usage: UsageMetrics

# 5. POST /assistant/chat Endpoint
@router.post("/chat", response_model=AssistantChatResponse)
def assistant_chat(payload: AssistantChatRequest):
    try:
        # Assemble message history
        messages: List[Dict[str, Any]] = []
        for msg in payload.history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": payload.message})

        # Configure caching block in system prompt
        system_blocks = [
            {
                "type": "text",
                "text": TELECOM_RETENTION_SYSTEM_PROMPT.strip(),
                "cache_control": {"type": "ephemeral"}
            }
        ]

        # Call parameters
        call_params: Dict[str, Any] = {
            "model": MODEL,
            "system": system_blocks,
            "messages": messages,
        }

        if payload.enable_thinking:
            call_params["max_tokens"] = payload.thinking_budget + 1500
            call_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": payload.thinking_budget
            }
        else:
            call_params["max_tokens"] = 1024

        response = anthropic_client.messages.create(**call_params)

        # Parse text and thinking blocks
        reply_text = ""
        thinking_text = ""
        for block in response.content:
            block_type = getattr(block, "type", "")
            if block_type == "text":
                reply_text += getattr(block, "text", "")
            elif block_type == "thinking":
                thinking_text += getattr(block, "thinking", "")

        # Extract usage metrics including cache telemetry
        usage = response.usage
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        
        output_details = getattr(usage, "output_tokens_details", None)
        thinking_toks = getattr(output_details, "thinking_tokens", 0) if output_details else 0

        return AssistantChatResponse(
            reply=reply_text,
            thinking=thinking_text if payload.enable_thinking else None,
            model=response.model,
            usage=UsageMetrics(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_creation_input_tokens=cache_creation,
                cache_read_input_tokens=cache_read,
                thinking_tokens=thinking_toks
            )
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))