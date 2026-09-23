"""
Stage 9 Tests — Final Maintenance Verification Engine & Closure Enforcement.

Tests cover:
  1.  Parameter comparison: approved motor speed change classified as EXPECTED
  2.  Parameter comparison: unexpected pressure change classified as UNEXPECTED
  3.  Parameter comparison: unauthorized rogue IP change classified as UNAUTHORIZED / is_critical
  4.  Parameter comparison: unapplied approved change classified as UNRESOLVED
  5.  PLC verification: matching approved logic verifies successfully
  6.  PLC verification: removal of N7 safety interlock flags SAFETY_INTERLOCK_COMPROMISED
  7.  PLC verification: unapproved instruction diff flags HASH_MISMATCH
  8.  Execution: clean scenario yields status VERIFIED and closure_allowed=True
  9.  Execution: minor unexpected change yields status REVIEW_REQUIRED and closure_allowed=False
  10. Execution: safety compromise yields status FAILED, unresolved_critical >= 1, closure_allowed=False
  11. Execution: unauthorized network IP yields status FAILED, unresolved_critical >= 1, closure_allowed=False
  12. API: GET /api/verification/demo/verified returns 200 and status VERIFIED
  13. API: GET /api/verification/demo/review-required returns 200 and status REVIEW_REQUIRED
  14. API: GET /api/verification/demo/failed-safety returns 200 and status FAILED
  15. API: Unknown demo scenario returns 404
  16. Closure prevention: complete_session with verification_status='FAILED' raises 409 Conflict
  17. Closure prevention: complete_session with unresolved critical changes in DB raises 409 Conflict
  18. Closure allowed: complete_session succeeds when verification is VERIFIED
  19. API: POST /api/verification/session/{id} requires authentication (401 without token)
  20. API: POST /api/verification/session/{id} returns 200 for authenticated engineer
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.auth import UserProfileResponse, UserRole
from app.schemas.verification import (
    ChangeClassification,
    PLCVerificationStatus,
    VerificationStatus,
)
from app.services.plc_demo import BASELINE_V17, TAMPERED_V17
from app.services.verification_engine import (
    compare_machine_parameters,
    execute_final_verification,
    verify_plc_logic_state,
)
from app.services.verification_service import APPROVED_V18, get_demo_verification

ENGINEER_ID = UUID("aaaaaaaa-0042-0042-0042-000000000042")
SESSION_ID = UUID("cccccccc-1111-2222-3333-444444444444")
MACHINE_ID = UUID("bbbbbbbb-1111-2222-3333-444444444444")
_AUTH = {"Authorization": "Bearer mock.jwt.token"}


def _make_profile(role: UserRole = UserRole.MAINTENANCE_ENGINEER) -> UserProfileResponse:
    return UserProfileResponse(
        id=ENGINEER_ID,
        email=f"{role.value.lower()}@maintx.internal",
        name=f"Test {role.value}",
        role=role,
        department="Machining Operations",
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


# ---------------------------------------------------------------------------
# 1. Parameter Comparison Tests
# ---------------------------------------------------------------------------

def test_compare_parameters_expected_change():
    """Approved motor speed change (3000 -> 3200) is classified as EXPECTED."""
    base = {"motor_speed_rpm": 3000}
    approved = [{"parameter_name": "motor_speed_rpm", "new_value": 3200}]
    actual = {"motor_speed_rpm": 3200}

    comps = compare_machine_parameters(base, approved, actual)
    motor_comp = next(c for c in comps if c.parameter_name == "motor_speed_rpm")

    assert motor_comp.classification == ChangeClassification.EXPECTED
    assert motor_comp.risk_level == "LOW"
    assert motor_comp.actual_value == 3200


def test_compare_parameters_unexpected_operational_change():
    """Unapproved pressure limit change (5.0 -> 5.2 bar) is classified as UNEXPECTED."""
    base = {"pressure_limit_bar": 5.0}
    approved = []
    actual = {"pressure_limit_bar": 5.2}

    comps = compare_machine_parameters(base, approved, actual)
    press_comp = next(c for c in comps if c.parameter_name == "pressure_limit_bar")

    assert press_comp.classification == ChangeClassification.UNEXPECTED
    assert press_comp.risk_level == "MEDIUM"
    assert press_comp.is_critical is False


def test_compare_parameters_unauthorized_critical_change():
    """Unauthorized IP change (192.168.10.20 -> 192.168.10.50) is classified as UNAUTHORIZED & is_critical."""
    base = {"ip_address": "192.168.10.20"}
    approved = []
    actual = {"ip_address": "192.168.10.50"}

    comps = compare_machine_parameters(base, approved, actual)
    ip_comp = next(c for c in comps if c.parameter_name == "ip_address")

    assert ip_comp.classification == ChangeClassification.UNAUTHORIZED
    assert ip_comp.is_critical is True
    assert ip_comp.risk_level == "CRITICAL"


def test_compare_parameters_unapplied_approved_deviation():
    """Approved change (expected 3200) but machine left at 3000 is UNRESOLVED."""
    base = {"motor_speed_rpm": 3000}
    approved = [{"parameter_name": "motor_speed_rpm", "new_value": 3200}]
    actual = {"motor_speed_rpm": 3000}

    comps = compare_machine_parameters(base, approved, actual)
    motor_comp = next(c for c in comps if c.parameter_name == "motor_speed_rpm")

    assert motor_comp.classification == ChangeClassification.UNRESOLVED


# ---------------------------------------------------------------------------
# 2. PLC Verification Tests
# ---------------------------------------------------------------------------

def test_plc_verification_matching_approved_v18():
    """Approved v18 program verified against actual v18 program."""
    detail = verify_plc_logic_state(
        baseline_plc=BASELINE_V17,
        approved_plc=APPROVED_V18,
        actual_plc=APPROVED_V18,
    )
    assert detail.hash_matches is True
    assert detail.safety_changes_detected is False
    assert detail.safety_interlock_compromised is False
    assert detail.status == PLCVerificationStatus.VERIFIED


def test_plc_verification_safety_interlock_n7_removed():
    """Actual program missing network N7 triggers SAFETY_INTERLOCK_COMPROMISED."""
    detail = verify_plc_logic_state(
        baseline_plc=BASELINE_V17,
        approved_plc=APPROVED_V18,
        actual_plc=TAMPERED_V17,
    )
    assert detail.safety_interlock_compromised is True
    assert detail.status == PLCVerificationStatus.SAFETY_INTERLOCK_COMPROMISED
    assert any("N7" in d for d in detail.details)


def test_plc_verification_hash_mismatch():
    """Actual program modified with unapproved logic results in hash mismatch."""
    modified = copy.deepcopy(BASELINE_V17)
    # Modify a contact tag
    modified["networks"][0]["contacts"][0]["tag"] = "I:0/99"

    detail = verify_plc_logic_state(
        baseline_plc=BASELINE_V17,
        approved_plc=BASELINE_V17,
        actual_plc=modified,
    )
    assert detail.hash_matches is False
    assert detail.status in (PLCVerificationStatus.HASH_MISMATCH, PLCVerificationStatus.UNAPPROVED_LOGIC)


# ---------------------------------------------------------------------------
# 3. Overall Execution Statuses
# ---------------------------------------------------------------------------

def test_final_verification_clean_scenario():
    """Clean maintenance scenario produces VERIFIED and closure_allowed=True."""
    base_params = {"motor_speed_rpm": 3000, "ip_address": "192.168.10.20"}
    approved_changes = [{"parameter_name": "motor_speed_rpm", "new_value": 3200}]
    actual_params = {"motor_speed_rpm": 3200, "ip_address": "192.168.10.20"}

    res = execute_final_verification(
        baseline_params=base_params,
        approved_changes=approved_changes,
        final_params=actual_params,
        baseline_plc=BASELINE_V17,
        actual_plc=APPROVED_V18,
        approved_plc=APPROVED_V18,
    )
    assert res.final_status == VerificationStatus.VERIFIED
    assert res.closure_allowed is True
    assert res.unresolved_critical_changes == 0
    assert res.expected_changes_count == 1
    assert res.unexpected_changes_count == 0


def test_final_verification_minor_unexpected_discrepancy():
    """Minor unexpected change produces REVIEW_REQUIRED and closure_allowed=False."""
    base_params = {"motor_speed_rpm": 3000, "pressure_limit_bar": 5.0}
    approved_changes = [{"parameter_name": "motor_speed_rpm", "new_value": 3200}]
    actual_params = {"motor_speed_rpm": 3200, "pressure_limit_bar": 5.2}

    res = execute_final_verification(
        baseline_params=base_params,
        approved_changes=approved_changes,
        final_params=actual_params,
        baseline_plc=BASELINE_V17,
        actual_plc=APPROVED_V18,
        approved_plc=APPROVED_V18,
    )
    assert res.final_status == VerificationStatus.REVIEW_REQUIRED
    assert res.closure_allowed is False
    assert res.unexpected_changes_count == 1


def test_final_verification_failed_on_safety_interlock_compromise():
    """N7 removal produces FAILED, closure_allowed=False, unresolved_critical_changes >= 1."""
    base_params = {"motor_speed_rpm": 3000}
    approved_changes = [{"parameter_name": "motor_speed_rpm", "new_value": 3200}]
    actual_params = {"motor_speed_rpm": 3200}

    res = execute_final_verification(
        baseline_params=base_params,
        approved_changes=approved_changes,
        final_params=actual_params,
        baseline_plc=BASELINE_V17,
        actual_plc=TAMPERED_V17,  # N7 missing
        approved_plc=APPROVED_V18,
    )
    assert res.final_status == VerificationStatus.FAILED
    assert res.closure_allowed is False
    assert res.unresolved_critical_changes >= 1
    assert res.plc_verification.safety_interlock_compromised is True


def test_final_verification_failed_on_unauthorized_ip():
    """Unauthorized rogue IP produces FAILED and closure_allowed=False."""
    base_params = {"ip_address": "192.168.10.20", "motor_speed_rpm": 3000}
    approved_changes = [{"parameter_name": "motor_speed_rpm", "new_value": 3200}]
    actual_params = {"ip_address": "192.168.10.50", "motor_speed_rpm": 3200}

    res = execute_final_verification(
        baseline_params=base_params,
        approved_changes=approved_changes,
        final_params=actual_params,
        baseline_plc=BASELINE_V17,
        actual_plc=APPROVED_V18,
        approved_plc=APPROVED_V18,
    )
    assert res.final_status == VerificationStatus.FAILED
    assert res.closure_allowed is False
    assert res.unresolved_critical_changes >= 1
    assert res.unauthorized_changes_count >= 1


# ---------------------------------------------------------------------------
# 4. API Demo Scenarios
# ---------------------------------------------------------------------------

def test_api_demo_verified(client):
    """GET /api/verification/demo/verified returns 200 and VERIFIED status."""
    with _patch_auth():
        res = client.get("/api/verification/demo/verified", headers=_AUTH)
        assert res.status_code == 200
        data = res.json()
        assert data["final_status"] == "VERIFIED"
        assert data["closure_allowed"] is True
        assert data["unresolved_critical_changes"] == 0


def test_api_demo_review_required(client):
    """GET /api/verification/demo/review-required returns 200 and REVIEW_REQUIRED."""
    with _patch_auth():
        res = client.get("/api/verification/demo/review-required", headers=_AUTH)
        assert res.status_code == 200
        data = res.json()
        assert data["final_status"] == "REVIEW_REQUIRED"
        assert data["closure_allowed"] is False
        assert data["unexpected_changes_count"] >= 1


def test_api_demo_failed_safety(client):
    """GET /api/verification/demo/failed-safety returns 200 and FAILED status."""
    with _patch_auth():
        res = client.get("/api/verification/demo/failed-safety", headers=_AUTH)
        assert res.status_code == 200
        data = res.json()
        assert data["final_status"] == "FAILED"
        assert data["closure_allowed"] is False
        assert data["unresolved_critical_changes"] >= 1


def test_api_demo_unknown_scenario_returns_404(client):
    """GET /api/verification/demo/unknown returns 404."""
    with _patch_auth():
        res = client.get("/api/verification/demo/unknown-scenario-xyz", headers=_AUTH)
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# 5. Maintenance Closure Gatekeeper Enforcement
# ---------------------------------------------------------------------------

def test_complete_session_blocked_when_failed_status(client):
    """Attempting complete_session with verification_status='FAILED' raises 409 Conflict."""
    mock_session = {
        "id": str(SESSION_ID),
        "machine_id": str(MACHINE_ID),
        "request_id": str(uuid4()),
        "engineer_id": str(ENGINEER_ID),
        "session_status": "ACTIVE",
        "verification_status": "PENDING",
    }

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_session

    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        with patch("app.services.maintenance_service.get_supabase_client", return_value=mock_sb):
            res = client.post(
                f"/api/maintenance/sessions/{SESSION_ID}/complete",
                json={"verification_status": "FAILED", "notes": "Compromised machine"},
                headers=_AUTH,
            )
            assert res.status_code == 409
            assert "Maintenance closure blocked" in res.json()["detail"]


def test_complete_session_blocked_when_unresolved_critical_changes_in_db(client):
    """Attempting complete_session when database verification has unresolved critical changes raises 409."""
    mock_session = {
        "id": str(SESSION_ID),
        "machine_id": str(MACHINE_ID),
        "request_id": str(uuid4()),
        "engineer_id": str(ENGINEER_ID),
        "session_status": "ACTIVE",
        "verification_status": "PENDING",
    }

    mock_verif = [{
        "final_status": "FAILED",
        "unresolved_critical_changes": 2,
    }]

    mock_sb = MagicMock()
    # Mock session fetch
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_session
    # Mock verification_results query
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = mock_verif

    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        with patch("app.services.maintenance_service.get_supabase_client", return_value=mock_sb):
            res = client.post(
                f"/api/maintenance/sessions/{SESSION_ID}/complete",
                json={"verification_status": "VERIFIED"},
                headers=_AUTH,
            )
            assert res.status_code == 409
            assert "unresolved critical change(s) exist" in res.json()["detail"]


def test_complete_session_allowed_when_verified(client):
    """complete_session succeeds when verification is VERIFIED and session is active."""
    mock_session = {
        "id": str(SESSION_ID),
        "machine_id": str(MACHINE_ID),
        "request_id": str(uuid4()),
        "engineer_id": str(ENGINEER_ID),
        "session_status": "ACTIVE",
        "verification_status": "VERIFIED",
        "started_at": "2026-09-23T10:00:00Z",
        "created_at": "2026-09-23T10:00:00Z",
    }

    mock_completed_session = {
        **mock_session,
        "session_status": "COMPLETED",
        "completed_at": "2026-09-23T12:00:00Z",
        "verification_status": "VERIFIED",
    }

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = mock_session
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [mock_completed_session]

    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        with patch("app.services.maintenance_service.get_supabase_client", return_value=mock_sb):
            res = client.post(
                f"/api/maintenance/sessions/{SESSION_ID}/complete",
                json={"verification_status": "VERIFIED", "notes": "Work completed cleanly"},
                headers=_AUTH,
            )
            assert res.status_code == 200
            assert res.json()["session_status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# 6. Session Verification API Authentication
# ---------------------------------------------------------------------------

def test_api_verify_session_requires_auth(client):
    """POST /api/verification/session/{id} returns 401 without auth token."""
    res = client.post(f"/api/verification/session/{SESSION_ID}")
    assert res.status_code == 401


def test_api_verify_session_success(client):
    """POST /api/verification/session/{id} returns 200 for authenticated engineer."""
    mock_res = get_demo_verification("verified")

    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        with patch("app.services.verification_service.run_session_verification", new=AsyncMock(return_value=mock_res)):
            res = client.post(
                f"/api/verification/session/{SESSION_ID}",
                json={"notes": "Final inspection test"},
                headers=_AUTH,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["final_status"] == "VERIFIED"
            assert data["closure_allowed"] is True
