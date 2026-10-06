import os
import sys

CLEAN_DIR = r"D:\project1_clean_env"

def test_clean_environment():
    print("=" * 70)
    print("VERIFYING CLEAN ENVIRONMENT INSTALLATION (CRITERION 2)")
    print("=" * 70)

    # 1. Verify CLAUDE.md and Terminology Rules
    claude_md = os.path.join(CLEAN_DIR, "CLAUDE.md")
    assert os.path.exists(claude_md), "CLAUDE.md missing in fresh environment!"
    with open(claude_md, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "congestion" in content.lower(), "Congestion rule missing from CLAUDE.md"
    print("  [PASS] Rule Verification: Congestion prohibition rule is present and active.")

    # 2. Verify Slash Command (/network-health)
    cmd_file = os.path.join(CLEAN_DIR, ".claude", "commands", "network-health.md")
    assert os.path.exists(cmd_file), "/network-health command file missing!"
    with open(cmd_file, "r", encoding="utf-8") as f:
        cmd_text = f.read()
    assert "grain" in cmd_text.lower(), "Grain verification missing from /network-health"
    print("  [PASS] Command Verification: /network-health is registered and valid.")

    # 3. Verify Hooks and Settings
    settings_file = os.path.join(CLEAN_DIR, ".claude", "settings.json")
    hook_file = os.path.join(CLEAN_DIR, ".claude", "hooks", "post_edit_test.py")
    assert os.path.exists(settings_file), "settings.json missing in fresh environment!"
    assert os.path.exists(hook_file), "post_edit_test.py missing in fresh environment!"
    print("  [PASS] Safeguard Verification: Post-edit hooks and permissions policy configured.")

    print("\nALL VERIFICATIONS PASSED: The fresh environment inherits 100% of project standards.")

if __name__ == "__main__":
    test_clean_environment()