"""
Audit Log API Router — Security Event Audit Log with SHA-256 Hash Chaining.

Endpoints
---------
POST /api/logs                      — Record a new security event
GET  /api/logs                      — List audit events (paginated)
GET  /api/logs/{event_id}           — Get single event by ID
POST /api/logs/verify-integrity     — Verify the entire chain integrity
POST /api/logs/demo-tamper          — Safe tamper detection demo (in-memory only)

Hash chaining is enforced exclusively server-side.
The frontend never supplies previous_hash or current_hash.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, require_admin
from app.schemas.audit import (
    AuditEventCreate,
    AuditEventListResponse,
    AuditEventResponse,
    ChainVerifyResponse,
    TamperDemoResponse,
)
from app.schemas.auth import UserProfileResponse, UserRole
from app.services import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["Security Event Audit Log"])


# ---------------------------------------------------------------------------
# POST /api/logs — Record a new security event
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=AuditEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new security event",
    description=(
        "Appends a tamper-evident security event to the audit log. "
        "The backend computes previous_hash and current_hash — never the caller."
    ),
)
async def record_event(
    body: AuditEventCreate,
    current_user: UserProfileResponse = Depends(get_current_user),
) -> AuditEventResponse:
    # Auditors are read-only — they cannot write events
    if current_user.role == UserRole.AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditors have read-only access to the audit log.",
        )
    return await audit_service.record_event(event=body, actor_id=current_user.id)


# ---------------------------------------------------------------------------
# GET /api/logs — List events
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=AuditEventListResponse,
    summary="List audit events",
    description="Returns a paginated list of audit events in descending order (newest first).",
)
async def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: Optional[str] = Query(default=None),
    machine_id: Optional[UUID] = Query(default=None),
    _: UserProfileResponse = Depends(get_current_user),
) -> AuditEventListResponse:
    result = await audit_service.list_events(
        limit=limit,
        offset=offset,
        event_type=event_type,
        machine_id=machine_id,
    )
    return AuditEventListResponse(**result)


# ---------------------------------------------------------------------------
# GET /api/logs/{event_id} — Get single event
# ---------------------------------------------------------------------------

@router.get(
    "/{event_id}",
    response_model=AuditEventResponse,
    summary="Get a single audit event by ID",
)
async def get_event(
    event_id: UUID,
    _: UserProfileResponse = Depends(get_current_user),
) -> AuditEventResponse:
    event = await audit_service.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event {event_id} not found.",
        )
    return event


# ---------------------------------------------------------------------------
# POST /api/logs/verify-integrity — Chain integrity check
# ---------------------------------------------------------------------------

@router.post(
    "/verify-integrity",
    response_model=ChainVerifyResponse,
    summary="Verify SHA-256 hash chain integrity",
    description=(
        "Walks the entire audit log in chronological order and recomputes "
        "every SHA-256 hash. Returns valid=True if the chain is intact, "
        "or identifies the first broken event if tampering is detected."
    ),
)
async def verify_integrity(
    _: UserProfileResponse = Depends(get_current_user),
) -> ChainVerifyResponse:
    return await audit_service.verify_chain_integrity()


# ---------------------------------------------------------------------------
# POST /api/logs/demo-tamper — Safe tamper demonstration
# ---------------------------------------------------------------------------

@router.post(
    "/demo-tamper",
    response_model=TamperDemoResponse,
    summary="Demo: Simulated tamper detection (safe, in-memory only)",
    description=(
        "Builds an ephemeral simulated audit chain, corrupts one event "
        "in memory, then verifies the chain to demonstrate tamper detection. "
        "NO real database records are modified or corrupted. "
        "This endpoint exists solely for demonstration purposes."
    ),
)
async def demo_tamper(
    _: UserProfileResponse = Depends(get_current_user),
) -> TamperDemoResponse:
    return await audit_service.run_tamper_demo()
