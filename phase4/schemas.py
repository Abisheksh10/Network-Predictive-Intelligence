# from typing import List, Optional, Dict, Any
# from datetime import datetime as dt_datetime, date as dt_date
# from pydantic import BaseModel, Field
# from enum import Enum


# # ============================================================================
# # ENUMS
# # ============================================================================

# class AlertSeverity(str, Enum):
#     INFO = "INFO"
#     WARNING = "WARNING"
#     CRITICAL = "CRITICAL"


# class AlertStatus(str, Enum):
#     ACTIVE = "ACTIVE"
#     INVESTIGATING = "INVESTIGATING"
#     RESOLVED = "RESOLVED"


# class FeatureFreshnessStatus(str, Enum):
#     FRESH = "FRESH"
#     STALE = "STALE"
#     DEGRADED = "DEGRADED"


# class RiskLevel(str, Enum):
#     LOW = "LOW"
#     MEDIUM = "MEDIUM"
#     HIGH = "HIGH"
#     CRITICAL = "CRITICAL"


# # ============================================================================
# # API1 SCHEMAS: NETWORK SUMMARY
# # ============================================================================

# class NetworkSummaryResponse(BaseModel):
#     total_activity: float = Field(..., description="Total network activity units observed in the reporting window")
#     active_grids: int = Field(..., description="Count of distinct active grid cells in the reporting window")
#     peak_hour: int = Field(..., description="Hour of day (0-23) with the highest cumulative activity")
#     top_grid: int = Field(..., description="Grid cell ID with the highest cumulative activity")
#     as_of: dt_datetime = Field(..., description="Effective reporting timestamp used for this response")

#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "total_activity": 823651800.13,
#                 "active_grids": 10000,
#                 "peak_hour": 17,
#                 "top_grid": 5161,
#                 "as_of": "2013-11-07T23:00:00"
#             }
#         }


# # ============================================================================
# # API2 SCHEMAS: GRID ACTIVITY DRILL-DOWN
# # ============================================================================

# class GridHourlyActivityPoint(BaseModel):
#     timestamp: dt_datetime = Field(..., description="Hourly interval start timestamp")
#     date: dt_date = Field(..., description="Date of observation")
#     hour: int = Field(..., description="Hour of observation (0-23)")
#     sms_in: float
#     sms_out: float
#     call_in: float
#     call_out: float
#     internet_activity: float
#     total_sms: float
#     total_calls: float
#     total_activity: float
#     internet_share: float


# class GridActivityResponse(BaseModel):
#     grid_id: int = Field(..., description="Milan grid cell ID (1-10000)")
#     centroid_lon: float = Field(..., description="Grid centroid longitude")
#     centroid_lat: float = Field(..., description="Grid centroid latitude")
#     as_of: dt_datetime = Field(..., description="Effective cutoff timestamp")
#     data_points_count: int = Field(..., description="Number of hourly intervals returned")
#     series: List[GridHourlyActivityPoint] = Field(..., description="Chronological time series of activity observations")


# # ============================================================================
# # API3 SCHEMAS: HOTSPOTS & ALERTS (ML FORWARD-COMPATIBLE)
# # ============================================================================

# class HotspotItem(BaseModel):
#     grid_id: int = Field(..., description="Milan grid cell ID")
#     centroid_lon: float = Field(..., description="Grid centroid longitude")
#     centroid_lat: float = Field(..., description="Grid centroid latitude")
#     total_activity: float = Field(..., description="Cumulative total activity in the reporting window")
#     internet_activity: float = Field(..., description="Cumulative internet activity")
#     total_calls: float = Field(..., description="Cumulative call activity")
#     total_sms: float = Field(..., description="Cumulative SMS activity")
#     internet_share: float = Field(..., description="Ratio of internet activity to total activity")
#     rank: int = Field(..., description="Deterministic rank position")
#     risk_score: Optional[float] = None
#     risk_level: Optional[str] = None
#     model_version: Optional[str] = None


# class HotspotsResponse(BaseModel):
#     as_of: dt_datetime = Field(..., description="Effective reporting cutoff timestamp")
#     total_hotspots_returned: int = Field(..., description="Count of hotspot cells returned")
#     hotspots: List[HotspotItem] = Field(..., description="List of ranked operational hotspots")


