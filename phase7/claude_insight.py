import json
import os
from typing import List, Dict, Any
import anthropic
from dotenv import load_dotenv

from tools.tools_description import tools
from tools.tool_executor import execute_tool

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL")

if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY is not configured")

if not MODEL:
    raise ValueError("ANTHROPIC_MODEL is not configured")

client_kwargs = {"api_key": API_KEY}
if BASE_URL:
    client_kwargs["base_url"] = BASE_URL
    client_kwargs["default_headers"] = {
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Telecom-NOC-Operations",
    }

client = anthropic.Anthropic(**client_kwargs)

SYSTEM_PROMPT = """You are the Network Operations Assistant for the Milan telecom grid.
You answer network operations questions strictly by invoking available tools to retrieve factual telemetry.

MANDATORY OPERATIONAL PROTOCOLS:
1. PIPELINE STATUS FIRST:
   - Before asserting any situation as fact, invoke `get_pipeline_status()`.
   - You MUST explicitly state whether the underlying telemetry data is currently trustworthy, report the pipeline health status, and state the AS_OF timestamp.

2. EXPLAIN GRID PROTOCOL:
   - When asked to explain a grid (e.g., Grid 4821), you MUST invoke ALL FOUR of these tools before answering:
     a. `get_grid_location(grid_id=<id>)` -> identify where it is in Milan (coordinates).
     b. `get_grid_activity(grid_id=<id>)` -> retrieve current interaction volume and latest timestamp.
     c. `get_grid_features(grid_id=<id>)` -> retrieve baseline average, peak ratio, growth, variability.
     d. `get_anomaly_score(grid_id=<id>, timestamp=<retrieved_timestamp>)` -> retrieve anomaly z-score.
   - Do NOT guess future dates (2023/2024); omit date filters to default to the nominal November 2013 operational window.

3. TOOL ATTRIBUTION & TRANSPARENCY:
   - Explicitly cite which tool produced each number (e.g., "[Source: get_grid_features]").
   - If any tool call fails, explicitly name the failed tool and state what you CANNOT conclude. Never invent or substitute estimates.

4. SEPARATION OF EVIDENCE & INFERENCE:
   - Strictly separate what is OBSERVED (factual metrics from tools) from what is INFERRED (operational hypotheses, possibilities).
   - Label all interpretations with phrases like "This suggests" or "Hypothesis:".

5. NEGATIVE CONSTRAINTS:
   - NEVER use the word 'congestion' as an assertion under any circumstances. We monitor activity volume, not line capacity.
   - Activity measures are proportional interaction units, NOT call counts, SMS quantities, or Megabytes (MB/GB).
"""


def run_agent_turn(messages: List[Dict[str, Any]]) -> str:
    """
    Executes one conversational turn through the tool-calling loop until
    the model emits its final textual response.
    """
    iteration = 0
    max_iterations = 8

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model=MODEL,
            system=SYSTEM_PROMPT,
            max_tokens=1500,
            tools=tools,
            messages=messages
        )

        assistant_content = response.content
        messages.append({
            "role": "assistant",
            "content": assistant_content
        })

        tool_results = []

        for block in assistant_content:
            block_type = getattr(block, "type", None) if hasattr(block, "type") else (block.get("type") if isinstance(block, dict) else None)

            if block_type != "tool_use":
                continue

            if isinstance(block, dict):
                tool_name = block.get("name")
                tool_input = block.get("input", {})
                tool_id = block.get("id")
            else:
                tool_name = getattr(block, "name", None)
                tool_input = getattr(block, "input", {})
                tool_id = getattr(block, "id", None)

            print(f"  [Tool Call] {tool_name}({tool_input})")
            result = execute_tool(tool_name, tool_input)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, ensure_ascii=False, default=str)
            })

        # If no tools were invoked, extract final narrative synthesis
        if not tool_results:
            text_blocks = []
            for block in response.content:
                if isinstance(block, dict):
                    if block.get("type") == "text" and block.get("text"):
                        text_blocks.append(block["text"])
                    elif "text" in block and block["text"]:
                        text_blocks.append(block["text"])
                else:
                    text_val = getattr(block, "text", None)
                    if text_val:
                        text_blocks.append(text_val)

            combined_text = "\n".join(text_blocks).strip()
            if combined_text:
                return combined_text

            if hasattr(response, "text") and response.text:
                return response.text

            # If model concluded tool calls without outputting text, prompt synthesis
            messages.append({
                "role": "user",
                "content": "Synthesize the gathered tool evidence into your final response following all operational constraints."
            })
            continue

        # Feed tool execution responses back as the next turn
        messages.append({
            "role": "user",
            "content": tool_results
        })

    raise RuntimeError("Agent turn exceeded maximum allowed tool loop iterations.")


def main():
    print("=" * 70)
    print("C2: CLAUDE NETWORK OPERATIONS ASSISTANT MULTI-TURN SESSION")
    print("=" * 70)

    conversation_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------------
    # Turn 1: Initial Situation Request
    # ------------------------------------------------------------------------
    q1 = "Which areas need attention right now?"
    print(f"\n[User Q1]: {q1}\n")
    conversation_history.append({"role": "user", "content": q1})
    a1 = run_agent_turn(conversation_history)
    print(f"\n[Assistant A1]:\n{a1}\n")

    # ------------------------------------------------------------------------
    # Turn 2: Follow-Up Grid Drilldown (Exact C2 Syllabus Prompt)
    # ------------------------------------------------------------------------
    q2 = (
        "Explain Grid 4821. Gather the grid activity, features, anomaly score and "
        "location before answering. Tell me where it is in Milan, what the evidence shows, "
        "what it might mean, and what I should check next. Separate observed evidence from inference."
    )
    print("-" * 70)
    print(f"\n[User Q2 (Follow-up)]: {q2}\n")
    conversation_history.append({"role": "user", "content": q2})
    a2 = run_agent_turn(conversation_history)
    print(f"\n[Assistant A2]:\n{a2}\n")


if __name__ == "__main__":
    main()