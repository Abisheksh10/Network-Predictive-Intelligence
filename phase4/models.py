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
# # API1 MODELS: NETWORK SUMMARY
# # ============================================================================

# class NetworkSummaryResponse(BaseModel):
#     total_activity: float = Field(..., description="Total network activity units observed in the reporting window")
#     active_grids: int = Field(..., description="Count of distinct active grid cells in the reporting window")
#     peak_hour: int = Field(..., description="Hour of day (0-23) with the highest cumulative activity")
#     top_grid: int = Field(..., description="Grid cell ID with the highest cumulative activity")
#     as_of: dt_datetime = Field(..., description="Effective reporting timestamp used for this response")
    
#     class Config:
#             json_schema_extra = {
#                 "example": {
#                     "total_activity": 823651800.13,
#                     "active_grids": 10000,
#                     "peak_hour": 17,
#                     "top_grid": 5161,
#                     "as_of": "2013-11-07T23:00:00"
#                 }
#             }


# # ============================================================================
# # API2 MODELS: GRID ACTIVITY DRILL-DOWN
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
# # API3 MODELS: HOTSPOTS & ALERTS
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
# # API4 MODELS: ML2 GRID FEATURES (STABLE CONTRACT)
# # ============================================================================

# class GridFeaturesResponse(BaseModel):
#     grid_id: int = Field(..., description="Milan grid cell ID (1-10000)")
    
#     # Exact ML2 Feature Set (Character-for-character)
#     avg_activity: float = Field(..., description="Mean activity across baseline window")
#     activity_growth: float = Field(..., description="Rate of activity volume expansion")
#     active_hours: int = Field(..., description="Number of active hours with activity > 0")
#     peak_ratio: float = Field(..., description="Ratio of peak hourly activity to mean activity")
#     variability: float = Field(..., description="Coefficient of variation (stddev / mean)")
#     internet_share: float = Field(..., description="Proportion of internet traffic to total activity")
#     feature_timestamp: dt_datetime = Field(..., description="Timestamp when feature vector was materialized")
    
#     # Quality & Freshness Metadata
#     freshness_status: FeatureFreshnessStatus = Field(..., description="Freshness categorization (FRESH, STALE, DEGRADED)")
#     freshness_hours: float = Field(..., description="Hours elapsed between feature materialization and as_of")
#     data_quality_status: str = Field(default="PASSED", description="Validation status from feature pipeline")
    
    

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



# # (Append this to D:\project1\phase4\models.py)

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
#     geometry_ref: str = Field(..., description="Reference pointer to static GeoJSON polygon (No full Polygon returned)")


# class NeighborGridItem(BaseModel):
#     grid_id: int = Field(..., description="Neighbor grid cell ID")
#     centroid_lon: float = Field(..., description="Neighbor centroid longitude")
#     centroid_lat: float = Field(..., description="Neighbor centroid latitude")
#     distance_km: float = Field(..., description="Euclidean distance in kilometers from source grid")


# class GridNeighborsResponse(BaseModel):
#     grid_id: int = Field(..., description="Source grid cell ID")
#     neighbor_count: int = Field(..., description="Count of neighboring grid cells returned")
#     neighbors: List[NeighborGridItem] = Field(..., description="List of nearby grid cells ordered by proximity")


from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Double,
    String,
    Date,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all database ORM models."""
    pass


# ============================================================================
# DIMENSION TABLES
# ============================================================================

class DimTime(Base):
    __tablename__ = "dim_time"

    time_key = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, unique=True, index=True)
    date = Column(Date, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    hour = Column(Integer, nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    is_weekend = Column(Integer, nullable=False)

    # Relationships
    facts = relationship("FactNetworkActivity", back_populates="time_dim")


class DimGrid(Base):
    __tablename__ = "dim_grid"

    grid_id = Column(Integer, primary_key=True)
    centroid_lon = Column(Double, nullable=False)
    centroid_lat = Column(Double, nullable=False)

    # Relationships
    facts = relationship("FactNetworkActivity", back_populates="grid_dim")
    features = relationship("GridFeatures", back_populates="grid_dim", uselist=False)


# ============================================================================
# FACT TABLES
# ============================================================================

class FactNetworkActivity(Base):
    __tablename__ = "fact_network_activity"

    fact_id = Column(BigInteger, primary_key=True, autoincrement=True)
    time_key = Column(BigInteger, ForeignKey("dim_time.time_key"), nullable=False, index=True)
    grid_id = Column(Integer, ForeignKey("dim_grid.grid_id"), nullable=False, index=True)
    sms_in = Column(Double, nullable=False, default=0.0)
    sms_out = Column(Double, nullable=False, default=0.0)
    call_in = Column(Double, nullable=False, default=0.0)
    call_out = Column(Double, nullable=False, default=0.0)
    internet_activity = Column(Double, nullable=False, default=0.0)
    total_sms = Column(Double, nullable=False, default=0.0)
    total_calls = Column(Double, nullable=False, default=0.0)
    total_activity = Column(Double, nullable=False, default=0.0, index=True)
    internet_share = Column(Double, nullable=False, default=0.0)

    # Relationships
    time_dim = relationship("DimTime", back_populates="facts")
    grid_dim = relationship("DimGrid", back_populates="facts")


# ============================================================================
# ML FEATURE STORE TABLE
# ============================================================================

class GridFeatures(Base):
    __tablename__ = "grid_features"

    grid_id = Column(Integer, ForeignKey("dim_grid.grid_id"), primary_key=True)
    avg_activity = Column(Double, nullable=False)
    activity_growth = Column(Double, nullable=False)
    active_hours = Column(Integer, nullable=False)
    peak_ratio = Column(Double, nullable=False)
    variability = Column(Double, nullable=False)
    internet_share = Column(Double, nullable=False)
    feature_timestamp = Column(DateTime, nullable=False, index=True)
    data_quality_status = Column(String(50), nullable=False, default="PASSED")

    # Relationships
    grid_dim = relationship("DimGrid", back_populates="features")