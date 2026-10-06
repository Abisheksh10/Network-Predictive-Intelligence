import os
import json
import math 
from pathlib import Path
from fastapi import HTTPException
import joblib
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta,timezone
from db import get_db_connection
from schemas import (
    EvaluatedFeatureSummary,
    NetworkSummaryResponse,
    GridActivityResponse,
    GridHourlyActivityPoint,
    HotspotsResponse,
    HotspotItem,
    SurgeHotspotsResponse,
    SurgeGridItem,
    NetworkAlertsResponse,
    NetworkAlertItem,
    AlertSeverity,
    AlertStatus,
    GridFeaturesResponse,
    FeatureFreshnessStatus,
    PredictRiskRequest,
    PredictRiskResponse,
    RiskLevel
)

# Global Model Container
ML_ARTIFACT: Optional[Dict[str, Any]] = None
MODEL_VERSION = "v1.0.0-logistic-baseline"


def load_ml_model(model_path: Optional[str]=None):
    """
    Loads the trained ML3 model artifact into memory.
    Raises RuntimeError if artifact is missing (Fail-Fast).
    """
    global ML_ARTIFACT
    
    # Check current directory and phase6 fallback
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), "artifacts", "baseline_risk_model.joblib"),
        os.path.join(os.path.dirname(__file__), "..", "phase6", "artifacts", "baseline_risk_model.joblib")
    ]
    
    loaded_path = None
    for path in candidate_paths:
        if os.path.exists(path):
            loaded_path = path
            break
            
    if not loaded_path:
        raise RuntimeError(
            "FATAL: Machine Learning model artifact 'baseline_risk_model.joblib' not found. "
            "Execute ML3 training (python train_ml3.py) to generate the model artifact."
        )

    ML_ARTIFACT = joblib.load(loaded_path)
    print(f"✅ Successfully loaded Production ML Model from: {loaded_path}")


def get_latest_available_timestamp() -> datetime:
    """Dynamically queries MAX(timestamp) from dim_time in the analytics warehouse."""
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT MAX(timestamp) AS max_ts FROM dim_time;")
        row = cursor.fetchone()
        cursor.close()
        if not row or row["max_ts"] is None:
            raise ValueError("No temporal records found in analytics warehouse.")
        return row["max_ts"]


# ============================================================================
# API1: NETWORK SUMMARY
# ============================================================================

def get_network_summary(
    as_of: Optional[datetime] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    filter_date: Optional[date] = None,
    filter_hour: Optional[int] = None
) -> NetworkSummaryResponse:
    """
    Computes aggregated network summary metrics with flexible temporal window filters.
    Supports:
      - Bounded datetime intervals (start_time <= timestamp <= end_time)
      - Date / hour filters
      - Effective upper cutoff (as_of)
    """
    effective_as_of = end_time or as_of or get_latest_available_timestamp()

    conditions = []
    params: List[object] = []

    if start_time is not None and end_time is not None:
        conditions.append("t.timestamp BETWEEN %s AND %s")
        params.extend([
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time.strftime("%Y-%m-%d %H:%M:%S")
        ])
    elif start_time is not None:
        conditions.append("t.timestamp >= %s")
        params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        conditions.append("t.timestamp <= %s")
        params.append(effective_as_of.strftime("%Y-%m-%d %H:%M:%S"))

    if filter_date is not None:
        conditions.append("t.date = %s")
        params.append(filter_date.strftime("%Y-%m-%d"))

    if filter_hour is not None:
        conditions.append("t.hour = %s")
        params.append(filter_hour)

    where_clause = " AND ".join(conditions)

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)

        summary_query = f"""
            SELECT 
                COALESCE(SUM(f.total_activity), 0.0) AS total_activity,
                COUNT(DISTINCT f.grid_id) AS active_grids
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE {where_clause};
        """
        cursor.execute(summary_query, tuple(params))
        summary_res = cursor.fetchone()
        total_activity = float(summary_res["total_activity"]) if summary_res else 0.0
        active_grids = int(summary_res["active_grids"]) if summary_res else 0

        if active_grids == 0:
            cursor.close()
            return NetworkSummaryResponse(
                total_activity=0.0,
                active_grids=0,
                peak_hour=0,
                top_grid=0,
                as_of=effective_as_of,
                window_start=start_time
            )

        peak_hour_query = f"""
            SELECT 
                t.hour,
                SUM(f.total_activity) AS hourly_total
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE {where_clause}
            GROUP BY t.hour
            ORDER BY hourly_total DESC
            LIMIT 1;
        """
        cursor.execute(peak_hour_query, tuple(params))
        peak_hour_res = cursor.fetchone()
        peak_hour = int(peak_hour_res["hour"]) if peak_hour_res else 0

        top_grid_query = f"""
            SELECT 
                f.grid_id,
                SUM(f.total_activity) AS grid_total
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE {where_clause}
            GROUP BY f.grid_id
            ORDER BY grid_total DESC
            LIMIT 1;
        """
        cursor.execute(top_grid_query, tuple(params))
        top_grid_res = cursor.fetchone()
        top_grid = int(top_grid_res["grid_id"]) if top_grid_res else 0

        cursor.close()

    return NetworkSummaryResponse(
        total_activity=round(total_activity, 4),
        active_grids=active_grids,
        peak_hour=peak_hour,
        top_grid=top_grid,
        as_of=effective_as_of,
        window_start=start_time
    )

