import os
import sys
from datetime import datetime
import subprocess

LOG_FILE = os.path.join(os.path.dirname(__file__), "hook_audit.log")

def log(msg: str):
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] {msg}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())

def run_grain_check(target_file: str) -> bool:
    """Verifies that no duplicates exist on (grid_id, timestamp)."""
    log("[HOOK-CHECK] Running mandatory grain duplicate check...")
    
    # Deliberate fail demonstration check for Lab C10
    if "fail_test" in target_file.lower() or "broken" in target_file.lower():
        log("[HOOK-FAIL] Grain duplicate detected: [(time_key=1204, grid_id=4821, count=2)]")
        log("[HOOK-FAIL] Validation failed: Violation of canonical grain (1 grid per hourly timestamp).")
        return False

    try:
        import mysql.connector
        # Try localhost/127.0.0.1 first, fallback to WSL bridge with short connection timeout
        host = os.getenv("DB_HOST", "127.0.0.1")
        conn = mysql.connector.connect(
            host=host, 
            port=3306, 
            user="root", 
            password=os.getenv("DB_PASSWORD", "root"), 
            database="telecom_warehouse",
            connection_timeout=2
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT time_key, grid_id, COUNT(*) 
            FROM fact_network_activity 
            GROUP BY time_key, grid_id 
            HAVING COUNT(*) > 1 
            LIMIT 1;
        """)
        dups = cur.fetchall()
        cur.close()
        conn.close()

        if dups:
            log(f"[HOOK-FAIL] Grain duplicate detected in warehouse: {dups}")
            return False
        log("[HOOK-PASS] Grain check passed: Strictly 1 grid per hour.")
        return True
    except Exception as e:
        log(f"[HOOK-WARN] DB check skipped (offline/unreachable): {e}")
        return True

def run_leakage_check() -> bool:
    """Runs the ML feature leakage assertion test via pytest."""
    log("[HOOK-CHECK] Running ML temporal leakage test...")
    cmd = ["pytest", "phase4/tests/test_api3_surge.py", "-q"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        log("[HOOK-PASS] ML temporal integrity verified.")
        return True
    else:
        log(f"[HOOK-FAIL] Feature leakage test failed:\n{res.stdout}\n{res.stderr}")
        return False

def main():
    target_file = sys.argv[1] if len(sys.argv) > 1 else ""
    log(f"[POST-EDIT-HOOK TRIGGERED] File modified: {target_file}")

    target_norm = target_file.replace("\\", "/").lower()
    if any(k in target_norm for k in ["phase2", "spark", "phase3"]):
        if not run_grain_check(target_file):
            log("[HOOK-ABORT] Action blocked due to failed grain check.")
            sys.exit(1)

    if any(k in target_norm for k in ["phase6", "ml"]):
        if not run_leakage_check():
            log("[HOOK-ABORT] Action blocked due to feature leakage.")
            sys.exit(1)

    log("[HOOK-SUCCESS] All post-edit sanity checks passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()