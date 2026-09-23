"""
Change service — database persistence, policy execution, and review workflows
for the Change Detection Engine.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status as http_status

from app.db.client import get_supabase_client
from app.schemas.auth import UserProfileResponse, UserRole
from app.schemas.changes import (
    ChangeApprovalStatus,
    ChangeCategory,
    ChangeDetectionRunResponse,
    ChangeRecordCreate,
    ChangeRecordResponse,
    ChangeRiskLevel,
)
from app.services.change_engine import detect_differences, evaluate_change
from app.services.maintenance_service import _append_audit_event

logger = logging.getLogger(__name__)


def _to_jsonb_safe(val: Any) -> Any:
    """Ensure value is JSON-serializable for PostgreSQL jsonb."""
    if isinstance(val, (dict, list, int, float, bool)) or val is None:
        return val
    return str(val)


def _row_to_change_response(r: dict) -> ChangeRecordResponse:
    return ChangeRecordResponse(
        id=UUID(r["id"]) if isinstance(r["id"], str) else r["id"],
        session_id=UUID(r["session_id"]) if isinstance(r["session_id"], str) else r["session_id"],
        machine_id=UUID(r["machine_id"]) if isinstance(r["machine_id"], str) else r["machine_id"],
        user_id=UUID(r["user_id"]) if isinstance(r["user_id"], str) else r["user_id"],
        user_role=r["user_role"],
        category=ChangeCategory(r["category"]),
        parameter_name=r["parameter_name"],
        old_value=r.get("old_value"),
        new_value=r.get("new_value"),
        reason=r["reason"],
        is_expected=r["is_expected"],
        is_authorized=r["is_authorized"],
        risk_score=r["risk_score"],
        risk_level=ChangeRiskLevel(r["risk_level"]),
        ai_anomaly_score=r.get("ai_anomaly_score"),
        requires_supervisor_approval=r.get("requires_supervisor_approval", False),
        approval_status=ChangeApprovalStatus(r.get("approval_status", "PENDING")),
        timestamp=r.get("timestamp") or datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. Record an individual configuration change
# ---------------------------------------------------------------------------


async def record_change(
    payload: ChangeRecordCreate,
    actor: UserProfileResponse,
) -> ChangeRecordResponse:
    """
    Record an explicit configuration change with automated policy evaluation.
    Stores the change in configuration_changes and appends to the audit log.
    """
    if actor.role == UserRole.AUDITOR:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Auditor role is strictly read-only and cannot record configuration changes.",
        )

    client = get_supabase_client()

    # Look up session and its maintenance request for expected changes
    session_res = (
        client.table("maintenance_sessions")
        .select("id, machine_id, request_id")
        .eq("id", str(payload.session_id))
        .single()
        .execute()
    )
    if not session_res.data:
        raise HTTPException(status_code=404, detail="Maintenance session not found.")

    req_id = session_res.data["request_id"]
    req_res = (
        client.table("maintenance_requests")
        .select("expected_changes")
        .eq("id", str(req_id))
        .single()
        .execute()
    )
    expected_changes = (req_res.data or {}).get("expected_changes") or []

    # Run policy evaluation
    eval_res = evaluate_change(
        category=payload.category,
        parameter_name=payload.parameter_name,
        old_value=payload.old_value,
        new_value=payload.new_value,
        expected_changes=expected_changes,
        actor_role=actor.role.value,
    )

    db_record = {
        "session_id": str(payload.session_id),
        "machine_id": str(payload.machine_id),
        "user_id": str(actor.id),
        "user_role": actor.role.value,
        "category": payload.category.value,
        "parameter_name": payload.parameter_name,
        "old_value": _to_jsonb_safe(payload.old_value),
        "new_value": _to_jsonb_safe(payload.new_value),
        "reason": payload.reason,
        "is_expected": eval_res.is_expected,
        "is_authorized": eval_res.is_authorized,
        "risk_score": eval_res.risk_score,
        "risk_level": eval_res.risk_level.value,
        "requires_supervisor_approval": eval_res.requires_supervisor_approval,
        "approval_status": eval_res.approval_status.value,
    }

    try:
        insert_res = client.table("configuration_changes").insert(db_record).execute()
        row = insert_res.data[0]
    except Exception as exc:
        logger.error("Failed to insert configuration change: %s", exc)
        raise HTTPException(status_code=503, detail="Database error recording configuration change.")

    # Audit event
    _append_audit_event(
        client=client,
        event_type="CONFIGURATION_CHANGE_RECORDED",
        payload={
            "change_id": row["id"],
            "category": payload.category.value,
            "parameter": payload.parameter_name,
            "is_expected": eval_res.is_expected,
            "is_authorized": eval_res.is_authorized,
            "risk_level": eval_res.risk_level.value,
            "requires_supervisor": eval_res.requires_supervisor_approval,
        },
        severity="CRITICAL" if eval_res.risk_level == ChangeRiskLevel.CRITICAL else (
            "WARNING" if eval_res.risk_level == ChangeRiskLevel.HIGH else "INFO"
        ),
        machine_id=str(payload.machine_id),
        session_id=str(payload.session_id),
        actor_id=str(actor.id),
        actor_role=actor.role.value,
    )

    return _row_to_change_response(row)


# ---------------------------------------------------------------------------
# 2. Run automated change detection between baseline & current state
# ---------------------------------------------------------------------------


async def run_change_detection(
    session_id: UUID,
    current_state: Dict[str, Any],
    actor: UserProfileResponse,
) -> ChangeDetectionRunResponse:
    """
    Run automated change detection comparing the session's captured baseline
    against the provided current state.
    Evaluates every difference, stores in configuration_changes, and returns summary.
    """
    if actor.role == UserRole.AUDITOR:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Auditor role is strictly read-only and cannot trigger change detection execution.",
        )

    client = get_supabase_client()

    # Fetch session & baseline
    session_res = (
        client.table("maintenance_sessions")
        .select("id, machine_id, request_id, baseline_captured")
        .eq("id", str(session_id))
        .single()
        .execute()
    )
    if not session_res.data:
        raise HTTPException(status_code=404, detail="Maintenance session not found.")

    s_data = session_res.data
    machine_id = s_data["machine_id"]
    req_id = s_data["request_id"]

    # Fetch baseline snapshot from machine_baselines
    base_res = (
        client.table("machine_baselines")
        .select("*")
        .eq("session_id", str(session_id))
        .order("captured_at", desc=True)
        .limit(1)
        .execute()
    )
    baseline_state = base_res.data[0] if base_res.data else {}

    # If machine_baselines was empty, fall back to machine table state
    if not baseline_state:
        m_res = client.table("machines").select("*").eq("id", str(machine_id)).single().execute()
        baseline_state = m_res.data or {}

    # Fetch expected changes
    req_res = (
        client.table("maintenance_requests")
        .select("expected_changes")
        .eq("id", str(req_id))
        .single()
        .execute()
    )
    expected_changes = (req_res.data or {}).get("expected_changes") or []

    # Detect all differences across 6 categories
    raw_diffs = detect_differences(
        baseline_state=baseline_state,
        current_state=current_state,
        expected_changes=expected_changes,
        actor_role=actor.role.value,
    )

    detected_responses: List[ChangeRecordResponse] = []
    expected_count = 0
    unexpected_count = 0
    unauthorized_count = 0
    critical_count = 0
    high_risk_count = 0

    for d in raw_diffs:
        cat: ChangeCategory = d["category"]
        p_name: str = d["parameter_name"]
        eval_res = d["eval"]

        db_record = {
            "session_id": str(session_id),
            "machine_id": str(machine_id),
            "user_id": str(actor.id),
            "user_role": actor.role.value,
            "category": cat.value,
            "parameter_name": p_name,
            "old_value": _to_jsonb_safe(d.get("old_value")),
            "new_value": _to_jsonb_safe(d.get("new_value")),
            "reason": d.get("reason", "Change detected during verification"),
            "is_expected": eval_res.is_expected,
            "is_authorized": eval_res.is_authorized,
            "risk_score": eval_res.risk_score,
            "risk_level": eval_res.risk_level.value,
            "requires_supervisor_approval": eval_res.requires_supervisor_approval,
            "approval_status": eval_res.approval_status.value,
        }

        try:
            insert_res = client.table("configuration_changes").insert(db_record).execute()
            inserted_row = insert_res.data[0]
            resp_item = _row_to_change_response(inserted_row)
            detected_responses.append(resp_item)
        except Exception as exc:
            logger.warning("Failed to store detected change for %s: %s", p_name, exc)
            continue

        if eval_res.is_expected:
            expected_count += 1
        else:
            unexpected_count += 1

        if not eval_res.is_authorized:
            unauthorized_count += 1

        if eval_res.risk_level == ChangeRiskLevel.CRITICAL:
            critical_count += 1
        elif eval_res.risk_level == ChangeRiskLevel.HIGH:
            high_risk_count += 1

    overall_risk = ChangeRiskLevel.LOW
    if critical_count > 0:
        overall_risk = ChangeRiskLevel.CRITICAL
    elif high_risk_count > 0:
        overall_risk = ChangeRiskLevel.HIGH
    elif unexpected_count > 0:
        overall_risk = ChangeRiskLevel.MEDIUM

    requires_supervisor_review = critical_count > 0 or unauthorized_count > 0

    return ChangeDetectionRunResponse(
        session_id=session_id,
        machine_id=UUID(machine_id) if isinstance(machine_id, str) else machine_id,
        total_changes=len(detected_responses),
        expected_count=expected_count,
        unexpected_count=unexpected_count,
        unauthorized_count=unauthorized_count,
        critical_count=critical_count,
        high_risk_count=high_risk_count,
        overall_risk=overall_risk,
        requires_supervisor_review=requires_supervisor_review,
        changes=detected_responses,
        detection_timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 3. Query configuration changes
# ---------------------------------------------------------------------------


async def list_changes(
    session_id: Optional[UUID] = None,
    machine_id: Optional[UUID] = None,
    category: Optional[ChangeCategory] = None,
    risk_level: Optional[ChangeRiskLevel] = None,
    approval_status: Optional[ChangeApprovalStatus] = None,
) -> List[ChangeRecordResponse]:
    client = get_supabase_client()
    query = client.table("configuration_changes").select("*")

    if session_id:
        query = query.eq("session_id", str(session_id))
    if machine_id:
        query = query.eq("machine_id", str(machine_id))
    if category:
        query = query.eq("category", category.value)
    if risk_level:
        query = query.eq("risk_level", risk_level.value)
    if approval_status:
        query = query.eq("approval_status", approval_status.value)

    query = query.order("timestamp", desc=True)

    try:
        res = query.execute()
        return [_row_to_change_response(r) for r in (res.data or [])]
    except Exception as exc:
        logger.error("Failed to list configuration changes: %s", exc)
        raise HTTPException(status_code=503, detail="Database error retrieving changes.")


async def get_change(change_id: UUID) -> ChangeRecordResponse:
    client = get_supabase_client()
    try:
        res = client.table("configuration_changes").select("*").eq("id", str(change_id)).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Configuration change not found.")
        return _row_to_change_response(res.data)
    except Exception:
        raise HTTPException(status_code=404, detail="Configuration change not found.")


# ---------------------------------------------------------------------------
# 4. Supervisor Review & Authorization decision
# ---------------------------------------------------------------------------


async def review_change(
    change_id: UUID,
    approved: bool,
    notes: Optional[str],
    actor: UserProfileResponse,
) -> ChangeRecordResponse:
    """
    Supervisor or Admin review of a pending/unauthorized change.
    MAINTENANCE_ENGINEER and AUDITOR are strictly prohibited from reviewing changes.
    """
    if actor.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Only a SUPERVISOR or ADMIN can review and authorize configuration changes.",
        )

    client = get_supabase_client()
    existing = await get_change(change_id)

    new_status = ChangeApprovalStatus.APPROVED if approved else ChangeApprovalStatus.REJECTED
    is_authorized = approved

    update_payload = {
        "approval_status": new_status.value,
        "is_authorized": is_authorized,
    }

    try:
        res = (
            client.table("configuration_changes")
            .update(update_payload)
            .eq("id", str(change_id))
            .execute()
        )
        row = res.data[0]
    except Exception as exc:
        logger.error("Failed to update change review status: %s", exc)
        raise HTTPException(status_code=503, detail="Database error updating change review.")

    # Audit event
    _append_audit_event(
        client=client,
        event_type="CONFIGURATION_CHANGE_REVIEWED",
        payload={
            "change_id": str(change_id),
            "approved": approved,
            "decision": new_status.value,
            "notes": notes,
            "reviewer_role": actor.role.value,
        },
        severity="WARNING" if not approved else "INFO",
        machine_id=str(existing.machine_id),
        session_id=str(existing.session_id),
        actor_id=str(actor.id),
        actor_role=actor.role.value,
    )

    return _row_to_change_response(row)
