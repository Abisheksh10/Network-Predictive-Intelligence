import sys
import pathlib

# Add project root (D:\project1) to python path
project_root = pathlib.Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os
from typing import Optional
from datetime import datetime, date
from contextlib import asynccontextmanager
from fastapi import FastAPI, Path, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from phase7.explain_risk import generate_risk_explanation
from schemas import (
    InvestigateRequest,
    NetworkSummaryResponse,
    GridActivityResponse,
    HotspotsResponse,
    SurgeHotspotsResponse,
    NetworkAlertsResponse,
    AlertSeverity,
    GridFeaturesResponse,
    PredictRiskRequest,
    PredictRiskResponse,
    PipelineStatusResponse,
    GridLocationResponse,
    GridNeighboursResponse,
    ExplainRiskRequest
)
import service

from pydantic import BaseModel, Field





from api.assistant import router as assistant_router
# MODEL_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "baseline_risk_model.joblib")
MODEL_PATH = r"d:\project1\artifacts\baseline_risk_model.joblib"    


class WhatIfSimulationRequest(BaseModel):
    """Pydantic schema for real-time frontend What-If slider adjustments."""
    avg_activity: float = Field(default=2500.0, ge=0.0)
    activity_growth: float = Field(default=0.45, ge=-1.0, le=10.0)
    active_hours: float = Field(default=24.0, ge=0.0, le=24.0)
    peak_ratio: float = Field(default=2.1, ge=1.0)
    variability: float = Field(default=0.5, ge=0.0)
    internet_share: float = Field(default=0.75, ge=0.0, le=1.0)
    immediate_ratio: float = Field(default=1.35, ge=0.0, le=10.0)
    hour: int = Field(default=23, ge=0, le=23)
    dayofweek: int = Field(default=3, ge=0, le=6)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"FATAL: Production ML Model artifact not found at {MODEL_PATH}")
    service.load_ml_model(MODEL_PATH)
    print(f"Successfully loaded Production ML Model from: {MODEL_PATH}")

    yield

    # Shutdown logic
    print("Application shutting down...")


app = FastAPI(
    title="Telecom Network Intelligence API",
    description="Operational REST endpoints for Network Operations Center (NOC) analytics, operational monitoring, and predictive risk intelligence.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(assistant_router)
# ============================================================================
# API1: GET /network/summary
# ============================================================================

@app.get(
    "/network/summary",
    response_model=NetworkSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Network Activity Summary",
    tags=["Network Operations"]
)
def get_network_summary(
    as_of: Optional[datetime] = Query(
        None,
        description="Optional effective timestamp cutoff (ISO format: YYYY-MM-DDTHH:MM:SS)."
    ),
    start_time: Optional[datetime] = Query(
        None,
        description="Optional range start timestamp (ISO format: YYYY-MM-DDTHH:MM:SS)."
    ),
    end_time: Optional[datetime] = Query(
        None,
        description="Optional range end timestamp (ISO format: YYYY-MM-DDTHH:MM:SS)."
    ),
    filter_date: Optional[date] = Query(
        None,
        alias="date",
        description="Optional single date filter (YYYY-MM-DD)."
    ),
    filter_hour: Optional[int] = Query(
        None,
        alias="hour",
        ge=0,
        le=23,
        description="Optional single hour filter (0-23)."
    )
):
    try:
        return service.get_network_summary(
            as_of=as_of,
            start_time=start_time,
            end_time=end_time,
            filter_date=filter_date,
            filter_hour=filter_hour
        )
    except ConnectionError as ce:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database service unavailable: {str(ce)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error computing network summary: {str(e)}"
        )


# ============================================================================
# API2: GET /network/grid/{grid_id}
# ============================================================================

@app.get(
    "/network/grid/{grid_id}",
    response_model=GridActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Grid Activity Drill-Down Time Series",
    tags=["Grid Analytics"]
)
def get_grid_activity(
    grid_id: int = Path(
        ...,
        description="Milan grid cell ID (must be between 1 and 10000)",
        examples=[4821]
    ),
    filter_date: Optional[date] = Query(None, alias="date"),
    filter_hour: Optional[int] = Query(None, alias="hour", ge=0, le=23),
    as_of: Optional[datetime] = Query(None)
):
    if not (1 <= grid_id <= 10000):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grid ID {grid_id} is out of valid bounds [1, 10000]."
        )

    try:
        result = service.get_grid_activity(
            grid_id=grid_id,
            filter_date=filter_date,
            filter_hour=filter_hour,
            as_of=as_of
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Grid ID {grid_id} not found in reference grid."
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving grid activity: {str(e)}"
        )



