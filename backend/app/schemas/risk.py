"""
Pydantic schemas for the Deterministic Risk Engine & Prototype ML Anomaly Detector.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.changes import ChangeCategory, ChangeRiskLevel


class RiskAssessmentRequest(BaseModel):
    """Payload to evaluate risk and ML anomaly score for a configuration change."""
    category: ChangeCategory
    parameter_name: str
    old_value: Any
    new_value: Any
    is_expected: bool = False
    is_authorized: bool = False
    machine_code: str = "CNC-01"
    user_role: str = "MAINTENANCE_ENGINEER"
    session_id: Optional[UUID] = None
    change_id: Optional[UUID] = None


class RiskAssessmentResponse(BaseModel):
    """Authoritative risk assessment combining deterministic scoring and advisory ML."""
    # Deterministic Engine Outputs (Authoritative)
    risk_score: int = Field(..., ge=0, le=100, description="Deterministic rule-based risk score (0-100)")
    risk_level: ChangeRiskLevel = Field(..., description="Risk tier: LOW, MEDIUM, HIGH, CRITICAL")
    risk_reasons: List[str] = Field(..., description="Explanatory breakdown of why risk points were assigned")
    scoring_breakdown: Dict[str, Any] = Field(..., description="Itemized score components")

    # Prototype ML Anomaly Detection Outputs (Advisory Only)
    ai_anomaly_score: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Isolation Forest anomaly score (0-100). Strictly advisory.",
    )
    model_name: str = Field(
        "IsolationForest_v1.0-prototype",
        description="Name and version of the scikit-learn anomaly model",
    )
    ml_label: str = Field(
        "Prototype ML anomaly score",
        description="Mandatory label identifying ML output as advisory prototype",
    )
    ai_explanation: Optional[str] = Field(
        None,
        description="Explanation of feature deviations detected by Isolation Forest",
    )

    # Metadata & Governance
    evaluated_at: datetime
    rule_override_prevented: bool = Field(
        True,
        description="Always True — AI is strictly prevented from overriding deterministic rules",
    )
