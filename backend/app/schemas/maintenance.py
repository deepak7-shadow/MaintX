"""
Pydantic schemas for maintenance requests, sessions, and approvals.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MaintenanceType(str, Enum):
    SCHEDULED_MAINTENANCE = "SCHEDULED_MAINTENANCE"
    EMERGENCY_REPAIR = "EMERGENCY_REPAIR"
    FIRMWARE_UPDATE = "FIRMWARE_UPDATE"
    LOGIC_OPTIMIZATION = "LOGIC_OPTIMIZATION"
    SECURITY_PATCH = "SECURITY_PATCH"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class RequestStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    LOCKED = "LOCKED"


# ---------------------------------------------------------------------------
# Create / Update request bodies
# ---------------------------------------------------------------------------


class ExpectedChange(BaseModel):
    parameter: str
    from_value: Any
    to_value: Any
    reason: Optional[str] = None


class CreateMaintenanceRequest(BaseModel):
    machine_id: UUID
    reason: str = Field(..., min_length=10, max_length=2000)
    maintenance_type: MaintenanceType = MaintenanceType.SCHEDULED_MAINTENANCE
    priority: Priority = Priority.MEDIUM
    expected_changes: List[ExpectedChange] = []
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None


class AssignEngineerRequest(BaseModel):
    engineer_id: UUID


class ApproveMaintenanceRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    comments: Optional[str] = Field(None, max_length=1000)


class StartSessionRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)


class CompleteSessionRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=2000)
    verification_status: str = Field(
        "VERIFIED", pattern="^(VERIFIED|REVIEW_REQUIRED|FAILED)$"
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MaintenanceRequestResponse(BaseModel):
    id: UUID
    request_number: str
    machine_id: UUID
    engineer_id: UUID
    supervisor_id: Optional[UUID] = None
    reason: str
    maintenance_type: str
    expected_changes: List[Any] = []
    priority: str
    approval_status: str
    status: str
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MaintenanceSessionResponse(BaseModel):
    id: UUID
    request_id: UUID
    machine_id: UUID
    engineer_id: UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    session_status: str
    baseline_captured: bool
    verification_status: str
    notes: Optional[str] = None
    created_at: datetime


class MaintenanceModeStatus(BaseModel):
    """Current maintenance mode status for a machine."""
    machine_code: str
    machine_id: UUID
    in_maintenance: bool
    active_session_id: Optional[UUID] = None
    active_request_number: Optional[str] = None
    engineer_id: Optional[UUID] = None
    started_at: Optional[datetime] = None
    machine_locked: bool
    message: str
