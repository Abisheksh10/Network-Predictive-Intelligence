import time
import json
import requests

API_URL = "http://localhost:8000/assistant/chat"

def test_cache_and_chat():
    print("=" * 75)
    print("1. VERIFYING POST /assistant/chat & PROMPT CACHING (CALL 1 vs CALL 2)")
    print("=" * 75)

    payload = {
        "message": "What is our customer cohort size and churn baseline? Also give me customer John Doe's tenure.",
        "history": [],
        "enable_thinking": False
    }

    # Call 1: Cold start (Cache Write)
    t0 = time.time()
    resp1 = requests.post(API_URL, json=payload).json()
    lat1 = round(time.time() - t0, 2)

    print(f"\n[CALL 1 - Cold Start] ({lat1}s)")
    print(f"  Reply Preview : {resp1['reply'][:140]}...")
    print(f"  Input Tokens  : {resp1['usage']['input_tokens']}")
    print(f"  Cache Write   : {resp1['usage']['cache_creation_input_tokens']}")
    print(f"  Cache Read    : {resp1['usage']['cache_read_input_tokens']}")

    # Call 2: Warm hit (Cache Read)
    t1 = time.time()
    resp2 = requests.post(API_URL, json=payload).json()
    lat2 = round(time.time() - t1, 2)

    print(f"\n[CALL 2 - Warm Cache Hit] ({lat2}s)")
    print(f"  Input Tokens  : {resp2['usage']['input_tokens']}")
    print(f"  Cache Write   : {resp2['usage']['cache_creation_input_tokens']}")
    print(f"  Cache Read    : {resp2['usage']['cache_read_input_tokens']}")

    return resp1, resp2

def test_thinking_comparison():
    print("\n" + "=" * 75)
    print("2. THINKING COMPARISON (OFF vs ON) ON MULTI-STEP REASONING")
    print("=" * 75)

    hard_prompt = (
        "A cohort of 500 month-to-month fiber optic customers paying $85/mo with electronic checks "
        "has a projected 42% churn risk. We have two retention offers: Offer A gives a flat $15/mo discount "
        "if they switch to 1-year contract. Offer B gives free tech support ($10 value) and automated bank pay "
        "with no price discount. Which offer protects higher net revenue over 12 months assuming Offer A cuts churn "
        "to 15% and Offer B cuts churn to 22%?"
    )

    # Thinking OFF
    p_off = {"message": hard_prompt, "history": [], "enable_thinking": False}
    t0 = time.time()
    r_off = requests.post(API_URL, json=p_off).json()
    lat_off = round(time.time() - t0, 2)

    # Thinking ON
    p_on = {"message": hard_prompt, "history": [], "enable_thinking": True, "thinking_budget": 1500}
    t1 = time.time()
    r_on = requests.post(API_URL, json=p_on).json()
    lat_on = round(time.time() - t1, 2)

    print(f"\n[THINKING OFF] Latency: {lat_off}s | Total Output: {r_off['usage']['output_tokens']} tokens")
    print(f"Reply summary:\n{r_off['reply'][:260]}...\n")

    print(f"[THINKING ON] Latency: {lat_on}s | Total Output: {r_on['usage']['output_tokens']} tokens")
    if r_on.get("thinking"):
        print(f"Thinking trace sample:\n{r_on['thinking'][:260]}...\n")
    print(f"Reply summary:\n{r_on['reply'][:260]}...\n")

if __name__ == "__main__":
    test_cache_and_chat()
    test_thinking_comparison()