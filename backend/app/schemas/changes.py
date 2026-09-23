"""
Pydantic schemas for the Change Detection Engine.

Tracks configuration and logic changes across 6 critical operational categories:
  1. PARAMETERS    — operational setpoints (motor speed, temp, pressure, mode)
  2. PLC_LOGIC     — ladder logic programs, rungs, and PLC version
  3. NETWORK       — IP address, subnet, gateway, network topology
  4. FIREWALL      — firewall rules, open ports, default packet policies
  5. FIRMWARE      — device firmware and bootloader versions
  6. SAFETY_CONFIG — safety category, physical/logical interlocks, E-stop monitoring
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ChangeCategory(str, Enum):
    PARAMETERS = "PARAMETERS"
    PLC_LOGIC = "PLC_LOGIC"
    NETWORK = "NETWORK"
    FIREWALL = "FIREWALL"
    FIRMWARE = "FIRMWARE"
    SAFETY_CONFIG = "SAFETY_CONFIG"


class ChangeRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_AUTHORIZED = "AUTO_AUTHORIZED"


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------


class ChangeRecordCreate(BaseModel):
    """Schema for submitting or recording a configuration change."""
    session_id: UUID
    machine_id: UUID
    category: ChangeCategory
    parameter_name: str
    old_value: Any
    new_value: Any
    reason: str
    metadata: Optional[Dict[str, Any]] = None


class ChangeRecordResponse(BaseModel):
    """Authoritative representation of a tracked configuration change."""
    id: UUID
    session_id: UUID
    machine_id: UUID
    user_id: UUID
    user_role: str
    category: ChangeCategory
    parameter_name: str
    old_value: Any
    new_value: Any
    reason: str
    is_expected: bool
    is_authorized: bool
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: ChangeRiskLevel
    ai_anomaly_score: Optional[int] = Field(None, ge=0, le=100)
    requires_supervisor_approval: bool
    approval_status: ChangeApprovalStatus
    timestamp: datetime
    authorization_notes: Optional[str] = None


class ChangeReviewRequest(BaseModel):
    """Supervisor or Admin review decision for a pending/unauthorized change."""
    approved: bool
    notes: Optional[str] = None


class ChangeDetectionRunRequest(BaseModel):
    """Request payload to detect changes against a maintenance session baseline."""
    session_id: UUID
    current_state: Dict[str, Any] = Field(
        ...,
        description=(
            "Current or target machine state including parameters, network, "
            "firewall, firmware, safety_config, and plc_program."
        ),
    )


class ChangeDetectionRunResponse(BaseModel):
    """Aggregated summary of a change detection run."""
    session_id: UUID
    machine_id: UUID
    total_changes: int
    expected_count: int
    unexpected_count: int
    unauthorized_count: int
    critical_count: int
    high_risk_count: int
    overall_risk: ChangeRiskLevel
    requires_supervisor_review: bool
    changes: List[ChangeRecordResponse]
    detection_timestamp: datetime
