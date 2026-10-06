import sys
from pathlib import Path
from dotenv import dotenv_values
sys.path.append(str(Path(__file__).resolve().parent))

from prompt_manager import load_template, execute_safe_claude_call, ENV_PATH

print("=" * 70)
print("TEST 2A: TEMPLATE LOADER EXECUTION")
print("=" * 70)
prompt = load_template(
    "dataset_profile_v1",
    table_name="fact_network_activity",
    expected_grain="(time_key, grid_id)",
    row_count="125,000",
    distinct_keys_count="125,000",
    missing_values_summary="0 nulls across internet_activity"
)
print("Template successfully loaded and filled:")
print(prompt[:180] + "...\n")

print("=" * 70)
print("TEST 2B: SECRET LEAKAGE GUARD (DELIBERATE INJECTION)")
print("=" * 70)
secrets = dotenv_values(ENV_PATH)
real_secret = secrets.get("ANTHROPIC_API_KEY", "sk-ant-dummysecret12345")

malicious_prompt = f"Audit this database connection string: mysql://root:{real_secret}@localhost/telecom"

try:
    execute_safe_claude_call("System", malicious_prompt)
    print("FAILED: Security guard did not catch secret injection!")
except PermissionError as e:
    print(f"PASS: Security guard caught the secret! -> {e}")