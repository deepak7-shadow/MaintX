"""
SHA-256 Hash Chain Engine — pure Python, no I/O.

Implements the tamper-evident hash chaining algorithm used by the
MaintX Security Event Audit Log.

Algorithm
---------
1. Each event is serialised to a canonical JSON string (keys sorted,
   timestamps normalised, UUIDs lowercased).
2. `current_hash = SHA-256(canonical_payload + previous_hash)`
3. The first (genesis) event uses `previous_hash = "0" * 64`.
4. Every subsequent event's `previous_hash` is the `current_hash` of
   its immediate predecessor.

Tamper Detection
----------------
Verifying the chain walks every event in ascending `created_at` order,
recomputes the expected `current_hash`, and compares it to the stored
value.  If any event diverges, the chain is broken at that point and
every subsequent event will also appear broken (because their
`previous_hash` links to the corrupted value).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID


# The genesis previous_hash — 64 zero hex chars.
GENESIS_HASH: str = "0" * 64


def _normalise_value(v: Any) -> Any:
    """Recursively normalise values for canonical serialisation."""
    if isinstance(v, UUID):
        return str(v).lower()
    if isinstance(v, datetime):
        # Always UTC, always the same ISO format
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    if isinstance(v, dict):
        return {str(k): _normalise_value(val) for k, val in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_normalise_value(item) for item in v]
    return v


def _canonical_payload(
    event_id: UUID,
    event_type: str,
    user_id: Optional[UUID],
    machine_id: Optional[UUID],
    session_id: Optional[UUID],
    event_data: Dict[str, Any],
    created_at: datetime,
) -> str:
    """
    Build the canonical, deterministic JSON string for an event.

    All fields that contribute to the hash are included.  Sorting keys
    ensures the same bytes regardless of dict insertion order.
    """
    payload: Dict[str, Any] = {
        "event_id":   str(event_id).lower(),
        "event_type": event_type,
        "user_id":    str(user_id).lower() if user_id else None,
        "machine_id": str(machine_id).lower() if machine_id else None,
        "session_id": str(session_id).lower() if session_id else None,
        "event_data": _normalise_value(event_data),
        "created_at": _normalise_value(created_at),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_event_hash(
    event_id: UUID,
    event_type: str,
    user_id: Optional[UUID],
    machine_id: Optional[UUID],
    session_id: Optional[UUID],
    event_data: Dict[str, Any],
    created_at: datetime,
    previous_hash: str,
) -> str:
    """
    Compute the SHA-256 `current_hash` for a single audit event.

    Returns a 64-character lowercase hex string.
    """
    canonical = _canonical_payload(
        event_id=event_id,
        event_type=event_type,
        user_id=user_id,
        machine_id=machine_id,
        session_id=session_id,
        event_data=event_data,
        created_at=created_at,
    )
    # Hash = SHA-256( canonical_json + previous_hash )
    raw = f"{canonical}{previous_hash}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# In-memory chain: used for tamper demo & unit tests
# ---------------------------------------------------------------------------

class InMemoryChainEvent:
    """Lightweight struct representing one link in a simulated chain."""

    def __init__(
        self,
        event_id: UUID,
        event_type: str,
        user_id: Optional[UUID],
        machine_id: Optional[UUID],
        session_id: Optional[UUID],
        event_data: Dict[str, Any],
        created_at: datetime,
        previous_hash: str,
        current_hash: str,
    ) -> None:
        self.event_id      = event_id
        self.event_type    = event_type
        self.user_id       = user_id
        self.machine_id    = machine_id
        self.session_id    = session_id
        self.event_data    = event_data
        self.created_at    = created_at
        self.previous_hash = previous_hash
        self.current_hash  = current_hash


def build_in_memory_chain(
    events: List[Dict[str, Any]],
) -> List[InMemoryChainEvent]:
    """
    Build a correctly-linked hash chain from a list of event dicts.

    Each dict should have: event_type, user_id, machine_id, session_id, event_data, created_at.
    event_id and hashes are generated automatically.
    """
    chain: List[InMemoryChainEvent] = []
    prev_hash = GENESIS_HASH

    for raw in events:
        eid       = uuid.uuid4()
        etype     = raw["event_type"]
        uid       = raw.get("user_id")
        mid       = raw.get("machine_id")
        sid       = raw.get("session_id")
        edata     = raw.get("event_data", {})
        created   = raw.get("created_at", datetime.now(timezone.utc))

        cur_hash = compute_event_hash(
            event_id=eid,
            event_type=etype,
            user_id=uid,
            machine_id=mid,
            session_id=sid,
            event_data=edata,
            created_at=created,
            previous_hash=prev_hash,
        )

        chain.append(InMemoryChainEvent(
            event_id=eid,
            event_type=etype,
            user_id=uid,
            machine_id=mid,
            session_id=sid,
            event_data=edata,
            created_at=created,
            previous_hash=prev_hash,
            current_hash=cur_hash,
        ))
        prev_hash = cur_hash

    return chain


def verify_chain(
    events: List[InMemoryChainEvent],
) -> Tuple[bool, Optional[int], Optional[str], Optional[str]]:
    """
    Verify the integrity of a hash chain.

    Returns:
        (valid, broken_index, expected_hash, calculated_hash)

    If valid:  (True, None, None, None)
    If broken: (False, <index>, <stored_hash>, <recomputed_hash>)
    """
    prev_hash = GENESIS_HASH

    for i, evt in enumerate(events):
        expected = compute_event_hash(
            event_id=evt.event_id,
            event_type=evt.event_type,
            user_id=evt.user_id,
            machine_id=evt.machine_id,
            session_id=evt.session_id,
            event_data=evt.event_data,
            created_at=evt.created_at,
            previous_hash=prev_hash,
        )
        if evt.current_hash != expected:
            return False, i, evt.current_hash, expected
        prev_hash = evt.current_hash

    return True, None, None, None