# ============================================================================
# API3: GET /network/hotspots
# ============================================================================

@app.get(
    "/network/hotspots",
    response_model=HotspotsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Ranked Operational Hotspots",
    tags=["Operational Intelligence"]
)
def get_hotspots(
    limit: int = Query(10, ge=1, le=1000),
    as_of: Optional[datetime] = Query(None)
):
    try:
        return service.get_hotspots(limit=limit, as_of=as_of)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving hotspots: {str(e)}"
        )


# ============================================================================
# API3: GET /network/hotspots/surge
# ============================================================================


#c5 done by claude
@app.get(
    "/network/hotspots/surge",
    response_model=SurgeHotspotsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Grids Ranked by Sharpest Activity Increase vs Baseline",
    tags=["Operational Intelligence"]
)
def get_surge_hotspots(
    limit: int = Query(10, ge=1, le=1000),
    as_of: Optional[datetime] = Query(None)
):
    try:
        return service.get_surge_grids(limit=limit, as_of=as_of)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving surge hotspots: {str(e)}"
        )


# ============================================================================
# API3: GET /network/alerts
# ============================================================================

@app.get(
    "/network/alerts",
    response_model=NetworkAlertsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Operational Network Alerts",
    tags=["Operational Intelligence"]
)
def get_network_alerts(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[AlertSeverity] = Query(None),
    as_of: Optional[datetime] = Query(None)
):
    try:
        return service.get_network_alerts(limit=limit, severity=severity, as_of=as_of)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving alerts: {str(e)}"
        )


# ============================================================================
# API4: GET /network/grid/{grid_id}/features
# ============================================================================

@app.get(
    "/network/grid/{grid_id}/features",
    response_model=GridFeaturesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get ML2 Grid Feature Vector",
    tags=["Machine Learning & Features"]
)
def get_grid_features(
    grid_id: int = Path(..., description="Milan grid cell ID", examples=[4821]),
    as_of: Optional[datetime] = Query(None)
):
    if not (1 <= grid_id <= 10000):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grid ID {grid_id} is outside valid bounds [1, 10000]."
        )

    try:
        features = service.get_grid_features(grid_id=grid_id, as_of=as_of)
        if features is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No pre-computed ML features exist for Grid ID {grid_id}."
            )
        return features
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading features: {str(e)}"
        )


# ============================================================================
# API5: POST /network/predict-risk (REAL ML5 INFERENCE)
# ============================================================================

@app.post(
    "/network/predict-risk",
    status_code=status.HTTP_200_OK,
    summary="Predict Grid Operational Risk",
    tags=["Machine Learning & Inference"]
)
def predict_grid_risk(payload: PredictRiskRequest):
    """
    Evaluates 24-hour historical telemetry prior to the given timestamp for a grid cell.
    Applies the trained HistGradientBoosting model using all 10 dynamic features 
    and the learned optimal decision threshold.
    """
    try:
        return service.predict_network_risk(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference engine failure: {str(e)}"
        )
@app.get(
    "/network/model/info",
    status_code=status.HTTP_200_OK,
    summary="Get Active Model Metadata & Optimal Threshold",
    tags=["Machine Learning & Inference"]
)
def get_model_info():
    """Returns the trained model type, 10 feature names, optimal threshold, and validation metrics."""
    try:
        if hasattr(service, "get_model_metadata"):
            return service.get_model_metadata()
        import joblib
        art = joblib.load(MODEL_PATH)
        return {
            "model_type": type(art["model"]).__name__,
            "features": art.get("features", []),
            "optimal_threshold": round(float(art.get("optimal_threshold", 0.7046)), 4),
            "metrics": art.get("metrics", {})
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading model metadata: {str(e)}"
        )

# ============================================================================
# CLAUDE SPECIFIC OPERATIONS TOOLS
# ============================================================================

@app.post(
    "/network/anamoly_score",
    status_code=status.HTTP_200_OK,
    summary="Get Anomaly Score for Grid (Claude Operations)",
    tags=["Claude Operations Tools"]
)
def get_grid_anomaly_score_endpoint(
    grid_id: int = Query(..., ge=1, le=10000),
    timestamp: datetime = Query(...)
):
    try:
        return service.get_grid_anomaly_score(grid_id=grid_id, timestamp=timestamp)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating anomaly score: {str(e)}"
        )


