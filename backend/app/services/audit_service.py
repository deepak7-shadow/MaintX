"""
Audit Service — database-backed security event log with hash chaining.

Manages the `audit_log_entries` table:
  - Writing new events (always appended, never updated/deleted)
  - Reading events in chain order
  - Verifying chain integrity
  - Safe tamper demo (ephemeral in-memory only — NO real data corrupted)
"""
from __future__ import annotations

import copy
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.db.client import get_supabase_client
from app.schemas.audit import (
    AuditEventCreate,
    AuditEventResponse,
    AuditEventType,
    ChainVerifyResponse,
    TamperDemoResponse,
)
from app.services.audit_chain import (
    GENESIS_HASH,
    InMemoryChainEvent,
    build_in_memory_chain,
    compute_event_hash,
    verify_chain,
)

logger = logging.getLogger(__name__)

def get_supabase():
    return get_supabase_client()


TABLE = "audit_log_entries"
# ---------------------------------------------------------------------------
# Internal: fetch latest hash from DB
# ---------------------------------------------------------------------------

async def _get_tail_hash() -> str:
    """Return the current_hash of the most recent event, or GENESIS_HASH."""
    try:
        sb = get_supabase()
        resp = (
            sb.table(TABLE)
            .select("current_hash")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]["current_hash"]
    except Exception as exc:
        logger.warning("Could not fetch tail hash: %s — using genesis hash", exc)
    return GENESIS_HASH


# ---------------------------------------------------------------------------
# Write a new audit event
# ---------------------------------------------------------------------------

async def record_event(
    event: AuditEventCreate,
    actor_id: Optional[UUID] = None,
) -> AuditEventResponse:
    """
    Append a new tamper-evident event to the audit log.

    The previous_hash and current_hash are calculated entirely server-side.
    The caller only supplies event_type, optional foreign keys, and event_data.
    """
    sb = get_supabase()

    # 1. Resolve actor
    user_id = event.user_id or actor_id

    # 2. Get chain tail
    previous_hash = await _get_tail_hash()

    # 3. Assign identity & timestamp
    event_id  = uuid.uuid4()
    created_at = datetime.now(timezone.utc)

    # 4. Compute hash
    current_hash = compute_event_hash(
        event_id=event_id,
        event_type=event.event_type.value,
        user_id=user_id,
        machine_id=event.machine_id,
        session_id=event.session_id,
        event_data=event.event_data,
        created_at=created_at,
        previous_hash=previous_hash,
    )

    # 5. Persist
    row: Dict[str, Any] = {
        "event_id":    str(event_id),
        "event_type":  event.event_type.value,
        "user_id":     str(user_id) if user_id else None,
        "machine_id":  str(event.machine_id) if event.machine_id else None,
        "session_id":  str(event.session_id) if event.session_id else None,
        "event_data":  event.event_data,
        "previous_hash": previous_hash,
        "current_hash":  current_hash,
        "created_at":  created_at.isoformat(),
    }

    resp = sb.table(TABLE).insert(row).execute()
    stored = resp.data[0] if resp.data else row

    return _row_to_response(stored)


# ---------------------------------------------------------------------------
# Read events
# ---------------------------------------------------------------------------

