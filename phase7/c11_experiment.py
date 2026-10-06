import json
import requests

API_BASE = "http://127.0.0.1:8000"

def get_grid_scores():
    # Gather alerts and hotspot indicators
    hotspots = requests.get(f"{API_BASE}/network/hotspots?limit=100").json()
    alerts = requests.get(f"{API_BASE}/network/alerts").json()
    return hotspots, alerts

def evaluate_threshold(threshold: float):
    """
    Evaluates alert volume and agreement with NP3 rule alerts
    given an anomaly decision threshold (baseline is typically -0.15 or z-score 2.0).
    """
    # Sample 50 active representative grids in Milan
    sample_grids = [
        4821, 5259, 5059, 5258, 5159, 5061, 4459, 6064, 5161, 6058,
        4956, 4259, 4359, 4559, 4659, 4759, 4859, 4959, 5359, 5459,
        4160, 4260, 4360, 4460, 4560, 4660, 4760, 4860, 4960, 5060,
        5160, 5260, 5360, 5460, 5560, 4161, 4261, 4361, 4461, 4561,
        4661, 4761, 4861, 4961, 5261, 5361, 5461, 5561, 5062, 5162
    ]
    
    flagged = []
    rule_alerted = []
    
    for gid in sample_grids:
        # Check rule alerts
        try:
            feat = requests.get(f"{API_BASE}/network/grid/{gid}/features", timeout=3).json()
            score_resp = requests.post(f"{API_BASE}/network/anamoly_score?grid_id={gid}&timestamp=2013-11-07T23:00:00", timeout=3).json()
            score = float(score_resp.get("anomaly_score", 0.0))
            
            # Simulated NP3 rule: peak_ratio > 2.0 or variability > 0.6
            is_rule_alert = (feat.get("peak_ratio", 0) > 2.0 or feat.get("variability", 0) > 0.55)
            if is_rule_alert:
                rule_alerted.append(gid)
                
            # Evaluated model threshold
            if score >= threshold:
                flagged.append((gid, score))
        except Exception:
            continue

    flagged_ids = set([x[0] for x in flagged])
    rule_ids = set(rule_alerted)
    
    # Agreement: Jaccard overlap between rule alerts and model flagged
    intersection = len(flagged_ids.intersection(rule_ids))
    union = len(flagged_ids.union(rule_ids)) if len(flagged_ids.union(rule_ids)) > 0 else 1
    agreement = (intersection / union) * 100.0

    return {
        "threshold": threshold,
        "total_flagged": len(flagged),
        "top_20": [x[0] for x in sorted(flagged, key=lambda x: x[1], reverse=True)[:20]],
        "rule_alert_count": len(rule_ids),
        "agreement_pct": round(agreement, 2)
    }

if __name__ == "__main__":
    print("Evaluating Baseline Threshold (e.g. -0.20)...")
    baseline = evaluate_threshold(-0.20)
    
    print("Evaluating Relaxed Threshold to double alert volume (e.g. -0.65)...")
    relaxed = evaluate_threshold(-0.65)
    
    print("\n" + "=" * 70)
    print("C11: EXPERIMENT RUNNER RESULTS")
    print("=" * 70)
    print(f"BASELINE: Alert Volume = {baseline['total_flagged']} | NP3 Agreement = {baseline['agreement_pct']}%")
    print(f"RELAXED : Alert Volume = {relaxed['total_flagged']} | NP3 Agreement = {relaxed['agreement_pct']}%")
    print(f"Top-20 Overlap Count: {len(set(baseline['top_20']).intersection(set(relaxed['top_20'])))}")