"""
Pydantic schemas for the Security Event Audit Log.

Each event in the chain contains:
  - event_id        : UUID primary key
  - event_type      : Category of security event
  - user_id         : UUID of the actor (nullable for system events)
  - machine_id      : UUID of the related machine (nullable)
  - session_id      : UUID of the maintenance session (nullable)
  - event_data      : Arbitrary JSON payload describing the event
  - previous_hash   : SHA-256 hash of the PREVIOUS event's current_hash (or 64 zeros for genesis)
  - current_hash    : SHA-256 hash of (event content + previous_hash) — computed server-side
  - created_at      : ISO-8601 timestamp

Hash chaining guarantees tamper-evidence: altering any past event
breaks the chain for all subsequent events.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

class AuditEventType(str, Enum):
    # Authentication & Access
    LOGIN                   = "LOGIN"
    LOGOUT                  = "LOGOUT"
    AUTH_FAILURE            = "AUTH_FAILURE"
    UNAUTHORIZED_ACCESS     = "UNAUTHORIZED_ACCESS"

    # Maintenance Lifecycle
    MAINTENANCE_CREATED     = "MAINTENANCE_CREATED"
    MAINTENANCE_ASSIGNED    = "MAINTENANCE_ASSIGNED"
    MAINTENANCE_APPROVED    = "MAINTENANCE_APPROVED"
    MAINTENANCE_STARTED     = "MAINTENANCE_STARTED"
    MAINTENANCE_COMPLETED   = "MAINTENANCE_COMPLETED"

    # PLC Integrity
    PLC_BASELINE_SET        = "PLC_BASELINE_SET"
    PLC_INTEGRITY_CHECKED   = "PLC_INTEGRITY_CHECKED"
    PLC_HASH_MISMATCH       = "PLC_HASH_MISMATCH"
    PLC_TAMPER_DETECTED     = "PLC_TAMPER_DETECTED"

    # Configuration Changes
    CONFIG_CHANGE_DETECTED  = "CONFIG_CHANGE_DETECTED"
    CONFIG_CHANGE_AUTHORIZED= "CONFIG_CHANGE_AUTHORIZED"
    CONFIG_CHANGE_REJECTED  = "CONFIG_CHANGE_REJECTED"

    # Risk & Security
    RISK_ASSESSED           = "RISK_ASSESSED"
    CRITICAL_RISK_FLAGGED   = "CRITICAL_RISK_FLAGGED"
    SAFETY_INTERLOCK_ALERT  = "SAFETY_INTERLOCK_ALERT"

    # Demo (safe simulated data only)
    DEMO_EVENT              = "DEMO_EVENT"
    DEMO_TAMPER_SIMULATED   = "DEMO_TAMPER_SIMULATED"


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class AuditEventCreate(BaseModel):
    """Input schema for recording a new audit event."""
    event_type: AuditEventType
    user_id: Optional[UUID] = None
    machine_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    event_data: Dict[str, Any] = Field(default_factory=dict)


class AuditEventResponse(BaseModel):
    """Full audit event as returned from the API."""
    model_config = {"from_attributes": True}

    event_id: UUID
    event_type: AuditEventType
    user_id: Optional[UUID]
    machine_id: Optional[UUID]
    session_id: Optional[UUID]
    event_data: Dict[str, Any]
    previous_hash: str  # 64-char hex SHA-256 (or 64 zeros for genesis)
    current_hash: str   # 64-char hex SHA-256
    created_at: datetime


class AuditEventListResponse(BaseModel):
    """Paginated list of audit events."""
    events: List[AuditEventResponse]
    total: int
    chain_length: int


# ---------------------------------------------------------------------------
# Integrity Verification
# ---------------------------------------------------------------------------

class ChainVerifyResponse(BaseModel):
    """
    Result of POST /api/logs/verify-integrity.

    If the chain is intact, valid=True and broken fields are None.
    If tampered, valid=False and the first broken event is identified.
    """
    valid: bool
    chain_length: int
    verified_count: int
    first_broken_event: Optional[UUID] = None
    expected_hash: Optional[str] = None     # What the chain expected
    calculated_hash: Optional[str] = None   # What we computed from event data
    message: str


# ---------------------------------------------------------------------------
# Demo Tamper Simulation
# ---------------------------------------------------------------------------

class TamperDemoResponse(BaseModel):
    """
    Result of POST /api/logs/demo-tamper.

    Creates a set of simulated demo events, then corrupts one in-memory
    to demonstrate what a tampered chain looks like. NO real data is
    modified — this operates purely on ephemeral simulated payloads.
    """
    message: str
    disclaimer: str
    chain_before_tamper: List[AuditEventResponse]
    tampered_event_index: int
    tampered_event_id: UUID
    verification_result: ChainVerifyResponse