@app.post(
    "/network/total_activity",
    status_code=status.HTTP_200_OK,
    summary="Get Total Cumulative Activity for Grid (Claude Operations)",
    tags=["Claude Operations Tools"]
)
def get_grid_total_activity_endpoint(
    grid_id: int = Query(..., ge=1, le=10000)
):
    try:
        return service.get_grid_total_activity(grid_id=grid_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading total activity: {str(e)}"
        )
        


# ============================================================================
# API6: GET /pipeline/status
# ============================================================================

@app.get(
    "/pipeline/status",
    response_model=PipelineStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Operational Pipeline Health & Freshness",
    tags=["Operational Support"]
)
def get_pipeline_status():
    """
    Exposes the DE7/DE8 machine-readable pipeline status record.
    Provides a top-level `healthy` boolean, row audit metrics, and AS_OF timestamp.
    """
    return service.get_pipeline_status()


# ============================================================================
# API6: GET /network/grid/{grid_id}/location
# ============================================================================

@app.get(
    "/network/grid/{grid_id}/location",
    response_model=GridLocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Grid Spatial Location (Centroid)",
    tags=["Spatial Operations"]
)
def get_grid_location(
    grid_id: int = Path(..., description="Milan grid cell ID", examples=[4821])
):
    loc = service.get_grid_location(grid_id)
    if not loc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grid ID {grid_id} not found in dim_grid spatial dimension."
        )
    return loc


# ============================================================================
# API6 (Optional): GET /network/grid/{grid_id}/neighbours
# ============================================================================

@app.get(
    "/network/grid/{grid_id}/neighbours",
    response_model=GridNeighboursResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Surrounding Grid Cells by Distance",
    tags=["Spatial Operations"]
)
def get_grid_neighbours(
    grid_id: int = Path(..., ge=1, le=10000, description="Milan grid cell ID", examples=[4821]),
    limit: int = Query(8, ge=1, le=30, description="Number of nearest cells to return")
):
    """
    Returns nearby grid IDs sorted by centroid distance (Haversine).
    Allows Claude to assess whether anomalies are isolated or clustered.
    """
    result = service.get_grid_neighbours(grid_id=grid_id, limit=limit)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grid ID {grid_id} not found."
        )
    return result

# @app.post(
#     "/network/investigate",
#     status_code=status.HTTP_200_OK,
#     summary="Run Autonomous Claude RCA Agent for Grid",
#     tags=["Claude Operations Tools"]
# )
# def run_investigation_endpoint(payload: InvestigateRequest):
#     """
#     Invokes the autonomous NOC investigation agent from c14_agent.py.
#     Returns structured root-cause evidence, pipeline health audit, and operational checks.
#     """
#     if not (1 <= payload.grid_id <= 10000):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Grid ID {payload.grid_id} must be between 1 and 10000."
#         )
#     try:
#         # If c14_agent.py is in phase7, ensure project root is on sys.path
#         from phase7.c14_agent import run_headless_investigation
#         report = run_headless_investigation(grid_id=payload.grid_id)
#         return report
#     except Exception as e:
#         # Fallback if import path differs
#         try:
            
#             return c14_agent.run_headless_investigation(grid_id=payload.grid_id)
#         except Exception as err:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=f"Investigation agent failed: {str(err)}"
#             )
  

# ----------------------------------------------------------------------------
# PHASE 7: CLAUDE DIAGNOSTIC EXPLANATION ENDPOINT
# ----------------------------------------------------------------------------


@app.post(
    "/network/explain-risk",
    status_code=status.HTTP_200_OK,
    summary="Generate Claude Root-Cause Diagnostic Narrative",
    tags=["Claude Operations Tools"]
)
def explain_risk_endpoint(payload: ExplainRiskRequest):
    try:
        from phase7.explain_risk import generate_risk_explanation
        result = generate_risk_explanation(
            grid_id=payload.grid_id,
            timestamp=payload.timestamp,
            risk_score=payload.risk_score,
            risk_level=payload.risk_level,
            features=payload.features
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating diagnostic narrative: {str(e)}"
        )
        
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)








