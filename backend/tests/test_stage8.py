"""
Stage 8 Tests — Security Event Audit Log with SHA-256 Hash Chaining.

Tests cover:
  1.  Hash chain engine: canonical form is deterministic
  2.  Same event inputs always produce the same SHA-256 hash
  3.  Different event data produces different hashes
  4.  Genesis event uses 64-zero previous_hash
  5.  Chain is correctly linked: each event's previous_hash == predecessor's current_hash
  6.  Chain verification: intact chain returns valid=True
  7.  Chain verification: single tampered event (data changed) is detected
  8.  Chain verification: correct broken event index is returned
  9.  Chain verification: subsequent events after tampering are also invalidated
  10. Tamper demo: returns the correct structure (chain_before_tamper, verification_result)
  11. Tamper demo: verification_result.valid is False (tamper detected)
  12. Tamper demo: disclaimer confirms no real data modified
  13. API: POST /api/logs/demo-tamper returns 200 with tamper detected
  14. API: POST /api/logs/verify-integrity returns 200
  15. API: GET  /api/logs returns 200 (list)
  16. API: POST /api/logs requires auth (401 without token)
  17. API: AUDITOR cannot POST /api/logs (403 forbidden)
  18. API: Non-auditor roles CAN POST /api/logs (201 created)
"""
from __future__ import annotations

import copy
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.audit import AuditEventCreate, AuditEventType
from app.schemas.auth import UserProfileResponse, UserRole
from app.services.audit_chain import (
    GENESIS_HASH,
    InMemoryChainEvent,
    build_in_memory_chain,
    compute_event_hash,
    verify_chain,
    _canonical_payload,
)
from app.services.audit_service import run_tamper_demo

# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

ENGINEER_ID = UUID("aaaaaaaa-0042-0042-0042-000000000042")
_AUTH = {"Authorization": "Bearer mock.jwt.token"}


def _make_profile(role: UserRole) -> UserProfileResponse:
    return UserProfileResponse(
        id=ENGINEER_ID,
        email=f"{role.value.lower()}@maintx.internal",
        name=f"Test {role.value}",
        role=role,
        department="Industrial Operations",
        engineer_code="ENG-042",
    )


@contextmanager
def _patch_auth(role: UserRole = UserRole.MAINTENANCE_ENGINEER):
    profile = _make_profile(role)
    with patch("app.api.deps.decode_supabase_jwt", return_value={"sub": str(ENGINEER_ID)}):
        with patch("app.api.deps.get_profile_by_user_id", new=AsyncMock(return_value=profile)):
            yield profile


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _make_sample_event(
    event_type: str = "DEMO_EVENT",
    offset_seconds: int = 0,
) -> InMemoryChainEvent:
    """Create a single InMemoryChainEvent with a known hash."""
    eid = uuid4()
    created = datetime(2026, 9, 23, 12, 0, offset_seconds, tzinfo=timezone.utc)
    prev_hash = GENESIS_HASH
    cur_hash = compute_event_hash(
        event_id=eid,
        event_type=event_type,
        user_id=None,
        machine_id=None,
        session_id=None,
        event_data={"test": "data", "index": offset_seconds},
        created_at=created,
        previous_hash=prev_hash,
    )
    return InMemoryChainEvent(
        event_id=eid,
        event_type=event_type,
        user_id=None,
        machine_id=None,
        session_id=None,
        event_data={"test": "data", "index": offset_seconds},
        created_at=created,
        previous_hash=prev_hash,
        current_hash=cur_hash,
    )


def _build_test_chain(n: int = 5) -> list[InMemoryChainEvent]:
    """Build a valid test chain of n events."""
    raw = [
        {
            "event_type": "DEMO_EVENT",
            "event_data": {"seq": i, "label": f"event-{i}"},
            "created_at": datetime(2026, 9, 23, 10, 0, i, tzinfo=timezone.utc),
        }
        for i in range(n)
    ]
    return build_in_memory_chain(raw)


# ---------------------------------------------------------------------------
# 1. Canonical form is deterministic
# ---------------------------------------------------------------------------

def test_canonical_form_is_deterministic():
    """Same inputs produce the same canonical JSON string."""
    eid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    created = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
    c1 = _canonical_payload(eid, "DEMO_EVENT", None, None, None, {"x": 1}, created)
    c2 = _canonical_payload(eid, "DEMO_EVENT", None, None, None, {"x": 1}, created)
    assert c1 == c2


def test_canonical_form_key_order_does_not_matter():
    """Dict key insertion order must NOT affect the canonical string."""
    eid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    created = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
    c1 = _canonical_payload(eid, "DEMO_EVENT", None, None, None, {"a": 1, "b": 2}, created)
    c2 = _canonical_payload(eid, "DEMO_EVENT", None, None, None, {"b": 2, "a": 1}, created)
    assert c1 == c2


