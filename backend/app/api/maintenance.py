"""
Maintenance API router — full maintenance workflow.

Endpoints
---------
GET  /api/maintenance                              — List requests
POST /api/maintenance                              — Create request
GET  /api/maintenance/{request_id}                 — Get request detail
POST /api/maintenance/{request_id}/assign          — Assign engineer (SUPERVISOR/ADMIN)
POST /api/maintenance/{request_id}/approve         — Approve/Reject (SUPERVISOR/ADMIN)
POST /api/maintenance/{request_id}/start           — Start session (assigned engineer)
GET  /api/maintenance/{request_id}/sessions        — List sessions for request
POST /api/maintenance/sessions/{session_id}/complete — Complete session
GET  /api/maintenance/sessions                     — List all sessions
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, require_engineer, require_supervisor
from app.schemas.auth import UserProfileResponse
from app.schemas.maintenance import (
    ApproveMaintenanceRequest,
    AssignEngineerRequest,
    CompleteSessionRequest,
    CreateMaintenanceRequest,
    MaintenanceModeStatus,
    MaintenanceRequestResponse,
    MaintenanceSessionResponse,
    StartSessionRequest,
)
from app.services import maintenance_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["Maintenance"])


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=List[MaintenanceRequestResponse],
    summary="List maintenance requests",
)
async def list_requests(
    status: Optional[str] = Query(None, description="Filter by request status"),
    machine_id: Optional[UUID] = Query(None, description="Filter by machine UUID"),
    _: UserProfileResponse = Depends(get_current_user),
) -> List[MaintenanceRequestResponse]:
    return await maintenance_service.list_requests(status_filter=status, machine_id=machine_id)


@router.post(
    "",
    response_model=MaintenanceRequestResponse,
    status_code=201,
    summary="Create maintenance request",
    description="Create a new maintenance request. The requesting user becomes the engineer unless overridden.",
)
async def create_request(
    body: CreateMaintenanceRequest,
    current_user: UserProfileResponse = Depends(require_engineer),
) -> MaintenanceRequestResponse:
    return await maintenance_service.create_request(
        machine_id=body.machine_id,
        engineer_id=current_user.id,
        reason=body.reason,
        maintenance_type=body.maintenance_type.value,
        priority=body.priority.value,
        expected_changes=[c.model_dump() for c in body.expected_changes],
        scheduled_start=body.scheduled_start,
        scheduled_end=body.scheduled_end,
        actor=current_user,
    )


@router.get(
    "/{request_id}",
    response_model=MaintenanceRequestResponse,
    summary="Get maintenance request detail",
)
async def get_request(
    request_id: UUID,
    _: UserProfileResponse = Depends(get_current_user),
) -> MaintenanceRequestResponse:
    return await maintenance_service.get_request(request_id)


@router.post(
    "/{request_id}/assign",
    response_model=MaintenanceRequestResponse,
    summary="Assign engineer to request",
    description="Supervisor/Admin can assign or reassign an engineer to a maintenance request.",
)
async def assign_engineer(
    request_id: UUID,
    body: AssignEngineerRequest,
    current_user: UserProfileResponse = Depends(require_supervisor),
) -> MaintenanceRequestResponse:
    return await maintenance_service.assign_engineer(
        request_id=request_id,
        new_engineer_id=body.engineer_id,
        actor=current_user,
    )


@router.post(
    "/{request_id}/approve",
    response_model=MaintenanceRequestResponse,
    summary="Approve or reject a maintenance request",
    description="Supervisor/Admin formally approves or rejects a submitted maintenance request.",
)
async def approve_request(
    request_id: UUID,
    body: ApproveMaintenanceRequest,
    current_user: UserProfileResponse = Depends(require_supervisor),
) -> MaintenanceRequestResponse:
    return await maintenance_service.approve_request(
        request_id=request_id,
        decision=body.decision,
        comments=body.comments,
        actor=current_user,
    )


@router.post(
    "/{request_id}/start",
    response_model=MaintenanceSessionResponse,
    status_code=201,
    summary="Start maintenance session",
    description=(
        "Starts a maintenance session for an approved request. "
        "This immediately places the machine in MAINTENANCE_MODE and captures a pre-session baseline."
    ),
)
async def start_session(
    request_id: UUID,
    body: StartSessionRequest = StartSessionRequest(),
    current_user: UserProfileResponse = Depends(require_engineer),
) -> MaintenanceSessionResponse:
    return await maintenance_service.start_session(
        request_id=request_id,
        actor=current_user,
        notes=body.notes,
    )


@router.get(
    "/{request_id}/sessions",
    response_model=List[MaintenanceSessionResponse],
    summary="List sessions for a request",
)
async def list_request_sessions(
    request_id: UUID,
    _: UserProfileResponse = Depends(get_current_user),
) -> List[MaintenanceSessionResponse]:
    return await maintenance_service.list_sessions(request_id=request_id)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/all",
    response_model=List[MaintenanceSessionResponse],
    summary="List all maintenance sessions",
)
async def list_all_sessions(
    _: UserProfileResponse = Depends(get_current_user),
) -> List[MaintenanceSessionResponse]:
    return await maintenance_service.list_sessions()


@router.post(
    "/sessions/{session_id}/complete",
    response_model=MaintenanceSessionResponse,
    summary="Complete a maintenance session",
    description=(
        "Closes the active maintenance session. "
        "The machine is restored to OPERATIONAL status. "
        "The request is marked COMPLETED (or VERIFYING if review is needed)."
    ),
)
async def complete_session(
    session_id: UUID,
    body: CompleteSessionRequest = CompleteSessionRequest(),
    current_user: UserProfileResponse = Depends(require_engineer),
) -> MaintenanceSessionResponse:
    return await maintenance_service.complete_session(
        session_id=session_id,
        actor=current_user,
        notes=body.notes,
        verification_status=body.verification_status,
    )