# class NetworkAlertItem(BaseModel):
#     alert_id: str = Field(..., description="Unique deterministic alert identifier")
#     grid_id: int = Field(..., description="Milan grid cell ID (1-10000)")
#     timestamp: dt_datetime = Field(..., description="Hourly observation timestamp")
#     severity: AlertSeverity = Field(..., description="Operational alert severity level")
#     status: AlertStatus = Field(default=AlertStatus.ACTIVE, description="Current operational triage status")
#     alert_type: str = Field(..., description="Category of rule or operational anomaly trigger")
#     activity_measure: float = Field(..., description="Observed metric value triggering operational attention")
#     threshold_value: float = Field(..., description="Baseline or threshold reference value")
#     reason: str = Field(..., description="Human-readable explanation of the operational trigger")
#     risk_score: Optional[float] = None
#     risk_level: Optional[str] = None
#     model_version: Optional[str] = None
#     model_features: Optional[Dict[str, Any]] = None


# class NetworkAlertsResponse(BaseModel):
#     as_of: dt_datetime = Field(..., description="Effective reporting cutoff timestamp")
#     total_alerts_returned: int = Field(..., description="Count of alerts returned")
#     alerts: List[NetworkAlertItem] = Field(..., description="List of operational alerts")


# # ============================================================================
# # API4 SCHEMAS: ML2 GRID FEATURES
# # ============================================================================

# class GridFeaturesResponse(BaseModel):
#     grid_id: int = Field(..., description="Milan grid cell ID (1-10000)")
#     avg_activity: float = Field(..., description="Mean activity across baseline window")
#     activity_growth: float = Field(..., description="Rate of activity volume expansion")
#     active_hours: int = Field(..., description="Number of active hours with activity > 0")
#     peak_ratio: float = Field(..., description="Ratio of peak hourly activity to mean activity")
#     variability: float = Field(..., description="Coefficient of variation (stddev / mean)")
#     internet_share: float = Field(..., description="Proportion of internet traffic to total activity")
#     feature_timestamp: dt_datetime = Field(..., description="Timestamp when feature vector was materialized")
#     freshness_status: FeatureFreshnessStatus = Field(..., description="Freshness categorization (FRESH, STALE, DEGRADED)")
#     freshness_hours: float = Field(..., description="Hours elapsed between feature materialization and as_of")
#     data_quality_status: str = Field(default="PASSED", description="Validation status from feature pipeline")


# # ============================================================================
# # API5 SCHEMAS: PREDICTIVE RISK
# # ============================================================================

# class PredictRiskRequest(BaseModel):
#     grid_id: int = Field(..., ge=1, le=10000, description="Milan grid cell ID (must be between 1 and 10000)")
#     avg_activity: float = Field(..., ge=0.0, description="Mean historical hourly activity")
#     activity_growth: float = Field(..., description="Hourly activity growth rate relative to baseline")
#     active_hours: int = Field(..., ge=0, le=168, description="Number of active operating hours observed")
#     peak_ratio: float = Field(..., ge=1.0, description="Peak-to-mean activity ratio (must be >= 1.0)")
#     variability: float = Field(..., ge=0.0, description="Activity coefficient of variation (stddev / mean)")
#     internet_share: float = Field(..., ge=0.0, le=1.0, description="Internet activity proportion (between 0.0 and 1.0)")

#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "grid_id": 5161,
#                 "avg_activity": 1065.38,
#                 "activity_growth": 0.35,
#                 "active_hours": 168,
#                 "peak_ratio": 2.85,
#                 "variability": 0.45,
#                 "internet_share": 0.94
#             }
#         }


# class PredictRiskResponse(BaseModel):
#     grid_id: int = Field(..., description="Milan grid cell ID evaluated")
#     risk_score: float = Field(..., ge=0.0, le=1.0, description="Predictive operational risk score bounded in [0.0, 1.0]")
#     risk_level: RiskLevel = Field(..., description="Operational attention classification level (LOW, MEDIUM, HIGH, CRITICAL)")
#     model_version: str = Field(..., description="ML model identifier or stub implementation tag")
#     explanation_note: str = Field(..., description="Diagnostic note indicating stub status or feature attribution summary")
#     prediction_timestamp: dt_datetime = Field(default_factory=dt_datetime.utcnow, description="UTC timestamp of inference")


# # ============================================================================
# # PIPELINE & GEOSPATIAL SCHEMAS (API6 / RE4)
# # ============================================================================

# class PipelineMetrics(BaseModel):
#     rows_in: int = Field(..., description="Total raw input rows processed across the batch")
#     rows_rejected: int = Field(..., description="Count of invalid/quarantined records")
#     nulls_handled: int = Field(..., description="Count of activity nulls converted to zero")
#     rows_published: int = Field(..., description="Total canonical fact rows loaded into analytics warehouse")


