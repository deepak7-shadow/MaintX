"""
Verification API Router — Final Maintenance Verification Endpoints.

Endpoints
---------
POST /api/verification/session/{session_id}  — Execute and persist final verification
GET  /api/verification/session/{session_id}  — Fetch latest verification record
GET  /api/verification/demo/{scenario_id}    — Run pre-built demo verification scenario
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_current_user, require_engineer
from app.schemas.auth import UserProfileResponse
from app.schemas.verification import (
    VerificationResultResponse,
    VerifySessionRequest,
)
from app.services import verification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/verification", tags=["Final Maintenance Verification"])


@router.post(
    "/session/{session_id}",
    response_model=VerificationResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute final maintenance verification",
    description=(
        "Compares trusted baseline machine state + approved changes against actual "
        "final machine state + actual PLC logic. Persists to verification_results "
        "and updates the maintenance session verification status."
    ),
)
async def verify_session(
    session_id: UUID,
    body: VerifySessionRequest = VerifySessionRequest(),
    current_user: UserProfileResponse = Depends(require_engineer),
) -> VerificationResultResponse:
    return await verification_service.run_session_verification(
        session_id=session_id,
        actor_id=current_user.id,
        request_body=body,
    )


@router.get(
    "/session/{session_id}",
    response_model=VerificationResultResponse,
    summary="Get latest verification result for a session",
)
async def get_session_verification(
    session_id: UUID,
    _: UserProfileResponse = Depends(get_current_user),
) -> VerificationResultResponse:
    result = await verification_service.get_latest_session_verification(session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No verification result found for session {session_id}.",
        )
    return result


@router.get(
    "/demo/{scenario_id}",
    response_model=VerificationResultResponse,
    summary="Get pre-built verification demo scenario",
    description="Returns pre-computed verification for 'verified', 'review-required', or 'failed-safety'.",
)
async def get_demo_scenario(
    scenario_id: str = Path(..., description="Demo scenario identifier"),
    _: UserProfileResponse = Depends(get_current_user),
) -> VerificationResultResponse:
    return verification_service.get_demo_verification(scenario_id)
