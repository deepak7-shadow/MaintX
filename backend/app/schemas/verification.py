"""
Verification Schemas — Final Maintenance Verification Models & Enums.

Defines the data structures for comparing trusted baseline + approved changes
against actual final machine state + actual PLC logic.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VerificationStatus(str, Enum):
    """Overall final status of the maintenance verification."""
    VERIFIED = "VERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class ChangeClassification(str, Enum):
    """Classification of each individual discrepancy between expected and actual state."""
    EXPECTED = "EXPECTED"
    UNEXPECTED = "UNEXPECTED"
    UNAUTHORIZED = "UNAUTHORIZED"
    UNRESOLVED = "UNRESOLVED"


class PLCVerificationStatus(str, Enum):
    """Status of the PLC logic integrity comparison."""
    VERIFIED = "VERIFIED"
    HASH_MISMATCH = "HASH_MISMATCH"
    SAFETY_INTERLOCK_COMPROMISED = "SAFETY_INTERLOCK_COMPROMISED"
    UNAPPROVED_LOGIC = "UNAPPROVED_LOGIC"


class ParameterComparison(BaseModel):
    """Detailed comparison for a single parameter or component."""
    parameter_name: str
    category: str
    baseline_value: Any
    approved_value: Any
    actual_value: Any
    classification: ChangeClassification
    risk_level: str
    details: str
    is_critical: bool = False


class PLCVerificationDetail(BaseModel):
    """Detailed result of the PLC logic verification."""
    baseline_hash: str
    approved_hash: Optional[str] = None
    actual_hash: str
    hash_matches: bool
    semantic_diff: Dict[str, Any]
    safety_changes_detected: bool
    safety_interlock_compromised: bool
    approved_logic_matches: bool
    status: PLCVerificationStatus
    details: List[str] = Field(default_factory=list)


class VerificationResultResponse(BaseModel):
    """Full verification assessment returned by the verification engine and API."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    machine_id: Optional[UUID] = None
    verified_by: Optional[UUID] = None
    final_status: VerificationStatus
    plc_integrity_passed: bool
    all_changes_authorized: bool
    unresolved_critical_changes: int = 0
    expected_changes_count: int = 0
    unexpected_changes_count: int = 0
    unauthorized_changes_count: int = 0
    unresolved_changes_count: int = 0
    parameters_comparison: List[ParameterComparison] = Field(default_factory=list)
    plc_verification: PLCVerificationDetail
    closure_allowed: bool
    message: str
    verified_at: datetime


class VerifySessionRequest(BaseModel):
    """Optional payload when running session verification, allowing simulated final state overrides."""
    final_machine_state: Optional[Dict[str, Any]] = None
    final_plc_logic: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