# class PipelineStatusResponse(BaseModel):
#     healthy: bool = Field(..., description="Top-level boolean status indicating if data is reliable and fresh")
#     run_id: str = Field(..., description="Unique orchestration run identifier")
#     run_timestamp: dt_datetime = Field(..., description="Timestamp when the pipeline run finished")
#     as_of: dt_datetime = Field(..., description="Effective data cutoff timestamp present in the analytics warehouse")
#     freshness_indicator: str = Field(..., description="Human-readable freshness assessment (e.g. 'CURRENT', 'STALE')")
#     freshness_hours: float = Field(..., description="Hours elapsed between as_of and current time")
#     overall_status: str = Field(..., description="Execution status ('SUCCESS', 'FAILED')")
#     tasks: Dict[str, str] = Field(..., description="Per-task execution status breakdown")
#     metrics: PipelineMetrics = Field(..., description="Row counts and null handling audit figures")
#     reasons: List[str] = Field(default_factory=list, description="List of failure or degradation reasons if healthy is false")


# class GridLocationResponse(BaseModel):
#     grid_id: int = Field(..., ge=1, le=10000, description="Milan grid cell ID")
#     centroid_lon: float = Field(..., description="Grid centroid longitude")
#     centroid_lat: float = Field(..., description="Grid centroid latitude")
#     geometry_ref: str = Field(..., description="Reference pointer to static GeoJSON polygon")


# class NeighborGridItem(BaseModel):
#     grid_id: int = Field(..., description="Neighbor grid cell ID")
#     centroid_lon: float = Field(..., description="Neighbor centroid longitude")
#     centroid_lat: float = Field(..., description="Neighbor centroid latitude")
#     distance_km: float = Field(..., description="Euclidean distance in kilometers from source grid")


# class GridNeighborsResponse(BaseModel):
#     grid_id: int = Field(..., description="Source grid cell ID")
#     neighbor_count: int = Field(..., description="Count of neighboring grid cells returned")
#     neighbors: List[NeighborGridItem] = Field(..., description="List of nearby grid cells ordered by proximity")


from typing import List, Optional, Dict, Any
from datetime import datetime as dt_datetime, date as dt_date,timezone
from pydantic import BaseModel, Field
from enum import Enum


class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    
class AlertStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"


class FeatureFreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    DEGRADED = "DEGRADED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    CRITICAL = "CRITICAL"


class NetworkSummaryResponse(BaseModel):
    total_activity: float = Field(..., description="Total network activity units observed in the reporting window")
    active_grids: int = Field(..., description="Count of distinct active grid cells in the reporting window")
    peak_hour: int = Field(..., description="Hour of day (0-23) with the highest cumulative activity")
    top_grid: int = Field(..., description="Grid cell ID with the highest cumulative activity")
    as_of: dt_datetime = Field(..., description="Effective reporting timestamp used for this response")
    window_start: Optional[dt_datetime] = Field(None, description="Optional start timestamp for bounded reporting windows")
    class Config:
        json_schema_extra = {
            "example": {
                "total_activity": 823651800.13,
                "active_grids": 10000,
                "peak_hour": 17,
                "top_grid": 5161,
                "as_of": "2013-11-07T23:00:00",
                "window_start": "2013-11-01T00:00:00"
            }
        }
class GridHourlyActivityPoint(BaseModel):
    timestamp: dt_datetime
    date: dt_date
    hour: int
    sms_in: float
    sms_out: float
    call_in: float
    call_out: float
    internet_activity: float
    total_sms: float
    total_calls: float
    total_activity: float
    internet_share: float


class GridActivityResponse(BaseModel):
    grid_id: int
    centroid_lon: float
    centroid_lat: float
    as_of: dt_datetime
    data_points_count: int
    series: List[GridHourlyActivityPoint]


class HotspotItem(BaseModel):
    grid_id: int
    centroid_lon: float
    centroid_lat: float
    total_activity: float
    internet_activity: float
    total_calls: float
    total_sms: float
    internet_share: float
    rank: int
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    model_version: Optional[str] = None


class HotspotsResponse(BaseModel):
    as_of: dt_datetime
    total_hotspots_returned: int
    hotspots: List[HotspotItem]

