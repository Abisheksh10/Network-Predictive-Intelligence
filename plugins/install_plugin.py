import os
import shutil
import sys
import json

def install_plugin(target_dir: str):
    plugin_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "telecom-noc-standard"))
    target_dir = os.path.abspath(target_dir)

    print("=" * 70)
    print(f"INSTALLING TELECOM-NOC-STANDARD PLUGIN")
    print(f"Source: {plugin_src}")
    print(f"Target: {target_dir}")
    print("=" * 70)

    if not os.path.exists(plugin_src):
        print(f"ERROR: Plugin source {plugin_src} does not exist.")
        sys.exit(1)

    os.makedirs(target_dir, exist_ok=True)
    target_claude = os.path.join(target_dir, ".claude")
    os.makedirs(target_claude, exist_ok=True)

    # 1. Install CLAUDE.md
    shutil.copy2(
        os.path.join(plugin_src, "CLAUDE.md"),
        os.path.join(target_dir, "CLAUDE.md")
    )
    print("  [INSTALLED] CLAUDE.md rules (C4)")

    # 2. Install .claude tree (commands, skills, hooks, settings)
    src_claude = os.path.join(plugin_src, ".claude")
    for folder in ["commands", "skills", "hooks"]:
        s_folder = os.path.join(src_claude, folder)
        t_folder = os.path.join(target_claude, folder)
        if os.path.exists(s_folder):
            if os.path.exists(t_folder):
                shutil.rmtree(t_folder)
            shutil.copytree(s_folder, t_folder)
            print(f"  [INSTALLED] .claude/{folder}/")

    # 3. Install settings.json
    shutil.copy2(
        os.path.join(src_claude, "settings.json"),
        os.path.join(target_claude, "settings.json")
    )
    print("  [INSTALLED] .claude/settings.json (Permissions, Hooks, MCP)")

    # 4. Write installation receipt
    receipt = {
        "plugin": "telecom-noc-standard",
        "version": "1.0.0",
        "installed_at": target_dir,
        "verified": True
    }
    with open(os.path.join(target_claude, "plugin_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    print("\nSUCCESS: Plugin installed cleanly into fresh environment.")

if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else r"D:\project1_clean_env"
    install_plugin(dest)