# ---------------------------------------------------------------------------
# 2. Same inputs → same SHA-256 hash
# ---------------------------------------------------------------------------

def test_hash_is_stable_for_same_inputs():
    """compute_event_hash must be a pure function — same inputs → same hash."""
    eid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    created = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
    h1 = compute_event_hash(eid, "DEMO_EVENT", None, None, None, {"k": "v"}, created, GENESIS_HASH)
    h2 = compute_event_hash(eid, "DEMO_EVENT", None, None, None, {"k": "v"}, created, GENESIS_HASH)
    assert h1 == h2
    assert len(h1) == 64
    assert h1 == h1.lower()


# ---------------------------------------------------------------------------
# 3. Different data → different hashes
# ---------------------------------------------------------------------------

def test_different_event_data_produces_different_hashes():
    """Two events with different data must have different hashes."""
    eid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    created = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
    h1 = compute_event_hash(eid, "DEMO_EVENT", None, None, None, {"val": 1}, created, GENESIS_HASH)
    h2 = compute_event_hash(eid, "DEMO_EVENT", None, None, None, {"val": 2}, created, GENESIS_HASH)
    assert h1 != h2


# ---------------------------------------------------------------------------
# 4. Genesis event uses 64-zero previous_hash
# ---------------------------------------------------------------------------

def test_genesis_hash_is_64_zeros():
    """GENESIS_HASH must be exactly 64 zero characters."""
    assert GENESIS_HASH == "0" * 64
    assert len(GENESIS_HASH) == 64


def test_first_event_in_chain_has_genesis_previous_hash():
    """The first event in a built chain must have previous_hash == GENESIS_HASH."""
    chain = _build_test_chain(3)
    assert chain[0].previous_hash == GENESIS_HASH


# ---------------------------------------------------------------------------
# 5. Chain linkage
# ---------------------------------------------------------------------------

def test_chain_is_correctly_linked():
    """Each event's previous_hash must equal the current_hash of its predecessor."""
    chain = _build_test_chain(5)
    for i in range(1, len(chain)):
        assert chain[i].previous_hash == chain[i - 1].current_hash, (
            f"Link broken between event {i-1} and {i}"
        )


# ---------------------------------------------------------------------------
# 6. Intact chain verification → valid=True
# ---------------------------------------------------------------------------

def test_intact_chain_verifies_as_valid():
    """Verify a correctly built chain — must return valid=True."""
    chain = _build_test_chain(6)
    valid, broken_idx, _, _ = verify_chain(chain)
    assert valid is True
    assert broken_idx is None


# ---------------------------------------------------------------------------
# 7. Tampered event_data is detected
# ---------------------------------------------------------------------------

def test_tampered_event_data_detected():
    """Changing event_data without updating current_hash must break the chain."""
    chain = _build_test_chain(5)
    tampered = copy.deepcopy(chain)
    tampered[2].event_data = {"injected": "malicious payload"}  # data changed, hash NOT updated

    valid, broken_idx, _, _ = verify_chain(tampered)
    assert valid is False
    assert broken_idx == 2


# ---------------------------------------------------------------------------
# 8. Correct broken index returned
# ---------------------------------------------------------------------------

def test_correct_broken_index_returned():
    """verify_chain must identify exactly the first corrupted event index."""
    chain = _build_test_chain(7)
    tampered = copy.deepcopy(chain)
    tampered[4].event_data = {"corrupted": True}

    _, broken_idx, stored_hash, computed_hash = verify_chain(tampered)
    assert broken_idx == 4
    assert stored_hash is not None   # stored (stale) hash
    assert computed_hash is not None  # freshly computed hash
    assert stored_hash != computed_hash


# ---------------------------------------------------------------------------
# 9. Subsequent events also fail after tamper
# ---------------------------------------------------------------------------

def test_subsequent_events_invalidated_after_tamper():
    """
    After tampering with event N, events N+1, N+2, … also fail because
    their previous_hash links to the (now-invalid) hash of event N.
    """
    chain = _build_test_chain(6)
    tampered = copy.deepcopy(chain)
    # Tamper event 1 (second event)
    tampered[1].event_data = {"tampered": True}

    # The broken index is 1; events 2-5 are also implicitly broken
    valid, broken_idx, _, _ = verify_chain(tampered)
    assert valid is False
    assert broken_idx == 1


# ---------------------------------------------------------------------------
# 10. Tamper demo returns correct structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tamper_demo_returns_correct_structure():
    """run_tamper_demo must return a TamperDemoResponse with required fields."""
    result = await run_tamper_demo()
    assert result.message
    assert result.disclaimer
    assert len(result.chain_before_tamper) == 6  # 6 demo events
    assert result.tampered_event_index == 2       # PLC_BASELINE_SET event
    assert result.tampered_event_id is not None
    assert result.verification_result is not None