#c5 done by claude code
class SurgeGridItem(BaseModel):
    grid_id: int
    centroid_lon: float
    centroid_lat: float
    current_activity: float = Field(..., description="Mean total activity over the recent 24h window")
    baseline_activity: float = Field(..., description="Mean total activity over the prior 24h baseline window")
    surge_score: float = Field(..., description="Proportional increase of current_activity over baseline_activity; 0.0 when baseline_activity <= 0")
    rank: int

#c5 done by claude code
class SurgeHotspotsResponse(BaseModel):
    as_of: dt_datetime
    total_grids_returned: int
    grids: List[SurgeGridItem]


class NetworkAlertItem(BaseModel):
    alert_id: str
    grid_id: int
    timestamp: dt_datetime
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    alert_type: str
    activity_measure: float
    threshold_value: float
    reason: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    model_version: Optional[str] = None
    model_features: Optional[Dict[str, Any]] = None


class NetworkAlertsResponse(BaseModel):
    as_of: dt_datetime
    total_alerts_returned: int
    alerts: List[NetworkAlertItem]


class GridFeaturesResponse(BaseModel):
    grid_id: int
    avg_activity: float
    activity_growth: float
    active_hours: int
    peak_ratio: float
    variability: float
    internet_share: float
    feature_timestamp: dt_datetime
    freshness_status: FeatureFreshnessStatus
    freshness_hours: float
    data_quality_status: str = "PASSED"


class PredictRiskRequest(BaseModel):
    grid_id: int = Field(..., ge=1, le=10000, description="Milan grid cell ID (1 to 10000)")
    timestamp: dt_datetime = Field(..., description="Feature cutoff timestamp t (ISO-8601). Mandatory coordinate.")

    class Config:
        json_schema_extra = {
            "example": {
                "grid_id": 5161,
                "timestamp": "2013-11-07T23:00:00"
            }
        }
class EvaluatedFeatureSummary(BaseModel):
    avg_activity: float
    activity_growth: float
    active_hours: int
    peak_ratio: float
    variability: float
    internet_share: float


class PredictRiskResponse(BaseModel):
    grid_id: int
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Continuous probability of operational attention [0.0 - 1.0]")
    risk_level: RiskLevel = Field(..., description="Binary operational verdict: LOW or CRITICAL")
    model_version: str
    explanation_note: str
    feature_timestamp: dt_datetime
    prediction_timestamp: dt_datetime = Field(default_factory=lambda: dt_datetime.now(timezone.utc))
    features_used: Optional[EvaluatedFeatureSummary] = None
    





# ============================================================================
# API 6: Operational Support & Spatial Schemas
# ============================================================================

class PipelineMetrics(BaseModel):
    rows_in: int = Field(..., description="Number of rows detected in landing/raw")
    rows_rejected: int = Field(..., description="Rows quarantined during validation")
    nulls_handled: int = Field(..., description="Null values imputed or filtered")
    rows_published: int = Field(..., description="Clean rows published to fact table")
    as_of: str = Field(..., description="Latest available telemetry timestamp (ISO)")

class PipelineStatusResponse(BaseModel):
    healthy: bool = Field(..., description="Top-level pipeline health flag")
    run_id: str = Field(..., description="Unique orchestrator run identifier")
    run_timestamp: str = Field(..., description="Timestamp of when the pipeline ran")
    pipeline_status: str = Field(..., description="Overall status: SUCCESS, FAILED, etc.")
    tasks: dict[str, str] = Field(..., description="Status breakdown per task")
    metrics: PipelineMetrics = Field(..., description="Data quality & row audit counters")
    freshness_indicator: str = Field(..., description="Analytics layer age description")
    reasons: list[str] = Field(default_factory=list, description="Reasons populated if unhealthy")

class GridLocationResponse(BaseModel):
    grid_id: int = Field(..., ge=1, le=10000, description="Milan cell ID")
    centroid_lat: float = Field(..., description="Centroid latitude coordinate")
    centroid_lon: float = Field(..., description="Centroid longitude coordinate")
    geometry_ref: str = Field(..., description="Reference pointer to GeoJSON asset (no raw polygon)")

class NeighbourGrid(BaseModel):
    grid_id: int
    centroid_lat: float
    centroid_lon: float
    distance_km: float

class GridNeighboursResponse(BaseModel):
    grid_id: int
    neighbours: list[NeighbourGrid]
    

class InvestigateRequest(BaseModel):
    grid_id: int
    

class ExplainRiskRequest(BaseModel):
    grid_id: int
    timestamp: Optional[str] = "2013-11-07 23:00:00"
    risk_score: float
    risk_level: str
    features: Dict[str, Any]