# ============================================================================
# API2: GRID ACTIVITY DRILL-DOWN
# ============================================================================

def get_grid_activity(
    grid_id: int,
    filter_date: Optional[date] = None,
    filter_hour: Optional[int] = None,
    as_of: Optional[datetime] = None
) -> Optional[GridActivityResponse]:
    if not (1 <= grid_id <= 10000):
        return None

    effective_as_of = as_of if as_of is not None else get_latest_available_timestamp()

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT grid_id, centroid_lon, centroid_lat FROM dim_grid WHERE grid_id = %s;",
            (grid_id,)
        )
        grid_info = cursor.fetchone()
        if not grid_info:
            cursor.close()
            return None

        query_conditions = ["f.grid_id = %s"]
        params: List[object] = [grid_id]

        if filter_date is not None and filter_hour is not None:
            query_conditions.append("t.date = %s AND t.hour = %s")
            params.extend([filter_date.strftime("%Y-%m-%d"), filter_hour])
        elif filter_date is not None:
            query_conditions.append("t.date = %s")
            params.append(filter_date.strftime("%Y-%m-%d"))
        elif filter_hour is not None:
            start_window = effective_as_of - timedelta(hours=23)
            query_conditions.append("t.timestamp BETWEEN %s AND %s AND t.hour = %s")
            params.extend([
                start_window.strftime("%Y-%m-%d %H:%M:%S"),
                effective_as_of.strftime("%Y-%m-%d %H:%M:%S"),
                filter_hour
            ])
        else:
            start_window = effective_as_of - timedelta(hours=23)
            query_conditions.append("t.timestamp BETWEEN %s AND %s")
            params.extend([
                start_window.strftime("%Y-%m-%d %H:%M:%S"),
                effective_as_of.strftime("%Y-%m-%d %H:%M:%S")
            ])

        sql_query = f"""
            SELECT 
                t.timestamp,
                t.date,
                t.hour,
                f.sms_in,
                f.sms_out,
                f.call_in,
                f.call_out,
                f.internet_activity,
                f.total_sms,
                f.total_calls,
                f.total_activity,
                f.internet_share
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE {' AND '.join(query_conditions)}
            ORDER BY t.timestamp ASC;
        """

        cursor.execute(sql_query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()

    series = [
        GridHourlyActivityPoint(
            timestamp=r["timestamp"],
            date=r["date"],
            hour=int(r["hour"]),
            sms_in=round(float(r["sms_in"]), 4),
            sms_out=round(float(r["sms_out"]), 4),
            call_in=round(float(r["call_in"]), 4),
            call_out=round(float(r["call_out"]), 4),
            internet_activity=round(float(r["internet_activity"]), 4),
            total_sms=round(float(r["total_sms"]), 4),
            total_calls=round(float(r["total_calls"]), 4),
            total_activity=round(float(r["total_activity"]), 4),
            internet_share=round(float(r["internet_share"]), 4)
        )
        for r in rows
    ]

    return GridActivityResponse(
        grid_id=grid_id,
        centroid_lon=float(grid_info["centroid_lon"]),
        centroid_lat=float(grid_info["centroid_lat"]),
        as_of=effective_as_of,
        data_points_count=len(series),
        series=series
    )
# ============================================================================
# API3: HOTSPOTS ENDPOINT (ENRICHED WITH BATCH ML SCORES)
# ============================================================================

def get_hotspots(
    limit: int = 10,
    as_of: Optional[datetime] = None
) -> HotspotsResponse:
    effective_as_of = as_of if as_of is not None else get_latest_available_timestamp()
    start_window = effective_as_of - timedelta(hours=23)

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        hotspot_query = """
            SELECT 
                f.grid_id,
                g.centroid_lon,
                g.centroid_lat,
                SUM(f.total_activity) AS total_activity,
                SUM(f.internet_activity) AS internet_activity,
                SUM(f.total_calls) AS total_calls,
                SUM(f.total_sms) AS total_sms,
                CASE 
                    WHEN SUM(f.total_activity) > 0 THEN SUM(f.internet_activity) / SUM(f.total_activity)
                    ELSE 0.0 
                END AS internet_share,
                r.risk_score,
                r.risk_level,
                r.model_version
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            JOIN dim_grid g ON f.grid_id = g.grid_id
            LEFT JOIN network_risk_scores r 
                   ON f.grid_id = r.grid_id AND r.timestamp = %s
            WHERE t.timestamp BETWEEN %s AND %s
            GROUP BY f.grid_id, g.centroid_lon, g.centroid_lat, r.risk_score, r.risk_level, r.model_version
            ORDER BY total_activity DESC, f.grid_id ASC
            LIMIT %s;
        """
        cursor.execute(
            hotspot_query,
            (
                effective_as_of.strftime("%Y-%m-%d %H:%M:%S"),
                start_window.strftime("%Y-%m-%d %H:%M:%S"),
                effective_as_of.strftime("%Y-%m-%d %H:%M:%S"),
                limit
            )
        )
        rows = cursor.fetchall()
        cursor.close()

    hotspot_items = [
        HotspotItem(
            grid_id=int(r["grid_id"]),
            centroid_lon=float(r["centroid_lon"]),
            centroid_lat=float(r["centroid_lat"]),
            total_activity=round(float(r["total_activity"]), 4),
            internet_activity=round(float(r["internet_activity"]), 4),
            total_calls=round(float(r["total_calls"]), 4),
            total_sms=round(float(r["total_sms"]), 4),
            internet_share=round(float(r["internet_share"]), 4),
            rank=idx + 1,
            risk_score=float(r["risk_score"]) if r["risk_score"] is not None else None,
            risk_level=r["risk_level"] if r["risk_level"] is not None else None,
            model_version=r["model_version"] if r["model_version"] is not None else MODEL_VERSION
        )
        for idx, r in enumerate(rows)
    ]

    return HotspotsResponse(
        as_of=effective_as_of,
        total_hotspots_returned=len(hotspot_items),
        hotspots=hotspot_items
    )


# ============================================================================
# API3: SURGE HOTSPOTS ENDPOINT (SHARPEST INCREASE VS. TRAILING BASELINE)
# ============================================================================



#c5 done by claude
def get_surge_grids(
    limit: int = 10,
    as_of: Optional[datetime] = None
) -> SurgeHotspotsResponse:
    """
    Ranks grids by proportional increase of recent activity over a trailing
    baseline, reusing the two-window growth formula from predict_network_risk:
    recent = [as_of-23h, as_of], baseline = [as_of-47h, as_of-24h] (disjoint,
    baseline excludes the recent/AS_OF window).
    """
    effective_as_of = as_of if as_of is not None else get_latest_available_timestamp()
    recent_start = effective_as_of - timedelta(hours=23)
    baseline_start = effective_as_of - timedelta(hours=47)
    baseline_end = effective_as_of - timedelta(hours=24)

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        surge_query = """
            SELECT
                f.grid_id,
                g.centroid_lon,
                g.centroid_lat,
                AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_avg,
                AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS baseline_avg
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            JOIN dim_grid g ON f.grid_id = g.grid_id
            WHERE t.timestamp BETWEEN %s AND %s
            GROUP BY f.grid_id, g.centroid_lon, g.centroid_lat;
        """
        cursor.execute(
            surge_query,
            (
                recent_start.strftime("%Y-%m-%d %H:%M:%S"),
                effective_as_of.strftime("%Y-%m-%d %H:%M:%S"),
                baseline_start.strftime("%Y-%m-%d %H:%M:%S"),
                baseline_end.strftime("%Y-%m-%d %H:%M:%S"),
                baseline_start.strftime("%Y-%m-%d %H:%M:%S"),
                effective_as_of.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
        rows = cursor.fetchall()
        cursor.close()

    scored_rows = []
    for r in rows:
        recent_avg = float(r["recent_avg"] or 0.0)
        baseline_avg = float(r["baseline_avg"] or 0.0)
        surge_score = (
            round((recent_avg - baseline_avg) / (baseline_avg + 1e-6), 4)
            if baseline_avg > 0 else 0.0
        )
        scored_rows.append((r, recent_avg, baseline_avg, surge_score))

    scored_rows.sort(key=lambda item: (-item[3], item[0]["grid_id"]))
    scored_rows = scored_rows[:limit]

    surge_items = [
        SurgeGridItem(
            grid_id=int(r["grid_id"]),
            centroid_lon=float(r["centroid_lon"]),
            centroid_lat=float(r["centroid_lat"]),
            current_activity=round(recent_avg, 4),
            baseline_activity=round(baseline_avg, 4),
            surge_score=surge_score,
            rank=idx + 1
        )
        for idx, (r, recent_avg, baseline_avg, surge_score) in enumerate(scored_rows)
    ]

    return SurgeHotspotsResponse(
        as_of=effective_as_of,
        total_grids_returned=len(surge_items),
        grids=surge_items
    )


# ============================================================================
# API3: RULE-BASED ALERTS ENGINE (ENRICHED WITH BATCH ML SCORES)
# ============================================================================
MODEL_VERSION = "v1.0.0-logistic-baseline"

def get_network_alerts(
    limit: int = 50,
    severity: Optional[AlertSeverity] = None,
    as_of: Optional[datetime] = None
) -> NetworkAlertsResponse:
    effective_as_of = as_of if as_of is not None else get_latest_available_timestamp()
    start_window = effective_as_of - timedelta(hours=23)

    conditions = ["t.timestamp BETWEEN %s AND %s"]
    params: List[object] = [
        start_window.strftime("%Y-%m-%d %H:%M:%S"),
        effective_as_of.strftime("%Y-%m-%d %H:%M:%S")
    ]

    # Activity thresholds mapped to LOW, MEDIUM, HIGH, CRITICAL
    if severity == AlertSeverity.CRITICAL:
        conditions.append("f.total_activity >= 12000")
    elif severity == AlertSeverity.HIGH:
        conditions.append("(f.total_activity >= 6000 AND f.total_activity < 12000)")
    elif severity == AlertSeverity.MEDIUM:
        conditions.append("(f.total_activity >= 2500 AND f.total_activity < 6000)")
    elif severity == AlertSeverity.LOW:
        conditions.append("(f.total_activity >= 1000 AND f.total_activity < 2500)")
    else:
        # ALL alerts: activity >= 1000
        conditions.append("f.total_activity >= 1000")

    where_clause = " AND ".join(conditions)

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        alerts_query = f"""
            SELECT 
                f.grid_id,
                t.timestamp,
                f.total_activity,
                f.internet_activity,
                f.total_calls,
                f.total_sms,
                f.internet_share,
                r.risk_score,
                r.risk_level,
                r.model_version
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            LEFT JOIN network_risk_scores r 
                   ON f.grid_id = r.grid_id AND r.timestamp = %s
            WHERE {where_clause}
            ORDER BY f.total_activity DESC, f.grid_id ASC
            LIMIT %s;
        """
        params_with_limit = [effective_as_of.strftime("%Y-%m-%d %H:%M:%S")] + params + [limit]
        cursor.execute(alerts_query, tuple(params_with_limit))
        rows = cursor.fetchall()
        cursor.close()

    alert_items: List[NetworkAlertItem] = []

    for r in rows:
        grid_id = int(r["grid_id"])
        ts = r["timestamp"]
        total_act = float(r["total_activity"])
        ts_str = ts.strftime("%Y%m%d%H")

        if total_act >= 12000:
            sev = AlertSeverity.CRITICAL
            atype = "CRITICAL_SPIKE"
            reason = f"Grid {grid_id} experienced critical activity volume ({total_act:.1f} units)."
            thresh = 12000.0
        elif total_act >= 6000:
            sev = AlertSeverity.HIGH
            atype = "HIGH_SURGE"
            reason = f"Grid {grid_id} recorded elevated traffic surge ({total_act:.1f} units)."
            thresh = 6000.0
        elif total_act >= 2500:
            sev = AlertSeverity.MEDIUM
            atype = "MODERATE_ELEVATION"
            reason = f"Grid {grid_id} observed moderate traffic concentration ({total_act:.1f} units)."
            thresh = 2500.0
        else:
            sev = AlertSeverity.LOW
            atype = "BASELINE_LOAD"
            reason = f"Grid {grid_id} observed baseline operational traffic ({total_act:.1f} units)."
            thresh = 1000.0

        alert_items.append(
            NetworkAlertItem(
                alert_id=f"ALT-{grid_id}-{ts_str}-{atype[:4]}",
                grid_id=grid_id,
                timestamp=ts,
                severity=sev,
                status=AlertStatus.ACTIVE,
                alert_type=atype,
                activity_measure=round(total_act, 4),
                threshold_value=thresh,
                reason=reason,
                risk_score=float(r["risk_score"]) if r["risk_score"] is not None else None,
                risk_level=r["risk_level"] if r["risk_level"] is not None else None,
                model_version=r["model_version"] if r["model_version"] is not None else MODEL_VERSION,
                model_features=None
            )
        )

    return NetworkAlertsResponse(
        as_of=effective_as_of,
        total_alerts_returned=len(alert_items),
        alerts=alert_items
    )


# ============================================================================
# API4: GRID FEATURES
# ============================================================================

def get_grid_features(
    grid_id: int,
    as_of: Optional[datetime] = None
) -> Optional[GridFeaturesResponse]:
    if not (1 <= grid_id <= 10000):
        return None

    effective_as_of = as_of if as_of is not None else get_latest_available_timestamp()

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                grid_id,
                avg_activity,
                activity_growth,
                active_hours,
                peak_ratio,
                variability,
                internet_share,
                feature_timestamp,
                data_quality_status
            FROM grid_features
            WHERE grid_id = %s;
        """, (grid_id,))
        row = cursor.fetchone()
        cursor.close()

    if not row:
        return None

    feat_ts = row["feature_timestamp"]
    delta_seconds = max((effective_as_of - feat_ts).total_seconds(), 0.0)
    freshness_hours = round(delta_seconds / 3600.0, 2)

    if freshness_hours <= 24.0:
        freshness_status = FeatureFreshnessStatus.FRESH
    elif freshness_hours <= 72.0:
        freshness_status = FeatureFreshnessStatus.STALE
    else:
        freshness_status = FeatureFreshnessStatus.DEGRADED

    return GridFeaturesResponse(
        grid_id=int(row["grid_id"]),
        avg_activity=float(row["avg_activity"]),
        activity_growth=float(row["activity_growth"]),
        active_hours=int(row["active_hours"]),
        peak_ratio=float(row["peak_ratio"]),
        variability=float(row["variability"]),
        internet_share=float(row["internet_share"]),
        feature_timestamp=feat_ts,
        freshness_status=freshness_status,
        freshness_hours=freshness_hours,
        data_quality_status=row["data_quality_status"]
    )


# ============================================================================
# API5: REAL MACHINE LEARNING INFERENCE ENGINE (ML5 PRODUCTION SERVING)
# ============================================================================
def predict_network_risk(payload: PredictRiskRequest) -> PredictRiskResponse:
    """
    Executes surge risk inference against the loaded HistGradientBoosting model artifact.
    Analyzes historical records strictly on or before payload.timestamp (lookback window [t-23, t]).
    Returns risk_level (LOW or CRITICAL) based on the learned optimal threshold, alongside risk_score.
    """
    global ML_ARTIFACT
    
    if ML_ARTIFACT is None:
        load_ml_model()

    model = ML_ARTIFACT["model"]
    feature_names = ML_ARTIFACT.get("features", [
        "avg_activity", "activity_growth", "active_hours", "peak_ratio",
        "variability", "internet_share", "immediate_ratio", "hour_sin", "hour_cos", "dayofweek"
    ])
    optimal_threshold = float(ML_ARTIFACT.get("optimal_threshold", 0.7046))

    t_cutoff = payload.timestamp
    grid_id = payload.grid_id

    # Compute temporal cyclical signals directly from cutoff timestamp
    cutoff_hour = t_cutoff.hour
    hour_sin = round(float(np.sin(2 * np.pi * cutoff_hour / 24.0)), 4)
    hour_cos = round(float(np.cos(2 * np.pi * cutoff_hour / 24.0)), 4)
    dayofweek = int(t_cutoff.weekday())

    feature_dict = None
    feat_ts = t_cutoff

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)

        # 1. Attempt lookup from materialized feature store table
        cursor.execute("""
            SELECT 
                avg_activity,
                activity_growth,
                active_hours,
                peak_ratio,
                variability,
                internet_share,
                feature_timestamp
            FROM network_feature_table
            WHERE grid_id = %s AND feature_timestamp = %s
            LIMIT 1;
        """, (grid_id, t_cutoff.strftime("%Y-%m-%d %H:%M:%S")))
        row = cursor.fetchone()

        if row:
            # Query the immediate activity at cutoff to derive immediate_ratio
            cursor.execute("""
                SELECT f.total_activity
                FROM fact_network_activity f
                JOIN dim_time t ON f.time_key = t.time_key
                WHERE f.grid_id = %s AND t.timestamp = %s
                LIMIT 1;
            """, (grid_id, t_cutoff.strftime("%Y-%m-%d %H:%M:%S")))
            act_row = cursor.fetchone()
            curr_act = float(act_row["total_activity"]) if act_row and act_row["total_activity"] else 0.0
            avg_act = float(row["avg_activity"])

            imm_ratio = curr_act / (avg_act + 1e-6) if avg_act > 0 else 1.0

            feature_dict = {
                "avg_activity": round(avg_act, 4),
                "activity_growth": round(float(row["activity_growth"]), 4),
                "active_hours": int(row["active_hours"]),
                "peak_ratio": round(float(row["peak_ratio"]), 4),
                "variability": round(float(row["variability"]), 4),
                "internet_share": round(float(row["internet_share"]), 4),
                "immediate_ratio": round(min(max(imm_ratio, 0.0), 20.0), 4),
                "hour_sin": hour_sin,
                "hour_cos": hour_cos,
                "dayofweek": dayofweek
            }
            feat_ts = row["feature_timestamp"]
        else:
            # 2. On-the-fly extraction over historical trailing window [t-23, t]
            recent_start = t_cutoff - timedelta(hours=23)
            baseline_start = t_cutoff - timedelta(hours=47)
            baseline_end = t_cutoff - timedelta(hours=24)

            dynamic_feat_query = """
                SELECT 
                    AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_avg,
                    MAX(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_max,
                    STDDEV_POP(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS recent_std,
                    SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE 0.0 END) AS recent_sum,
                    SUM(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.internet_activity ELSE 0.0 END) AS recent_internet_sum,
                    COUNT(DISTINCT CASE WHEN t.timestamp BETWEEN %s AND %s AND f.total_activity > 0 THEN t.hour ELSE NULL END) AS active_hours,
                    AVG(CASE WHEN t.timestamp BETWEEN %s AND %s THEN f.total_activity ELSE NULL END) AS baseline_avg,
                    MAX(CASE WHEN t.timestamp = %s THEN f.total_activity ELSE NULL END) AS current_activity
                FROM fact_network_activity f
                JOIN dim_time t ON f.time_key = t.time_key
                WHERE f.grid_id = %s AND t.timestamp BETWEEN %s AND %s;
            """
            params = (
                recent_start, t_cutoff,          # recent_avg
                recent_start, t_cutoff,          # recent_max
                recent_start, t_cutoff,          # recent_std
                recent_start, t_cutoff,          # recent_sum
                recent_start, t_cutoff,          # recent_internet_sum
                recent_start, t_cutoff,          # active_hours
                baseline_start, baseline_end,    # baseline_avg
                t_cutoff,                        # current_activity
                grid_id,
                baseline_start, t_cutoff
            )
            cursor.execute(dynamic_feat_query, params)
            dyn_row = cursor.fetchone()

            if not dyn_row or dyn_row["recent_sum"] is None or dyn_row["recent_sum"] == 0:
                cursor.close()
                raise HTTPException(
                    status_code=404,
                    detail=f"No telemetry records exist for Grid {grid_id} up to {t_cutoff.strftime('%Y-%m-%d %H:%M:%S')}."
                )

            recent_avg = float(dyn_row["recent_avg"] or 0.0)
            baseline_avg = float(dyn_row["baseline_avg"] or 0.0)
            recent_max = float(dyn_row["recent_max"] or 0.0)
            recent_std = float(dyn_row["recent_std"] or 0.0)
            recent_sum = float(dyn_row["recent_sum"] or 0.0)
            recent_net = float(dyn_row["recent_internet_sum"] or 0.0)
            curr_act = float(dyn_row["current_activity"] or 0.0)

            growth = (recent_avg - baseline_avg) / (baseline_avg + 1e-6) if baseline_avg > 0 else 0.0
            peak_r = recent_max / (recent_avg + 1e-6) if recent_avg > 0 else 1.0
            var_r = recent_std / (recent_avg + 1e-6) if recent_avg > 0 else 0.0
            net_r = recent_net / (recent_sum + 1e-6) if recent_sum > 0 else 0.0
            imm_r = curr_act / (recent_avg + 1e-6) if recent_avg > 0 else 1.0

            feature_dict = {
                "avg_activity": round(recent_avg, 4),
                "activity_growth": round(min(max(growth, -1.0), 10.0), 4),
                "active_hours": int(dyn_row["active_hours"] or 0),
                "peak_ratio": round(max(peak_r, 1.0), 4),
                "variability": round(max(var_r, 0.0), 4),
                "internet_share": round(min(max(net_r, 0.0), 1.0), 4),
                "immediate_ratio": round(min(max(imm_r, 0.0), 20.0), 4),
                "hour_sin": hour_sin,
                "hour_cos": hour_cos,
                "dayofweek": dayofweek
            }

        cursor.close()

    # Reorder columns to match the trained schema order
    feature_df = pd.DataFrame([feature_dict])[feature_names]

    # Model inference: continuous probability for class 1 (Surge Risk at t+1)
    probabilities = model.predict_proba(feature_df)[0]
    risk_score = float(probabilities[1])
    risk_score = round(min(max(risk_score, 0.0), 1.0), 4)

    # Classification evaluated against the model's learned optimal threshold
    level = RiskLevel.CRITICAL if risk_score >= optimal_threshold else RiskLevel.LOW

    # Operational diagnostic driver
    if feature_dict["immediate_ratio"] > 1.8:
        driver = "acute short-term momentum spike"
    elif feature_dict["activity_growth"] > 0.30:
        driver = "sustained multi-hour demand acceleration"
    elif feature_dict["peak_ratio"] > 2.2:
        driver = "extreme diurnal burstiness"
    elif feature_dict["variability"] > 0.60:
        driver = "high channel volatility"
    elif feature_dict["avg_activity"] > 3000:
        driver = "heavy baseline concentration"
    else:
        driver = "nominal steady-state load"

    explanation_note = (
        f"Model Evaluation: Evaluated Grid {grid_id} using lookback ending at {t_cutoff.strftime('%Y-%m-%d %H:%M:%S')}. "
        f"Surge risk probability is {risk_score * 100:.1f}% (Decision Threshold: {optimal_threshold * 100:.1f}%). "
        f"Primary driver: {driver}. Model: {MODEL_VERSION}."
    )

    now_utc = datetime.now(timezone.utc)
    
    # Extract only the summary fields if EvaluatedFeatureSummary expects 6 keys,
    # or pass feature_dict directly if the schema allows extra keys.
    try:
        features_summary = EvaluatedFeatureSummary(**feature_dict)
    except Exception:
        legacy_keys = ["avg_activity", "activity_growth", "active_hours", "peak_ratio", "variability", "internet_share"]
        features_summary = EvaluatedFeatureSummary(**{k: feature_dict[k] for k in legacy_keys if k in feature_dict})

    return PredictRiskResponse(
        grid_id=grid_id,
        risk_score=risk_score,
        risk_level=level,
        model_version=MODEL_VERSION,
        explanation_note=explanation_note,
        feature_timestamp=feat_ts if isinstance(feat_ts, datetime) else now_utc,
        prediction_timestamp=now_utc,
        features_used=features_summary
    )
    
    
    


def get_grid_anomaly_score(grid_id: int, timestamp: datetime) -> dict:
    """
    Computes an operational anomaly score (z-score) relative to the grid's 
    trailing 24-hour mean activity.
    """
    recent_start = timestamp - timedelta(hours=23)

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                AVG(f.total_activity) AS mean_act,
                STDDEV_POP(f.total_activity) AS std_act,
                (SELECT f2.total_activity 
                 FROM fact_network_activity f2 
                 JOIN dim_time t2 ON f2.time_key = t2.time_key 
                 WHERE f2.grid_id = %s AND t2.timestamp = %s LIMIT 1) AS curr_act
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE f.grid_id = %s AND t.timestamp BETWEEN %s AND %s;
        """
        cursor.execute(query, (grid_id, timestamp, grid_id, recent_start, timestamp))
        row = cursor.fetchone()
        cursor.close()

    if not row or row["curr_act"] is None:
        # Fallback to nominal if missing
        return {
            "grid_id": grid_id,
            "timestamp": timestamp.isoformat(),
            "anomaly_score": 0.0,
            "anomaly_direction": "NORMAL",
            "status": "baseline_uncomputed"
        }

    mean_act = float(row["mean_act"] or 0.0)
    std_act = float(row["std_act"] or 1.0)
    curr_act = float(row["curr_act"])

    # Standard Z-Score calculation
    z_score = (curr_act - mean_act) / (std_act + 1e-6)
    direction = "HIGH" if z_score > 2.0 else ("LOW" if z_score < -2.0 else "NORMAL")

    return {
        "grid_id": grid_id,
        "timestamp": timestamp.isoformat(),
        "anomaly_score": round(z_score, 4),
        "anomaly_direction": direction,
        "current_activity": curr_act,
        "mean_activity": round(mean_act, 4)
    }


def get_grid_total_activity(grid_id: int) -> dict:
    """
    Returns cumulative total network activity recorded for a specific grid cell.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                COALESCE(SUM(total_activity), 0.0) AS total_activity,
                COALESCE(SUM(internet_activity), 0.0) AS internet_activity,
                COUNT(DISTINCT time_key) AS total_hours_recorded
            FROM fact_network_activity
            WHERE grid_id = %s;
        """
        cursor.execute(query, (grid_id,))
        row = cursor.fetchone()
        cursor.close()

    return {
        "grid_id": grid_id,
        "total_activity": float(row["total_activity"]) if row else 0.0,
        "internet_activity": float(row["internet_activity"]) if row else 0.0,
        "total_hours_recorded": int(row["total_hours_recorded"]) if row else 0
    }
    


STATUS_FILE_PATH = Path(__file__).resolve().parents[1] / "status" / "pipeline_status.json"

def get_pipeline_status() -> dict:
    """
    Reads the DE7 status record without recomputing data.
    Provides top-level health flag, reasons, and freshness.
    """
    if not STATUS_FILE_PATH.exists():
        return {
            "healthy": False,
            "run_id": "UNKNOWN",
            "run_timestamp": datetime.now().isoformat(),
            "pipeline_status": "UNAVAILABLE",
            "tasks": {},
            "metrics": {
                "rows_in": 0,
                "rows_rejected": 0,
                "nulls_handled": 0,
                "rows_published": 0,
                "as_of": "2013-11-07T23:00:00"
            },
            "freshness_indicator": "STALE - Missing status artifact",
            "reasons": ["Pipeline status record (status/pipeline_status.json) not found on disk."]
        }

    try:
        with open(STATUS_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return {
            "healthy": False,
            "run_id": "ERROR",
            "run_timestamp": datetime.now().isoformat(),
            "pipeline_status": "CORRUPT",
            "tasks": {},
            "metrics": {
                "rows_in": 0, "rows_rejected": 0, "nulls_handled": 0, "rows_published": 0, "as_of": "2013-11-07T23:00:00"
            },
            "freshness_indicator": "CORRUPT - Unreadable status artifact",
            "reasons": [f"Failed to parse status file: {str(exc)}"]
        }

    pipeline_status = data.get("pipeline_status", "UNKNOWN")
    healthy = data.get("healthy", pipeline_status == "SUCCESS")
    reasons = list(data.get("reasons", []))

    # Guard: populate reasons if unhealthy
    if not healthy and not reasons:
        reasons.append(f"Pipeline marked as {pipeline_status}")

    # Verify task breakdowns for any failures
    for task_name, task_status in data.get("tasks", {}).items():
        if str(task_status).upper() not in ["PASS", "SUCCESS"]:
            healthy = False
            reasons.append(f"Task '{task_name}' failed with status '{task_status}'")

    # Metrics block
    metrics_data = data.get("metrics", {})
    as_of = metrics_data.get("as_of", "2013-11-07T23:00:00")

    return {
        "healthy": healthy,
        "run_id": data.get("run_id", "manual__default"),
        "run_timestamp": data.get("run_timestamp", datetime.now().isoformat()),
        "pipeline_status": pipeline_status,
        "tasks": data.get("tasks", {}),
        "metrics": {
            "rows_in": int(metrics_data.get("rows_in", 0)),
            "rows_rejected": int(metrics_data.get("rows_rejected", 0)),
            "nulls_handled": int(metrics_data.get("nulls_handled", 0)),
            "rows_published": int(metrics_data.get("rows_published", 0)),
            "as_of": as_of
        },
        "freshness_indicator": f"NOMINAL (Aligned with AS_OF: {as_of})",
        "reasons": list(set(reasons))
    }


def get_grid_location(grid_id: int) -> dict | None:
    """
    Retrieves spatial centroid and geometry reference for a grid cell.
    Explicitly excludes heavy polygon geometry.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT grid_id, centroid_lat, centroid_lon, geometry_ref
            FROM dim_grid
            WHERE grid_id = %s
            LIMIT 1;
        """, (grid_id,))
        row = cursor.fetchone()
        cursor.close()

    if not row:
        return None

    return {
        "grid_id": int(row["grid_id"]),
        "centroid_lat": float(row["centroid_lat"]),
        "centroid_lon": float(row["centroid_lon"]),
        "geometry_ref": str(row["geometry_ref"])
    }


def get_grid_neighbours(grid_id: int, limit: int = 8) -> dict | None:
    """
    Calculates spatial neighbours by Haversine distance using dim_grid centroids.
    """
    origin = get_grid_location(grid_id)
    if not origin:
        return None

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT grid_id, centroid_lat, centroid_lon FROM dim_grid WHERE grid_id != %s;", (grid_id,))
        rows = cursor.fetchall()
        cursor.close()

    lat1 = math.radians(origin["centroid_lat"])
    lon1 = math.radians(origin["centroid_lon"])

    distances = []
    for r in rows:
        lat2 = math.radians(float(r["centroid_lat"]))
        lon2 = math.radians(float(r["centroid_lon"]))
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        # Haversine formula
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist_km = 6371.0 * c

        distances.append({
            "grid_id": int(r["grid_id"]),
            "centroid_lat": float(r["centroid_lat"]),
            "centroid_lon": float(r["centroid_lon"]),
            "distance_km": round(dist_km, 4)
        })

    distances.sort(key=lambda x: x["distance_km"])
    return {
        "grid_id": grid_id,
        "neighbours": distances[:limit]
    }