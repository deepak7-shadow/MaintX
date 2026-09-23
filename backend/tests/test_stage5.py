"""
Stage 5 tests — PLC Engine (canonicalization, hashing, diff).

Tests cover:
  1. Canonicalization is deterministic and strips runtime fields
  2. Hash is stable for the same program
  3. Different programs produce different hashes
  4. Diff detects added networks
  5. Diff detects removed networks
  6. Diff detects N7 safety interlock removal → INTEGRITY_FAILED
  7. Diff detects timer setpoint changes
  8. Diff detects contact type changes
  9. Diff detects coil changes in safety networks
 10. Diff: identical programs → VERIFIED, hash match
 11. API: fingerprint endpoint
 12. API: ad-hoc diff endpoint
 13. API: demo tamper endpoint → INTEGRITY_FAILED + SAFETY INTERLOCK REMOVED
 14. API: integrity check endpoint
 15. Canonicalize is order-independent (sorted networks)
 16. Hash changes when a setpoint changes
"""
from __future__ import annotations

import copy
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.auth import UserProfileResponse, UserRole
from app.schemas.plc import PLCDiffResult
from app.services.plc_demo import BASELINE_V17, TAMPERED_V17
from app.services.plc_engine import (
    calculate_plc_hash,
    canonicalize_plc_logic,
    compare_plc_logic,
    fingerprint,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MACHINE_ID = UUID("cccccccc-0001-0001-0001-000000000001")
ENGINEER_ID = UUID("aaaaaaaa-0042-0042-0042-000000000042")
_AUTH = {"Authorization": "Bearer mock.jwt.token"}


def _make_profile(role: UserRole) -> UserProfileResponse:
    return UserProfileResponse(
        id=ENGINEER_ID,
        email=f"{role.value.lower()}@test.local",
        name=f"Test {role.value}",
        role=role,
        department="Test",
        engineer_code="TECH-042",
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


# ── Minimal PLC programs for unit tests ──────────────────────────────────────

SIMPLE_PROG = {
    "program_name": "TEST",
    "version": "v1",
    "plc_type": "TEST",
    "networks": [
        {
            "network_id": "N1",
            "description": "Test network",
            "safety_critical": False,
            "enabled": True,
            "contacts": [{"tag": "I:0/0", "contact_type": "NORMALLY_OPEN"}],
            "coils": [{"tag": "O:0/0", "coil_type": "OUTPUT"}],
            "instructions": [],
        }
    ],
    "data_files": {},
    "metadata": {},
}

SAFETY_PROG = {
    "program_name": "TEST",
    "version": "v1",
    "plc_type": "TEST",
    "networks": [
        {
            "network_id": "N7",
            "description": "Safety interlock",
            "safety_critical": True,
            "enabled": True,
            "contacts": [{"tag": "N7:0/0", "contact_type": "NORMALLY_OPEN"}],
            "coils": [{"tag": "N7:1/0", "coil_type": "OUTPUT"}],
            "instructions": [],
        }
    ],
    "data_files": {},
}


# ---------------------------------------------------------------------------
# 1. Canonicalization
# ---------------------------------------------------------------------------


def test_canonicalize_strips_description_and_author():
    """Description and author fields must not appear in the canonical form."""
    prog = copy.deepcopy(SIMPLE_PROG)
    prog["description"] = "Verbose description that should not affect the hash"
    prog["author"] = "Someone"
    canon = canonicalize_plc_logic(prog)
    obj = json.loads(canon)
    assert "description" not in obj
    assert "author" not in obj
    assert "metadata" not in obj


def test_canonicalize_strips_network_descriptions():
    """Network-level description must not appear in canonical form."""
    prog = copy.deepcopy(SIMPLE_PROG)
    prog["networks"][0]["description"] = "Rung comment that should be ignored"
    canon = canonicalize_plc_logic(prog)
    network = json.loads(canon)["networks"][0]
    assert "description" not in network


def test_canonicalize_sorts_networks_by_id():
    """Networks must always be sorted by network_id regardless of insertion order."""
    prog = {
        "program_name": "P",
        "version": "v1",
        "plc_type": "T",
        "networks": [
            {"network_id": "N3", "enabled": True, "safety_critical": False,
             "contacts": [], "coils": [], "instructions": []},
            {"network_id": "N1", "enabled": True, "safety_critical": False,
             "contacts": [], "coils": [], "instructions": []},
            {"network_id": "N2", "enabled": True, "safety_critical": False,
             "contacts": [], "coils": [], "instructions": []},
        ],
        "data_files": {},
    }
    canon = canonicalize_plc_logic(prog)
    ids = [n["network_id"] for n in json.loads(canon)["networks"]]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# 2. Hashing
# ---------------------------------------------------------------------------


def test_hash_is_stable_for_same_program():
    """Same program must always produce the same hash."""
    h1 = calculate_plc_hash(BASELINE_V17)
    h2 = calculate_plc_hash(BASELINE_V17)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_different_programs_produce_different_hashes():
    """Baseline and tampered programs must have different hashes."""
    h_base = calculate_plc_hash(BASELINE_V17)
    h_tamp = calculate_plc_hash(TAMPERED_V17)
    assert h_base != h_tamp


def test_hash_ignores_description_changes():
    """Changing description or author alone must NOT change the hash."""
    p1 = copy.deepcopy(SIMPLE_PROG)
    p2 = copy.deepcopy(SIMPLE_PROG)
    p2["description"] = "New description"
    p2["author"] = "Someone Else"
    p2["networks"][0]["description"] = "Rung description changed"
    assert calculate_plc_hash(p1) == calculate_plc_hash(p2)


def test_hash_changes_on_setpoint_change():
    """Changing a timer preset (setpoint) must change the hash."""
    p1 = {
        "program_name": "P", "version": "v1", "plc_type": "T",
        "networks": [{
            "network_id": "N1", "enabled": True, "safety_critical": False,
            "contacts": [], "coils": [],
            "instructions": [{"instruction_type": "TON", "tag": "T4:0", "preset": 5000}],
        }],
        "data_files": {},
    }
    p2 = copy.deepcopy(p1)
    p2["networks"][0]["instructions"][0]["preset"] = 9000  # setpoint changed
    assert calculate_plc_hash(p1) != calculate_plc_hash(p2)


def test_hash_ignores_accumulator():
    """Accumulator (runtime) change must NOT affect the hash."""
    p1 = {
        "program_name": "P", "version": "v1", "plc_type": "T",
        "networks": [{
            "network_id": "N1", "enabled": True, "safety_critical": False,
            "contacts": [], "coils": [],
            "instructions": [{"instruction_type": "TON", "tag": "T4:0", "preset": 5000, "accumulator": 0}],
        }],
        "data_files": {},
    }
    p2 = copy.deepcopy(p1)
    p2["networks"][0]["instructions"][0]["accumulator"] = 4999  # runtime value
    assert calculate_plc_hash(p1) == calculate_plc_hash(p2)


# ---------------------------------------------------------------------------
# 3. Diff — network-level changes
# ---------------------------------------------------------------------------


def test_diff_identical_programs_returns_verified():
    """Identical programs must return VERIFIED with zero changes."""
    result = compare_plc_logic(BASELINE_V17, BASELINE_V17)
    assert result.hash_match is True
    assert result.integrity_status == "VERIFIED"
    assert result.total_changes == 0
    assert result.safety_violations == []


def test_diff_detects_added_network():
    base = copy.deepcopy(SIMPLE_PROG)
    curr = copy.deepcopy(SIMPLE_PROG)
    curr["networks"].append({
        "network_id": "N99",
        "description": "New rung",
        "safety_critical": False,
        "enabled": True,
        "contacts": [{"tag": "I:2/0", "contact_type": "NORMALLY_OPEN"}],
        "coils": [{"tag": "O:2/0", "coil_type": "OUTPUT"}],
        "instructions": [],
    })
    result = compare_plc_logic(base, curr)
    assert "N99" in result.added_networks
    assert result.total_changes == 1
    assert result.hash_match is False


def test_diff_detects_removed_network():
    base = copy.deepcopy(SIMPLE_PROG)
    base["networks"].append({
        "network_id": "N2",
        "description": "Second rung",
        "safety_critical": False,
        "enabled": True,
        "contacts": [],
        "coils": [{"tag": "O:1/0", "coil_type": "OUTPUT"}],
        "instructions": [],
    })
    curr = copy.deepcopy(SIMPLE_PROG)   # N2 absent
    result = compare_plc_logic(base, curr)
    assert "N2" in result.removed_networks


# ---------------------------------------------------------------------------
# 4. Diff — N7 safety interlock removal (THE key scenario)
# ---------------------------------------------------------------------------


def test_diff_n7_removal_triggers_integrity_failed():
    """
    CORE TEST: Removing N7 (SAFETY_OK → MACHINE_ENABLE) from the PLC program
    must trigger:
      - hash_match = False
      - integrity_status = INTEGRITY_FAILED
      - at least one safety_violation mentioning N7
      - "SAFETY INTERLOCK REMOVED" in the violation message
    """
    result = compare_plc_logic(BASELINE_V17, TAMPERED_V17)

    assert result.hash_match is False, "Hash must NOT match after N7 removal"
    assert result.integrity_status == "INTEGRITY_FAILED", (
        f"Expected INTEGRITY_FAILED, got {result.integrity_status}"
    )
    assert "N7" in result.removed_networks, "N7 must appear in removed_networks"
    assert len(result.safety_violations) >= 1

    violation_text = " ".join(result.safety_violations)
    assert "SAFETY INTERLOCK REMOVED" in violation_text, (
        f"Expected 'SAFETY INTERLOCK REMOVED' in violations, got: {violation_text}"
    )
    assert "N7" in violation_text

    # Check the integrity message
    assert "PLC HASH MISMATCH" in result.integrity_message
    assert "PLC LOGIC INTEGRITY FAILED" in result.integrity_message

    # The diff entry for N7 must be CRITICAL
    n7_diff = next((d for d in result.network_diffs if d.network_id == "N7"), None)
    assert n7_diff is not None
    assert n7_diff.change_type == "REMOVED"
    assert n7_diff.severity == "CRITICAL"
    assert n7_diff.safety_critical is True


def test_diff_n7_removal_network_diff_details():
    """N7 diff entry must include the contacts and coils that were removed."""
    result = compare_plc_logic(BASELINE_V17, TAMPERED_V17)
    n7_diff = next(d for d in result.network_diffs if d.network_id == "N7")
    assert "N7:0/0" in str(n7_diff.details)  # SAFETY_OK contact
    assert "N7:1/0" in str(n7_diff.details)  # MACHINE_ENABLE coil


def test_diff_safety_interlock_disabled_network():
    """Disabling (not removing) a safety network must also trigger a violation."""
    base = copy.deepcopy(SAFETY_PROG)
    curr = copy.deepcopy(SAFETY_PROG)
    curr["networks"][0]["enabled"] = False  # disabled instead of removed
    result = compare_plc_logic(base, curr)
    assert result.hash_match is False
    # Should flag as modified with safety violation
    assert "N7" in result.modified_networks
    safety_text = " ".join(result.safety_violations)
    assert "DISABLED" in safety_text.upper() or "INTERLOCK" in safety_text.upper()


# ---------------------------------------------------------------------------
# 5. Diff — setpoint / timer changes
# ---------------------------------------------------------------------------


def test_diff_detects_timer_setpoint_change():
    """Changing a TON preset must appear in the diff."""
    base = {
        "program_name": "P", "version": "v1", "plc_type": "T",
        "networks": [{
            "network_id": "N5",
            "description": "Coolant timer",
            "safety_critical": False,
            "enabled": True,
            "contacts": [],
            "coils": [],
            "instructions": [{"instruction_type": "TON", "tag": "T4:2", "preset": 30000}],
        }],
        "data_files": {},
    }
    curr = copy.deepcopy(base)
    curr["networks"][0]["instructions"][0]["preset"] = 5000   # shortened
    result = compare_plc_logic(base, curr)
    assert "N5" in result.modified_networks
    details = str(result.network_diffs)
    assert "SETPOINT_CHANGED" in details
    assert "30000" in details
    assert "5000" in details


def test_diff_detects_contact_type_change():
    """Changing a contact from NORMALLY_CLOSED to NORMALLY_OPEN must be detected."""
    base = {
        "program_name": "P", "version": "v1", "plc_type": "T",
        "networks": [{
            "network_id": "N1",
            "safety_critical": False,
            "enabled": True,
            "contacts": [{"tag": "I:0/0", "contact_type": "NORMALLY_CLOSED"}],
            "coils": [],
            "instructions": [],
        }],
        "data_files": {},
    }
    curr = copy.deepcopy(base)
    curr["networks"][0]["contacts"][0]["contact_type"] = "NORMALLY_OPEN"
    result = compare_plc_logic(base, curr)
    assert "N1" in result.modified_networks
    assert "CONTACT_TYPE_CHANGED" in str(result.network_diffs)


# ---------------------------------------------------------------------------
# 6. Fingerprint schema
# ---------------------------------------------------------------------------


def test_fingerprint_schema():
    fp = fingerprint(BASELINE_V17)
    assert fp.program_name == "CNC-01"
    assert fp.version == "v17"
    assert len(fp.sha256) == 64
    assert fp.network_count == 7    # N1..N7
    assert fp.sha256 == calculate_plc_hash(BASELINE_V17)
    assert isinstance(fp.computed_at, datetime)


# ---------------------------------------------------------------------------
# 7. API — demo tamper endpoint
# ---------------------------------------------------------------------------


def test_api_demo_tamper_returns_integrity_failed(client):
    """The /demo-tamper endpoint must return INTEGRITY_FAILED with N7 violation."""
    machine_data = {
        "id": str(MACHINE_ID), "machine_code": "CNC-01",
        "name": "CNC-01", "machine_type": "CNC_MILLING",
        "criticality": "CRITICAL", "location": "Sector 4",
        "status": "OPERATIONAL", "plc_version": "v17",
        "plc_integrity_status": "VERIFIED", "firmware": "4.2.1",
        "ip_address": "192.168.10.20", "subnet": "255.255.255.0",
        "gateway": "192.168.10.1",
        "firewall_configuration": {}, "safety_configuration": {},
        "parameters": {}, "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    from app.schemas.machines import MachineResponse
    machine = MachineResponse(**machine_data)
    with patch("app.api.plc.machine_service.get_machine", new=AsyncMock(return_value=machine)):
        with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
            r = client.get("/api/plc/CNC-01/demo-tamper", headers=_AUTH)

    assert r.status_code == 200
    body = r.json()

    assert body["hash_match"] is False
    assert body["integrity_status"] == "INTEGRITY_FAILED"
    assert "PLC HASH MISMATCH" in body["integrity_message"]
    assert "PLC LOGIC INTEGRITY FAILED" in body["integrity_message"]
    assert "N7" in body["removed_networks"]
    assert len(body["safety_violations"]) >= 1
    assert any("SAFETY INTERLOCK REMOVED" in v for v in body["safety_violations"])


def test_api_demo_tamper_requires_auth(client):
    r = client.get("/api/plc/CNC-01/demo-tamper")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 8. API — ad-hoc diff endpoint
# ---------------------------------------------------------------------------


def test_api_diff_endpoint_n7_scenario(client):
    """POST /api/plc/diff with baseline and tampered program."""
    with _patch_auth(UserRole.SECURITY_ANALYST):
        r = client.post(
            "/api/plc/diff",
            headers=_AUTH,
            json={"baseline": BASELINE_V17, "current": TAMPERED_V17},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["integrity_status"] == "INTEGRITY_FAILED"
    assert "N7" in body["removed_networks"]


def test_api_diff_endpoint_identical_programs(client):
    """POST /api/plc/diff with identical programs → VERIFIED."""
    with _patch_auth(UserRole.SECURITY_ANALYST):
        r = client.post(
            "/api/plc/diff",
            headers=_AUTH,
            json={"baseline": BASELINE_V17, "current": BASELINE_V17},
        )
    assert r.status_code == 200
    assert r.json()["integrity_status"] == "VERIFIED"
    assert r.json()["hash_match"] is True


def test_api_diff_missing_keys_returns_422(client):
    with _patch_auth():
        r = client.post(
            "/api/plc/diff",
            headers=_AUTH,
            json={"only_baseline": BASELINE_V17},  # missing "current"
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 9. API — fingerprint endpoint
# ---------------------------------------------------------------------------


def test_api_fingerprint_endpoint(client):
    machine_data = {
        "id": str(MACHINE_ID), "machine_code": "CNC-01",
        "name": "CNC-01", "machine_type": "CNC_MILLING",
        "criticality": "CRITICAL", "location": "Sector 4",
        "status": "OPERATIONAL", "plc_version": "v17",
        "plc_integrity_status": "VERIFIED", "firmware": "4.2.1",
        "ip_address": "192.168.10.20", "subnet": "255.255.255.0",
        "gateway": "192.168.10.1",
        "firewall_configuration": {}, "safety_configuration": {},
        "parameters": {}, "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    from app.schemas.machines import MachineResponse
    machine = MachineResponse(**machine_data)
    with patch("app.api.plc.machine_service.get_machine", new=AsyncMock(return_value=machine)):
        with _patch_auth():
            r = client.post(
                "/api/plc/CNC-01/fingerprint",
                headers=_AUTH,
                json=BASELINE_V17,
            )
    assert r.status_code == 200
    body = r.json()
    assert body["program_name"] == "CNC-01"
    assert body["version"] == "v17"
    assert len(body["sha256"]) == 64
    assert body["network_count"] == 7
    assert body["sha256"] == calculate_plc_hash(BASELINE_V17)
