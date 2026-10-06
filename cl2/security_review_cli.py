import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from project_context import get_project_context
from prompt_manager import load_template, execute_safe_claude_call

def run_human_security_review(module_name: str, author: str, diff_text: str):
    """
    MANUAL INVOCATION ONLY.
    Never import or invoke this function inside automated CI loops or background daemons.
    """
    prompt = load_template(
        "security_review_v1",
        module_name=module_name,
        author=author,
        code_diff=diff_text
    )
    system = get_project_context()
    print("=" * 70)
    print(f"RUNNING MANUAL HUMAN SECURITY AUDIT FOR: {module_name}")
    print("=" * 70)
    report = execute_safe_claude_call(system, prompt)
    print(report)
    return report

if __name__ == "__main__":
    sample_diff = """
    + def fetch_user_data(grid_id):
    +     query = f"SELECT * FROM fact_network_activity WHERE grid_id = {grid_id}"
    +     return engine.execute(query)
    """
    run_human_security_review("phase6/data_access.py", "Abishek", sample_diff)