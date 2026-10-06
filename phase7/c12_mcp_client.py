import os
import json
import anthropic
from dotenv import load_dotenv
from mcp_server import MCP_TOOL_SCHEMAS, handle_mcp_call

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL")

client_kwargs = {"api_key": API_KEY}
if BASE_URL:
    client_kwargs["base_url"] = BASE_URL
    client_kwargs["default_headers"] = {
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Telecom-NOC-MCP",
    }

client = anthropic.Anthropic(**client_kwargs)

SYSTEM_PROMPT = """You are a Network Operations Assistant connected to an MCP Server.
Rules:
- Telemetry values are proportional interaction units, NEVER counts or MB.
- High activity must NEVER be described as confirmed congestion.
- Always call the provided MCP tools to fetch facts before answering.
- State which tool you called to get your figures.
"""

def extract_text(response) -> str:
    texts = []
    content = getattr(response, "content", [])
    if isinstance(content, str):
        return content
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
        else:
            if getattr(block, "type", None) == "text":
                texts.append(getattr(block, "text", ""))
    return "\n".join(texts).strip()

def run_turn(conversation: list, user_message: str):
    conversation.append({"role": "user", "content": user_message})
    
    for hop in range(5):
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM_PROMPT,
            max_tokens=800,
            tools=MCP_TOOL_SCHEMAS,
            messages=conversation
        )
        
        # 1. Inspect content for any ToolUse blocks
        tool_uses = []
        for block in response.content:
            b_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            if b_type == "tool_use":
                tool_uses.append(block)

        # 2. If no tool calls were made, we have our final text answer
        if not tool_uses:
            final_text = extract_text(response)
            conversation.append({"role": "assistant", "content": response.content})
            return final_text, conversation

        # 3. Otherwise, execute the tools and feed results back into context
        conversation.append({"role": "assistant", "content": response.content})
        tool_results = []
        for b in tool_uses:
            t_name = b["name"] if isinstance(b, dict) else b.name
            t_input = b["input"] if isinstance(b, dict) else b.input
            t_id = b["id"] if isinstance(b, dict) else b.id

            print(f"  [MCP Tool Call] Invoking {t_name}({json.dumps(t_input)})")
            result = handle_mcp_call(t_name, t_input)
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": t_id,
                "content": json.dumps(result)
            })

        conversation.append({"role": "user", "content": tool_results})

    return "Max tool turns exceeded.", conversation

def main():
    print("=" * 70)
    print("C12: MCP SERVER MULTI-TURN SESSION")
    print("=" * 70)

    conv = []

    # Q1
    q1 = "Which grids have the highest anomaly scores? Use the hotspots tool."
    print(f"\n[User Q1]: {q1}")
    a1, conv = run_turn(conv, q1)
    print(f"\n[Assistant A1]:\n{a1}")

    # Q2
    print("\n" + "-" * 70)
    q2 = "Check whether their data pipeline completed successfully."
    print(f"\n[User Q2]: {q2}")
    a2, conv = run_turn(conv, q2)
    print(f"\n[Assistant A2]:\n{a2}")

if __name__ == "__main__":
    main()