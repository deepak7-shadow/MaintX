"""
Maintenance service — full workflow:

  create_request  →  assign_engineer  →  approve  →
  start_session   →  complete_session

All state transitions are validated; security audit events are
appended to the hash-chain log on every significant action.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status as http_status

from app.db.client import get_supabase_client
from app.schemas.auth import UserProfileResponse, UserRole
from app.schemas.maintenance import (
    MaintenanceModeStatus,
    MaintenanceRequestResponse,
    MaintenanceSessionResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(payload: dict) -> str:
    """SHA-256 hash of a JSON-serialised payload (for the audit chain)."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _get_last_event_hash(client) -> str:
    """Fetch the hash of the most recent security_events row for chain linking."""
    try:
        result = (
            client.table("security_events")
            .select("current_hash")
            .order("event_number", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["current_hash"]
    except Exception:
        pass
    return "0" * 64


def _append_audit_event(
    client,
    event_type: str,
    payload: dict,
    severity: str = "INFO",
    machine_id: Optional[str] = None,
    session_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
) -> None:
    """Append a tamper-evident entry to security_events."""
    try:
        previous_hash = _get_last_event_hash(client)
        current_hash = _compute_hash({
            "event_type": event_type,
            "payload": payload,
            "previous_hash": previous_hash,
            "ts": _now(),
        })
        client.table("security_events").insert({
            "event_type": event_type,
            "machine_id": machine_id,
            "session_id": session_id,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "payload": payload,
            "severity": severity,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
        }).execute()
    except Exception as exc:
        logger.error("Audit log append failed: %s", exc)


def _row_to_request(row: dict) -> MaintenanceRequestResponse:
    return MaintenanceRequestResponse(
        id=row["id"],
        request_number=row["request_number"],
        machine_id=row["machine_id"],
        engineer_id=row["engineer_id"],
        supervisor_id=row.get("supervisor_id"),
        reason=row["reason"],
        maintenance_type=row["maintenance_type"],
        expected_changes=row.get("expected_changes") or [],
        priority=row["priority"],
        approval_status=row["approval_status"],
        status=row["status"],
        scheduled_start=row["scheduled_start"],
        scheduled_end=row.get("scheduled_end"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_session(row: dict) -> MaintenanceSessionResponse:
    return MaintenanceSessionResponse(
        id=row["id"],
        request_id=row["request_id"],
        machine_id=row["machine_id"],
        engineer_id=row["engineer_id"],
        started_at=row["started_at"],
        completed_at=row.get("completed_at"),
        session_status=row["session_status"],
        baseline_captured=row.get("baseline_captured", False),
        verification_status=row.get("verification_status", "PENDING"),
        notes=row.get("notes"),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Request listing / fetching
# ---------------------------------------------------------------------------


async def list_requests(
    status_filter: Optional[str] = None,
    machine_id: Optional[UUID] = None,
) -> List[MaintenanceRequestResponse]:
    client = get_supabase_client()
    try:
        q = client.table("maintenance_requests").select("*").order("created_at", desc=True)
        if status_filter:
            q = q.eq("status", status_filter)
        if machine_id:
            q = q.eq("machine_id", str(machine_id))
        result = q.execute()
    except Exception as exc:
        logger.error("Failed to list maintenance requests: %s", exc)
        raise HTTPException(status_code=503, detail="Database error listing requests.")

    return [_row_to_request(r) for r in (result.data or [])]


async def get_request(request_id: UUID) -> MaintenanceRequestResponse:
    client = get_supabase_client()
    try:
        result = (
            client.table("maintenance_requests")
            .select("*")
            .eq("id", str(request_id))
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Maintenance request not found.")
    return _row_to_request(result.data)


# ---------------------------------------------------------------------------
# 1. Create maintenance request
# ---------------------------------------------------------------------------


async def create_request(
    machine_id: UUID,
    engineer_id: UUID,
    reason: str,
    maintenance_type: str,
    priority: str,
    expected_changes: list,
    scheduled_start: Optional[datetime],
    scheduled_end: Optional[datetime],
    actor: UserProfileResponse,
) -> MaintenanceRequestResponse:
    """Create a new maintenance request (DRAFT → SUBMITTED)."""
    client = get_supabase_client()

    # Verify the machine exists
    machine_res = (
        client.table("machines").select("id, machine_code, status").eq("id", str(machine_id)).single().execute()
    )
    if not machine_res.data:
        raise HTTPException(status_code=404, detail="Machine not found.")

    machine = machine_res.data
    if machine["status"] in ("DECOMMISSIONED", "COMPROMISED"):
        raise HTTPException(
            status_code=409,
            detail=f"Machine is in status '{machine['status']}' and cannot accept new maintenance requests.",
        )

    # Generate request number using timestamp + machine code
    ts = datetime.now(timezone.utc)
    req_number = f"MNT-{ts.year}-{int(ts.timestamp()) % 10000}"

    data = {
        "request_number": req_number,
        "machine_id": str(machine_id),
        "engineer_id": str(engineer_id),
        "reason": reason,
        "maintenance_type": maintenance_type,
        "priority": priority,
        "expected_changes": expected_changes,
        "status": "SUBMITTED",
        "approval_status": "PENDING",
        "scheduled_start": scheduled_start.isoformat() if scheduled_start else ts.isoformat(),
        "scheduled_end": scheduled_end.isoformat() if scheduled_end else None,
    }

    try:
        result = client.table("maintenance_requests").insert(data).execute()
    except Exception as exc:
        logger.error("Failed to create maintenance request: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to create maintenance request.")

    row = result.data[0]
    _append_audit_event(
        client,
        event_type="MAINTENANCE_REQUEST_CREATED",
        payload={"request_number": row["request_number"], "machine_code": machine["machine_code"], "reason": reason},
        severity="INFO",
        machine_id=str(machine_id),
        actor_id=str(actor.id),
        actor_role=actor.role.value,
    )
    return _row_to_request(row)


# ---------------------------------------------------------------------------
# 2. Assign engineer
# ---------------------------------------------------------------------------


async def assign_engineer(
    request_id: UUID,
    new_engineer_id: UUID,
    actor: UserProfileResponse,
) -> MaintenanceRequestResponse:
    """Assign (or reassign) an engineer to a maintenance request."""
    _require_roles(actor, [UserRole.ADMIN, UserRole.SUPERVISOR])
    client = get_supabase_client()

    req = await get_request(request_id)
    if req.status not in ("DRAFT", "SUBMITTED", "APPROVED"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reassign engineer for request in status '{req.status}'.",
        )

    # Verify the engineer exists and has the right role
    eng_res = client.table("profiles").select("id, role, engineer_code").eq("id", str(new_engineer_id)).single().execute()
    if not eng_res.data:
        raise HTTPException(status_code=404, detail="Engineer profile not found.")
    if eng_res.data["role"] not in ("MAINTENANCE_ENGINEER", "ADMIN"):
        raise HTTPException(status_code=422, detail="Assigned user must be a MAINTENANCE_ENGINEER.")

    try:
        result = (
            client.table("maintenance_requests")
            .update({"engineer_id": str(new_engineer_id)})
            .eq("id", str(request_id))
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Failed to assign engineer.")

    _append_audit_event(
        client,
        event_type="MAINTENANCE_REQUEST_CREATED",
        payload={"action": "ENGINEER_ASSIGNED", "request_id": str(request_id), "engineer_id": str(new_engineer_id)},
        severity="INFO",
        actor_id=str(actor.id),
        actor_role=actor.role.value,
    )
    return _row_to_request(result.data[0])


# ---------------------------------------------------------------------------
# 3. Approve / Reject
# ---------------------------------------------------------------------------


async def approve_request(
    request_id: UUID,
    decision: str,
    comments: Optional[str],
    actor: UserProfileResponse,
) -> MaintenanceRequestResponse:
    """Supervisor/Admin approves or rejects a maintenance request."""
    _require_roles(actor, [UserRole.ADMIN, UserRole.SUPERVISOR])
    client = get_supabase_client()

    req = await get_request(request_id)
    if req.status not in ("SUBMITTED", "DRAFT"):
        raise HTTPException(
            status_code=409,
            detail=f"Request in status '{req.status}' cannot be approved/rejected.",
        )

    new_status = "APPROVED" if decision == "APPROVED" else "REJECTED"
    new_approval_status = decision  # APPROVED | REJECTED

    try:
        result = (
            client.table("maintenance_requests")
            .update({
                "status": new_status,
                "approval_status": new_approval_status,
                "supervisor_id": str(actor.id),
            })
            .eq("id", str(request_id))
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Failed to record approval decision.")

    # Record formal approval row
    try:
        client.table("approvals").insert({
            "request_id": str(request_id),
            "approver_id": str(actor.id),
            "approver_role": actor.role.value,
            "decision": decision,
            "comments": comments,
        }).execute()
    except Exception as exc:
        logger.warning("Failed to insert approval record: %s", exc)

    event_type = "MAINTENANCE_APPROVED" if decision == "APPROVED" else "SUPERVISOR_REJECTED"
    _append_audit_event(
        client,
        event_type=event_type,
        payload={"request_id": str(request_id), "decision": decision, "comments": comments},
        severity="INFO" if decision == "APPROVED" else "MEDIUM",
        machine_id=str(req.machine_id),
        actor_id=str(actor.id),
        actor_role=actor.role.value,
    )
    return _row_to_request(result.data[0])


# ---------------------------------------------------------------------------
# 4. Start maintenance session
# ---------------------------------------------------------------------------


async def start_session(
    request_id: UUID,
    actor: UserProfileResponse,
    notes: Optional[str] = None,
) -> MaintenanceSessionResponse:
    """
    Start a maintenance session for an approved request.
    Puts the machine into MAINTENANCE_MODE and captures a baseline.
    """
    _require_roles(actor, [UserRole.ADMIN, UserRole.MAINTENANCE_ENGINEER, UserRole.SUPERVISOR])
    client = get_supabase_client()

    req = await get_request(request_id)
    if req.status != "APPROVED":
        raise HTTPException(
            status_code=409,
            detail=f"Request must be APPROVED before a session can be started. Current status: '{req.status}'.",
        )
    if req.engineer_id != actor.id and actor.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
        raise HTTPException(
            status_code=403,
            detail="Only the assigned engineer or a supervisor/admin can start this session.",
        )

    # Check for existing active session
    existing = (
        client.table("maintenance_sessions")
        .select("id")
        .eq("request_id", str(request_id))
        .eq("session_status", "ACTIVE")
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="An active session already exists for this request.")

    # Create session
    try:
        session_result = client.table("maintenance_sessions").insert({
            "request_id": str(request_id),
            "machine_id": str(req.machine_id),
            "engineer_id": str(actor.id),
            "notes": notes,
            "session_status": "ACTIVE",
            "baseline_captured": False,
            "verification_status": "PENDING",
        }).execute()
    except Exception as exc:
        logger.error("Failed to start session: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to create maintenance session.")

    session_row = session_result.data[0]

    # Transition request to IN_PROGRESS
    client.table("maintenance_requests").update({"status": "IN_PROGRESS"}).eq("id", str(request_id)).execute()

    # Put machine into MAINTENANCE_MODE
    client.table("machines").update({"status": "MAINTENANCE_MODE"}).eq("id", str(req.machine_id)).execute()

    # Capture machine baseline snapshot
    machine_res = client.table("machines").select("*").eq("id", str(req.machine_id)).single().execute()
    if machine_res.data:
        m = machine_res.data
        baseline_payload = {
            "parameters": m.get("parameters"),
            "network": {"ip_address": str(m.get("ip_address", "")), "subnet": m.get("subnet"), "gateway": str(m.get("gateway", ""))},
            "firmware": m.get("firmware"),
            "firewall_configuration": m.get("firewall_configuration"),
            "safety_configuration": m.get("safety_configuration"),
        }
        baseline_hash = _compute_hash(baseline_payload)
        try:
            client.table("machine_baselines").insert({
                "session_id": session_row["id"],
                "machine_id": str(req.machine_id),
                "parameters": baseline_payload["parameters"],
                "network_configuration": baseline_payload["network"],
                "firmware": baseline_payload["firmware"],
                "firewall_configuration": baseline_payload["firewall_configuration"],
                "safety_configuration": baseline_payload["safety_configuration"],
                "baseline_hash": baseline_hash,
                "captured_by": str(actor.id),
            }).execute()
            # Mark baseline as captured
            client.table("maintenance_sessions").update({"baseline_captured": True}).eq("id", session_row["id"]).execute()
            session_row["baseline_captured"] = True
        except Exception as exc:
            logger.warning("Failed to capture baseline: %s", exc)

    _append_audit_event(
        client,
        event_type="MAINTENANCE_STARTED",
        payload={"session_id": session_row["id"], "request_id": str(request_id), "notes": notes},
        severity="INFO",
        machine_id=str(req.machine_id),
        session_id=session_row["id"],
        actor_id=str(actor.id),
        actor_role=actor.role.value,
    )
    return _row_to_session(session_row)


# ---------------------------------------------------------------------------
# 5. Complete maintenance session
# ---------------------------------------------------------------------------


async def complete_session(
    session_id: UUID,
    actor: UserProfileResponse,
    notes: Optional[str] = None,
    verification_status: str = "VERIFIED",
) -> MaintenanceSessionResponse:
    """Close the maintenance session and restore the machine to OPERATIONAL."""
    _require_roles(actor, [UserRole.ADMIN, UserRole.MAINTENANCE_ENGINEER, UserRole.SUPERVISOR])
    client = get_supabase_client()

    # Fetch session
    try:
        ses_res = (
            client.table("maintenance_sessions")
            .select("*")
            .eq("id", str(session_id))
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found.")

    ses = ses_res.data
    if ses["session_status"] != "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail=f"Session is not ACTIVE (status: '{ses['session_status']}').",
        )
    if ses["engineer_id"] != str(actor.id) and actor.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
        raise HTTPException(status_code=403, detail="Only the assigned engineer or a supervisor/admin can complete this session.")

    # ── Stage 9 Enforcement: Prevent maintenance closure when unresolved critical changes exist ──
    if verification_status == "FAILED" or ses.get("verification_status") == "FAILED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Maintenance closure blocked: Verification status is FAILED. "
                "Unresolved critical changes or safety interlock violations must be resolved "
                "before the machine can be restored to operational mode."
            ),
        )

    # Check database verification_results for this session
    try:
        verif_res = (
            client.table("verification_results")
            .select("final_status, unresolved_critical_changes")
            .eq("session_id", str(session_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if verif_res.data:
            latest_v = verif_res.data[0]
            if latest_v.get("final_status") == "FAILED" or latest_v.get("unresolved_critical_changes", 0) > 0:
                unres_count = latest_v.get("unresolved_critical_changes", 1)
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Maintenance closure blocked: {unres_count} unresolved critical change(s) exist. "
                        f"Verification status: FAILED. Safety interlock or unauthorized critical changes "
                        f"must be resolved before session closure."
                    ),
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Could not query verification_results during complete_session: %s", exc)

    now_ts = _now()
    try:
        result = (
            client.table("maintenance_sessions")
            .update({
                "session_status": "COMPLETED",
                "completed_at": now_ts,
                "verification_status": verification_status,
                "notes": notes or ses.get("notes"),
            })
            .eq("id", str(session_id))
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Failed to complete session.")

    # Restore machine to OPERATIONAL
    client.table("machines").update({"status": "OPERATIONAL"}).eq("id", ses["machine_id"]).execute()

    # Close the parent request
    new_req_status = "COMPLETED" if verification_status == "VERIFIED" else "VERIFYING"
    client.table("maintenance_requests").update({"status": new_req_status}).eq("id", ses["request_id"]).execute()

    _append_audit_event(
        client,
        event_type="MAINTENANCE_CLOSED",
        payload={"session_id": str(session_id), "verification_status": verification_status, "notes": notes},
        severity="INFO",
        machine_id=ses["machine_id"],
        session_id=str(session_id),
        actor_id=str(actor.id),
        actor_role=actor.role.value,
    )
    return _row_to_session(result.data[0])


# ---------------------------------------------------------------------------
# 6. Maintenance mode status
# ---------------------------------------------------------------------------


async def get_maintenance_mode_status(machine_id: UUID) -> MaintenanceModeStatus:
    """Return current maintenance mode status for a machine."""
    client = get_supabase_client()

    machine_res = client.table("machines").select("id, machine_code, status").eq("id", str(machine_id)).single().execute()
    if not machine_res.data:
        raise HTTPException(status_code=404, detail="Machine not found.")

    m = machine_res.data
    in_maintenance = m["status"] == "MAINTENANCE_MODE"

    active_session = None
    active_request = None
    if in_maintenance:
        ses_res = (
            client.table("maintenance_sessions")
            .select("id, request_id, engineer_id, started_at")
            .eq("machine_id", str(machine_id))
            .eq("session_status", "ACTIVE")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        if ses_res.data:
            active_session = ses_res.data[0]
            req_res = (
                client.table("maintenance_requests")
                .select("request_number")
                .eq("id", active_session["request_id"])
                .single()
                .execute()
            )
            if req_res.data:
                active_request = req_res.data

    return MaintenanceModeStatus(
        machine_code=m["machine_code"],
        machine_id=m["id"],
        in_maintenance=in_maintenance,
        active_session_id=active_session["id"] if active_session else None,
        active_request_number=active_request["request_number"] if active_request else None,
        engineer_id=active_session["engineer_id"] if active_session else None,
        started_at=active_session["started_at"] if active_session else None,
        machine_locked=in_maintenance,
        message=(
            f"Machine is in MAINTENANCE_MODE — session {active_session['id']} active."
            if in_maintenance
            else "Machine is OPERATIONAL."
        ),
    )


async def list_sessions(request_id: Optional[UUID] = None) -> List[MaintenanceSessionResponse]:
    client = get_supabase_client()
    q = client.table("maintenance_sessions").select("*").order("created_at", desc=True)
    if request_id:
        q = q.eq("request_id", str(request_id))
    result = q.execute()
    return [_row_to_session(r) for r in (result.data or [])]


# ---------------------------------------------------------------------------
# Guard helper
# ---------------------------------------------------------------------------


def _require_roles(actor: UserProfileResponse, roles: list) -> None:
    if actor.role not in roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"Action requires one of: {[r.value for r in roles]}.",
        )
