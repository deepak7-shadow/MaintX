"""
Change Detection API Router.

Endpoints:
  - POST /api/changes/detect                 — Run automated change detection between baseline & current state
  - POST /api/changes                        — Record an individual configuration change
  - GET  /api/changes                        — List configuration changes (filterable)
  - GET  /api/changes/{change_id}            — Get single change
  - POST /api/changes/{change_id}/review     — Supervisor review (approve/reject)
  - GET  /api/changes/demo/expected-motor    — Demo: Expected motor change (3000 -> 3200) => EXPECTED, AUTHORIZED
  - GET  /api/changes/demo/unexpected-ip     — Demo: Unexpected IP change (192.168.10.20 -> 192.168.10.50) => UNEXPECTED, UNAUTHORIZED, HIGH RISK
  - GET  /api/changes/demo/safety-plc        — Demo: Safety PLC modification => CRITICAL, SUPERVISOR REVIEW REQUIRED
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_current_user,
    require_engineer,
    require_supervisor,
)
from app.schemas.auth import UserProfileResponse
from app.schemas.changes import (
    ChangeApprovalStatus,
    ChangeCategory,
    ChangeDetectionRunRequest,
    ChangeDetectionRunResponse,
    ChangeRecordCreate,
    ChangeRecordResponse,
    ChangeReviewRequest,
    ChangeRiskLevel,
)
from app.services import change_service
from app.services.change_engine import evaluate_change

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/changes", tags=["Change Detection & Authorization"])


# ---------------------------------------------------------------------------
# 1. Run automated change detection
# ---------------------------------------------------------------------------


@router.post(
    "/detect",
    response_model=ChangeDetectionRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run change detection on a maintenance session",
    description=(
        "Compares the session's captured baseline snapshot against the provided current state "
        "across all 6 categories (PARAMETERS, PLC_LOGIC, NETWORK, FIREWALL, FIRMWARE, SAFETY_CONFIG). "
        "Evaluates authorization policies and records all detected differences."
    ),
)
async def detect_changes(
    body: ChangeDetectionRunRequest,
    current_user: UserProfileResponse = Depends(require_engineer),
) -> ChangeDetectionRunResponse:
    return await change_service.run_change_detection(
        session_id=body.session_id,
        current_state=body.current_state,
        actor=current_user,
    )


# ---------------------------------------------------------------------------
# 2. Record individual change
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ChangeRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an individual configuration change",
    description="Submits a configuration change with automated policy evaluation and audit logging.",
)
async def create_change(
    body: ChangeRecordCreate,
    current_user: UserProfileResponse = Depends(require_engineer),
) -> ChangeRecordResponse:
    return await change_service.record_change(payload=body, actor=current_user)


# ---------------------------------------------------------------------------
# 3. List & Get changes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[ChangeRecordResponse],
    summary="List configuration changes",
    description="Query recorded configuration changes with optional filters.",
)
async def list_changes(
    session_id: Optional[UUID] = Query(None, description="Filter by maintenance session"),
    machine_id: Optional[UUID] = Query(None, description="Filter by machine ID"),
    category: Optional[ChangeCategory] = Query(None, description="Filter by change category"),
    risk_level: Optional[ChangeRiskLevel] = Query(None, description="Filter by risk level"),
    approval_status: Optional[ChangeApprovalStatus] = Query(None, description="Filter by approval status"),
    _: UserProfileResponse = Depends(get_current_user),
) -> List[ChangeRecordResponse]:
    return await change_service.list_changes(
        session_id=session_id,
        machine_id=machine_id,
        category=category,
        risk_level=risk_level,
        approval_status=approval_status,
    )


@router.get(
    "/{change_id}",
    response_model=ChangeRecordResponse,
    summary="Get configuration change details",
)
async def get_change(
    change_id: UUID,
    _: UserProfileResponse = Depends(get_current_user),
) -> ChangeRecordResponse:
    return await change_service.get_change(change_id)


# ---------------------------------------------------------------------------
# 4. Supervisor Review & Authorization
# ---------------------------------------------------------------------------


@router.post(
    "/{change_id}/review",
    response_model=ChangeRecordResponse,
    summary="Supervisor review and authorization",
    description=(
        "Approve or reject a pending or unauthorized configuration change. "
        "Strictly restricted to SUPERVISOR and ADMIN roles."
    ),
)
async def review_change(
    change_id: UUID,
    body: ChangeReviewRequest,
    current_user: UserProfileResponse = Depends(require_supervisor),
) -> ChangeRecordResponse:
    return await change_service.review_change(
        change_id=change_id,
        approved=body.approved,
        notes=body.notes,
        actor=current_user,
    )


# ---------------------------------------------------------------------------
# 5. Demonstration Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/demo/expected-motor",
    summary="Demo: Expected Motor Change (3000 -> 3200 RPM)",
    description=(
        "Demonstrates evaluation of an expected motor change (3000 -> 3200 RPM). "
        "Result: EXPECTED, AUTHORIZED."
    ),
)
async def demo_expected_motor(
    _: UserProfileResponse = Depends(get_current_user),
):
    expected_list = [
        {
            "category": "PARAMETERS",
            "parameter_name": "motor_speed_rpm",
            "from_value": 3000,
            "to_value": 3200,
            "reason": "Production cycle time reduction",
        }
    ]
    eval_res = evaluate_change(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        expected_changes=expected_list,
        actor_role="MAINTENANCE_ENGINEER",
    )
    return {
        "scenario": "Expected Motor Speed Increase",
        "category": ChangeCategory.PARAMETERS.value,
        "parameter_name": "motor_speed_rpm",
        "old_value": 3000,
        "new_value": 3200,
        "is_expected": eval_res.is_expected,
        "is_authorized": eval_res.is_authorized,
        "expected_status": "EXPECTED" if eval_res.is_expected else "UNEXPECTED",
        "authorization_status": "AUTHORIZED" if eval_res.is_authorized else "UNAUTHORIZED",
        "risk_level": eval_res.risk_level.value,
        "risk_score": eval_res.risk_score,
        "requires_supervisor_approval": eval_res.requires_supervisor_approval,
        "notes": eval_res.authorization_notes,
    }


@router.get(
    "/demo/unexpected-ip",
    summary="Demo: Unexpected IP Change (192.168.10.20 -> 192.168.10.50)",
    description=(
        "Demonstrates evaluation of an unexpected network IP change. "
        "Result: UNEXPECTED, UNAUTHORIZED, HIGH RISK."
    ),
)
async def demo_unexpected_ip(
    _: UserProfileResponse = Depends(get_current_user),
):
    # No network change in approved scope
    expected_list = [
        {
            "category": "PARAMETERS",
            "parameter_name": "motor_speed_rpm",
            "from_value": 3000,
            "to_value": 3200,
        }
    ]
    eval_res = evaluate_change(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        expected_changes=expected_list,
        actor_role="MAINTENANCE_ENGINEER",
    )
    return {
        "scenario": "Unexpected Machine IP Address Modification",
        "category": ChangeCategory.NETWORK.value,
        "parameter_name": "ip_address",
        "old_value": "192.168.10.20",
        "new_value": "192.168.10.50",
        "is_expected": eval_res.is_expected,
        "is_authorized": eval_res.is_authorized,
        "expected_status": "UNEXPECTED" if not eval_res.is_expected else "EXPECTED",
        "authorization_status": "UNAUTHORIZED" if not eval_res.is_authorized else "AUTHORIZED",
        "risk_level": eval_res.risk_level.value,
        "risk_score": eval_res.risk_score,
        "requires_supervisor_approval": eval_res.requires_supervisor_approval,
        "notes": eval_res.authorization_notes,
    }


@router.get(
    "/demo/safety-plc",
    summary="Demo: Safety PLC Modification (N7 Interlock)",
    description=(
        "Demonstrates evaluation of a safety PLC interlock modification. "
        "Result: CRITICAL, SUPERVISOR REVIEW REQUIRED."
    ),
)
async def demo_safety_plc(
    _: UserProfileResponse = Depends(get_current_user),
):
    eval_res = evaluate_change(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value={"network_id": "N7", "status": "SAFETY_INTERLOCK_ACTIVE"},
        new_value={"network_id": "N7", "status": "REMOVED"},
        expected_changes=[],
        actor_role="MAINTENANCE_ENGINEER",
    )
    return {
        "scenario": "Safety PLC Interlock N7 Modification",
        "category": ChangeCategory.PLC_LOGIC.value,
        "parameter_name": "plc_network:N7",
        "old_value": "SAFETY_INTERLOCK_ACTIVE",
        "new_value": "REMOVED",
        "is_expected": eval_res.is_expected,
        "is_authorized": eval_res.is_authorized,
        "expected_status": "UNEXPECTED" if not eval_res.is_expected else "EXPECTED",
        "authorization_status": "UNAUTHORIZED" if not eval_res.is_authorized else "AUTHORIZED",
        "risk_level": eval_res.risk_level.value,
        "risk_score": eval_res.risk_score,
        "requires_supervisor_approval": eval_res.requires_supervisor_approval,
        "supervisor_review_requirement": "SUPERVISOR REVIEW REQUIRED",
        "notes": eval_res.authorization_notes,
    }
