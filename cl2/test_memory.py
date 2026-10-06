import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from project_context import get_project_context
from prompt_manager import execute_safe_claude_call

test_question = "What is our database canonical grain, and are we allowed to use the word 'congestion' in incident tickets?"

print("=" * 70)
print("TEST 1A: CALLING WITH PROJECT MEMORY ENABLED")
print("=" * 70)
system_with_memory = get_project_context()
answer_with_memory = execute_safe_claude_call(system_with_memory, test_question)
print(answer_with_memory)

print("\n" + "=" * 70)
print("TEST 1B: CALLING WITH MEMORY REMOVED (DEGRADED BASELINE)")
print("=" * 70)
system_without_memory = "You are a general helpful assistant."
answer_without_memory = execute_safe_claude_call(system_without_memory, test_question)
print(answer_without_memory)