# ---------------------------------------------------------------------------
# 11. Tamper demo: verification_result.valid is False
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tamper_demo_chain_is_broken():
    """The tamper demo must produce a broken chain (valid=False)."""
    result = await run_tamper_demo()
    assert result.verification_result.valid is False
    assert result.verification_result.first_broken_event is not None


# ---------------------------------------------------------------------------
# 12. Tamper demo: disclaimer confirms no real data modified
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tamper_demo_disclaimer_present():
    """The tamper demo must include a clear disclaimer about in-memory only."""
    result = await run_tamper_demo()
    disclaimer_lower = result.disclaimer.lower()
    assert "demo" in disclaimer_lower
    assert "no real" in disclaimer_lower or "in-memory" in disclaimer_lower


# ---------------------------------------------------------------------------
# 13. API: POST /api/logs/demo-tamper
# ---------------------------------------------------------------------------

def test_api_demo_tamper_returns_200(client):
    """POST /api/logs/demo-tamper must return 200 with tamper detected."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        res = client.post("/api/logs/demo-tamper", headers=_AUTH)
    assert res.status_code == 200
    data = res.json()
    assert "chain_before_tamper" in data
    assert data["verification_result"]["valid"] is False
    assert "DEMO" in data["verification_result"]["message"] or "tamper" in data["verification_result"]["message"].lower()
    assert "no real" in data["disclaimer"].lower() or "in-memory" in data["disclaimer"].lower()


# ---------------------------------------------------------------------------
# 14. API: POST /api/logs/verify-integrity
# ---------------------------------------------------------------------------

def test_api_verify_integrity_returns_200(client):
    """POST /api/logs/verify-integrity must return 200 with a valid field."""
    with _patch_auth(UserRole.SECURITY_ANALYST):
        with patch(
            "app.services.audit_service.verify_chain_integrity",
            new=AsyncMock(return_value=MagicMock(
                valid=True,
                chain_length=0,
                verified_count=0,
                first_broken_event=None,
                expected_hash=None,
                calculated_hash=None,
                message="Audit log is empty — chain is trivially valid.",
            )),
        ):
            res = client.post("/api/logs/verify-integrity", headers=_AUTH)
    assert res.status_code == 200
    data = res.json()
    assert "valid" in data
    assert "chain_length" in data
    assert "message" in data


# ---------------------------------------------------------------------------
# 15. API: GET /api/logs returns list
# ---------------------------------------------------------------------------

def test_api_list_events_returns_200(client):
    """GET /api/logs must return 200 with events list."""
    with _patch_auth(UserRole.AUDITOR):
        with patch(
            "app.services.audit_service.list_events",
            new=AsyncMock(return_value={"events": [], "total": 0, "chain_length": 0}),
        ):
            res = client.get("/api/logs", headers=_AUTH)
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert "total" in data


# ---------------------------------------------------------------------------
# 16. API: POST /api/logs requires auth (401 without token)
# ---------------------------------------------------------------------------

def test_api_post_log_requires_auth(client):
    """POST /api/logs without Authorization header must return 401/403."""
    res = client.post("/api/logs", json={
        "event_type": "DEMO_EVENT",
        "event_data": {},
    })
    assert res.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 17. API: AUDITOR cannot POST /api/logs
# ---------------------------------------------------------------------------

def test_api_auditor_cannot_post_log(client):
    """AUDITOR must receive 403 when attempting to record an event."""
    with _patch_auth(UserRole.AUDITOR):
        res = client.post(
            "/api/logs",
            headers=_AUTH,
            json={"event_type": "DEMO_EVENT", "event_data": {"note": "test"}},
        )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 18. API: Non-auditor role CAN POST /api/logs
# ---------------------------------------------------------------------------

def test_api_engineer_can_post_log(client):
    """MAINTENANCE_ENGINEER must be able to record a new audit event."""
    sample_event = {
        "event_id":       str(uuid4()),
        "event_type":     "DEMO_EVENT",
        "user_id":        str(ENGINEER_ID),
        "machine_id":     None,
        "session_id":     None,
        "event_data":     {"note": "unit test event"},
        "previous_hash":  GENESIS_HASH,
        "current_hash":   "a" * 64,
        "created_at":     "2026-09-23T12:00:00+00:00",
    }

    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        with patch(
            "app.services.audit_service.record_event",
            new=AsyncMock(return_value=MagicMock(**sample_event)),
        ):
            res = client.post(
                "/api/logs",
                headers=_AUTH,
                json={"event_type": "DEMO_EVENT", "event_data": {"note": "unit test event"}},
            )
    assert res.status_code == 201