async def list_events(
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    machine_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """List audit events in descending order (newest first)."""
    sb = get_supabase()
    query = sb.table(TABLE).select("*", count="exact")

    if event_type:
        query = query.eq("event_type", event_type)
    if machine_id:
        query = query.eq("machine_id", str(machine_id))

    resp = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    events = [_row_to_response(r) for r in (resp.data or [])]
    total  = resp.count or len(events)

    return {
        "events":       events,
        "total":        total,
        "chain_length": total,
    }


async def get_event(event_id: UUID) -> Optional[AuditEventResponse]:
    """Fetch a single audit event by ID."""
    sb = get_supabase()
    resp = (
        sb.table(TABLE)
        .select("*")
        .eq("event_id", str(event_id))
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return _row_to_response(resp.data[0])


# ---------------------------------------------------------------------------
# Chain Integrity Verification
# ---------------------------------------------------------------------------

async def verify_chain_integrity() -> ChainVerifyResponse:
    """
    Walk the entire audit log chain in ascending order and verify every hash.

    Returns the first broken link (if any) with the stored vs recomputed hash.
    """
    sb = get_supabase()
    resp = (
        sb.table(TABLE)
        .select("*")
        .order("created_at", desc=False)
        .execute()
    )
    rows = resp.data or []

    if not rows:
        return ChainVerifyResponse(
            valid=True,
            chain_length=0,
            verified_count=0,
            message="Audit log is empty — chain is trivially valid.",
        )

    # Convert DB rows to InMemoryChainEvent for verification
    mem_events = [_row_to_mem(r) for r in rows]
    valid, broken_idx, stored_hash, computed_hash = verify_chain(mem_events)

    if valid:
        return ChainVerifyResponse(
            valid=True,
            chain_length=len(mem_events),
            verified_count=len(mem_events),
            message=(
                f"Chain integrity VERIFIED. "
                f"All {len(mem_events)} events are tamper-evident and intact."
            ),
        )
    else:
        broken_event = mem_events[broken_idx]  # type: ignore[index]
        return ChainVerifyResponse(
            valid=False,
            chain_length=len(mem_events),
            verified_count=broken_idx,
            first_broken_event=broken_event.event_id,
            expected_hash=stored_hash,
            calculated_hash=computed_hash,
            message=(
                f"CHAIN INTEGRITY FAILED at event index {broken_idx}. "
                f"Hash mismatch detected — possible tampering."
            ),
        )


# ---------------------------------------------------------------------------
# Safe Tamper Demo (ephemeral in-memory only)
# ---------------------------------------------------------------------------

_DEMO_EVENTS: List[Dict[str, Any]] = [
    {
        "event_type": AuditEventType.MAINTENANCE_CREATED.value,
        "event_data": {
            "request_number": "MNT-DEMO-001",
            "machine":        "CNC-01",
            "reason":         "Demo: routine PLC version upgrade",
        },
    },
    {
        "event_type": AuditEventType.MAINTENANCE_APPROVED.value,
        "event_data": {
            "approved_by": "supervisor@maintx.internal",
            "scope":       "Motor speed 3000→3200 RPM, PLC v17→v18",
        },
    },
    {
        "event_type": AuditEventType.PLC_BASELINE_SET.value,
        "event_data": {
            "baseline_hash": "a3f9d2c1" * 8,
            "version":       "v17",
            "machine":       "CNC-01",
        },
    },
    {
        "event_type": AuditEventType.CONFIG_CHANGE_DETECTED.value,
        "event_data": {
            "parameter": "motor_speed_rpm",
            "old_value": 3000,
            "new_value": 3200,
            "authorized": True,
        },
    },
    {
        "event_type": AuditEventType.PLC_HASH_MISMATCH.value,
        "event_data": {
            "expected_hash":   "a3f9d2c1" * 8,
            "calculated_hash": "00000000" * 8,
            "alert":           "PLC LOGIC INTEGRITY FAILED — SAFETY INTERLOCK REMOVED",
        },
    },
    {
        "event_type": AuditEventType.SAFETY_INTERLOCK_ALERT.value,
        "event_data": {
            "network":  "N7",
            "removed":  True,
            "severity": "CRITICAL",
        },
    },
]


async def run_tamper_demo() -> TamperDemoResponse:
    """
    Build a simulated hash chain from demo events, then corrupt one event
    IN MEMORY to demonstrate what a tampered chain looks like.

    IMPORTANT: This function NEVER modifies the real database.
               It operates purely on ephemeral Python objects.
    """
    # 1. Build a valid in-memory chain with timestamps
    now = datetime.now(timezone.utc)
    raw = []
    for i, template in enumerate(_DEMO_EVENTS):
        raw.append({
            **template,
            "created_at": now.replace(second=i),
        })

    chain = build_in_memory_chain(raw)

    # Convert to response objects for the "before" snapshot
    before_responses = [_mem_to_response(e) for e in chain]

    # 2. Tamper with event index 2 (PLC_BASELINE_SET) — change event_data in-place
    tamper_idx = 2
    tampered_chain = copy.deepcopy(chain)
    tampered_chain[tamper_idx].event_data = {
        "baseline_hash": "FORGED_HASH_INJECTED_BY_ATTACKER",
        "version":       "v17",
        "machine":       "CNC-01",
    }
    # NOTE: current_hash is NOT recomputed — simulating attacker forging data
    # but not updating the hash (most realistic attack scenario)

    # 3. Verify the tampered chain
    valid, broken_idx, stored_hash, computed_hash = verify_chain(tampered_chain)

    verify_result = ChainVerifyResponse(
        valid=valid,
        chain_length=len(tampered_chain),
        verified_count=broken_idx if broken_idx is not None else len(tampered_chain),
        first_broken_event=tampered_chain[broken_idx].event_id if broken_idx is not None else None,
        expected_hash=stored_hash,
        calculated_hash=computed_hash,
        message=(
            f"DEMO: CHAIN INTEGRITY FAILED at event index {broken_idx}. "
            "Simulated tampering with event_data detected via hash mismatch."
            if not valid else "Chain intact (unexpected)"
        ),
    )

    return TamperDemoResponse(
        message="Tamper detection demo completed successfully.",
        disclaimer=(
            "DEMO ONLY — This simulation uses ephemeral in-memory data. "
            "No real database records were modified or corrupted."
        ),
        chain_before_tamper=before_responses,
        tampered_event_index=tamper_idx,
        tampered_event_id=chain[tamper_idx].event_id,
        verification_result=verify_result,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_response(row: Dict[str, Any]) -> AuditEventResponse:
    return AuditEventResponse(
        event_id=UUID(row["event_id"]),
        event_type=AuditEventType(row["event_type"]),
        user_id=UUID(row["user_id"]) if row.get("user_id") else None,
        machine_id=UUID(row["machine_id"]) if row.get("machine_id") else None,
        session_id=UUID(row["session_id"]) if row.get("session_id") else None,
        event_data=row.get("event_data") or {},
        previous_hash=row["previous_hash"],
        current_hash=row["current_hash"],
        created_at=row["created_at"],
    )


def _row_to_mem(row: Dict[str, Any]) -> InMemoryChainEvent:
    created = row["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
    return InMemoryChainEvent(
        event_id=UUID(row["event_id"]),
        event_type=row["event_type"],
        user_id=UUID(row["user_id"]) if row.get("user_id") else None,
        machine_id=UUID(row["machine_id"]) if row.get("machine_id") else None,
        session_id=UUID(row["session_id"]) if row.get("session_id") else None,
        event_data=row.get("event_data") or {},
        created_at=created,
        previous_hash=row["previous_hash"],
        current_hash=row["current_hash"],
    )


def _mem_to_response(evt: InMemoryChainEvent) -> AuditEventResponse:
    return AuditEventResponse(
        event_id=evt.event_id,
        event_type=AuditEventType(evt.event_type),
        user_id=evt.user_id,
        machine_id=evt.machine_id,
        session_id=evt.session_id,
        event_data=evt.event_data,
        previous_hash=evt.previous_hash,
        current_hash=evt.current_hash,
        created_at=evt.created_at,
    )
