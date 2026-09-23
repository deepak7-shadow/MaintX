"""
Stage 6 Tests — Change Detection Engine & Authorization Policies.

Covers:
  1. Expected motor change (3000 -> 3200) => EXPECTED, AUTHORIZED
  2. Unexpected IP change (192.168.10.20 -> 192.168.10.50) => UNEXPECTED, UNAUTHORIZED, HIGH RISK
  3. Safety PLC modification (N7 interlock) => CRITICAL, SUPERVISOR REVIEW REQUIRED
  4. Safety configuration modification => CRITICAL, SUPERVISOR REVIEW REQUIRED
  5. Unexpected firmware modification => UNEXPECTED, UNAUTHORIZED, HIGH RISK
  6. Unexpected firewall modification => UNEXPECTED, UNAUTHORIZED, HIGH RISK
  7. Difference detection across all 6 categories (PARAMETERS, PLC_LOGIC, NETWORK, FIREWALL, FIRMWARE, SAFETY_CONFIG)
  8. Demo endpoint: expected motor change
  9. Demo endpoint: unexpected IP change
 10. Demo endpoint: safety PLC modification
 11. Security & RBAC: Auditor cannot record changes (403)
 12. Security & RBAC: Auditor cannot run change detection (403)
 13. Security & RBAC: Engineer cannot review changes (403)
 14. Security & RBAC: Supervisor can review & approve changes (200)
 15. Security & RBAC: Admin can review & reject changes (200)
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.auth import UserProfileResponse, UserRole
from app.schemas.changes import (
    ChangeApprovalStatus,
    ChangeCategory,
    ChangeRiskLevel,
)
from app.services.change_engine import (
    detect_differences,
    evaluate_change,
)

# ---------------------------------------------------------------------------
# Test IDs & Fixtures
# ---------------------------------------------------------------------------

MACHINE_ID = UUID("cccccccc-0001-0001-0001-000000000001")
SESSION_ID = UUID("bbbbbbbb-0001-0001-0001-000000000001")
CHANGE_ID = UUID("dddddddd-0001-0001-0001-000000000001")
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


# ---------------------------------------------------------------------------
# 1. Engine: Expected Motor Change (3000 -> 3200)
# ---------------------------------------------------------------------------


def test_expected_motor_change_evaluation():
    """
    Expected motor change: 3000 -> 3200 RPM
    Must evaluate to:
      - is_expected = True (EXPECTED)
      - is_authorized = True (AUTHORIZED)
      - risk_level = LOW
      - requires_supervisor_approval = False
    """
    expected_changes = [
        {
            "category": "PARAMETERS",
            "parameter_name": "motor_speed_rpm",
            "from_value": 3000,
            "to_value": 3200,
            "reason": "Production cycle optimization",
        }
    ]
    res = evaluate_change(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        expected_changes=expected_changes,
        actor_role="MAINTENANCE_ENGINEER",
    )

    assert res.is_expected is True
    assert res.is_authorized is True
    assert res.risk_level == ChangeRiskLevel.LOW
    assert res.requires_supervisor_approval is False
    assert res.approval_status == ChangeApprovalStatus.AUTO_AUTHORIZED


# ---------------------------------------------------------------------------
# 2. Engine: Unexpected IP Change (192.168.10.20 -> 192.168.10.50)
# ---------------------------------------------------------------------------


def test_unexpected_ip_change_evaluation():
    """
    Unexpected IP change: 192.168.10.20 -> 192.168.10.50
    Must evaluate to:
      - is_expected = False (UNEXPECTED)
      - is_authorized = False (UNAUTHORIZED)
      - risk_level = HIGH (HIGH RISK)
      - requires_supervisor_approval = True
    """
    # Empty or parameter-only expected changes
    expected_changes = [
        {
            "category": "PARAMETERS",
            "parameter_name": "motor_speed_rpm",
            "from_value": 3000,
            "to_value": 3200,
        }
    ]
    res = evaluate_change(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        expected_changes=expected_changes,
        actor_role="MAINTENANCE_ENGINEER",
    )

    assert res.is_expected is False
    assert res.is_authorized is False
    assert res.risk_level == ChangeRiskLevel.HIGH
    assert res.requires_supervisor_approval is True
    assert res.approval_status == ChangeApprovalStatus.PENDING
    assert "UNAUTHORIZED" in res.authorization_notes.upper()
    assert "HIGH RISK" in res.authorization_notes.upper()


# ---------------------------------------------------------------------------
# 3. Engine: Safety PLC Modification (N7 Safety Interlock)
# ---------------------------------------------------------------------------


def test_safety_plc_modification_evaluation():
    """
    Safety PLC modification (e.g. N7 interlock modified or removed)
    Must evaluate to:
      - risk_level = CRITICAL
      - requires_supervisor_approval = True (SUPERVISOR REVIEW REQUIRED)
      - is_authorized = False
    """
    res = evaluate_change(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value="SAFETY_OK -> MACHINE_ENABLE",
        new_value="REMOVED",
        expected_changes=[],
        actor_role="MAINTENANCE_ENGINEER",
    )

    assert res.risk_level == ChangeRiskLevel.CRITICAL
    assert res.requires_supervisor_approval is True
    assert res.is_authorized is False
    assert res.risk_score >= 90
    assert "SUPERVISOR REVIEW REQUIRED" in res.authorization_notes.upper()


# ---------------------------------------------------------------------------
# 4. Engine: Safety Configuration Modification
# ---------------------------------------------------------------------------


def test_safety_config_modification_evaluation():
    """Safety configuration change must be CRITICAL and require supervisor approval."""
    res = evaluate_change(
        category=ChangeCategory.SAFETY_CONFIG,
        parameter_name="safety:interlocks_active",
        old_value=True,
        new_value=False,
        expected_changes=[],
        actor_role="MAINTENANCE_ENGINEER",
    )
    assert res.risk_level == ChangeRiskLevel.CRITICAL
    assert res.requires_supervisor_approval is True
    assert res.is_authorized is False


# ---------------------------------------------------------------------------
# 5. Engine: Unexpected Firmware & Firewall Modifications
# ---------------------------------------------------------------------------


def test_unexpected_firmware_modification_evaluation():
    res = evaluate_change(
        category=ChangeCategory.FIRMWARE,
        parameter_name="firmware",
        old_value="4.2.1",
        new_value="4.3.0",
        expected_changes=[],
        actor_role="MAINTENANCE_ENGINEER",
    )
    assert res.is_expected is False
    assert res.is_authorized is False
    assert res.risk_level == ChangeRiskLevel.HIGH
    assert res.requires_supervisor_approval is True


def test_unexpected_firewall_modification_evaluation():
    res = evaluate_change(
        category=ChangeCategory.FIREWALL,
        parameter_name="firewall_configuration",
        old_value={"default_policy": "DENY"},
        new_value={"default_policy": "ALLOW"},
        expected_changes=[],
        actor_role="MAINTENANCE_ENGINEER",
    )
    assert res.is_expected is False
    assert res.is_authorized is False
    assert res.risk_level == ChangeRiskLevel.HIGH
    assert res.requires_supervisor_approval is True


# ---------------------------------------------------------------------------
# 6. Deep Difference Detection across all 6 Categories
# ---------------------------------------------------------------------------


def test_detect_differences_all_six_categories():
    """Verify detect_differences identifies differences across all 6 categories."""
    baseline = {
        "parameters": {"motor_speed_rpm": 3000, "temp_limit": 80.0},
        "network": {"ip_address": "192.168.10.20", "subnet": "255.255.255.0", "gateway": "192.168.10.1"},
        "firewall_configuration": {"default_policy": "DENY"},
        "firmware": "4.2.1",
        "safety_configuration": {"interlocks_active": True},
        "plc_version": "v17",
    }
    current = {
        "parameters": {"motor_speed_rpm": 3200, "temp_limit": 80.0},        # PARAMETERS
        "network": {"ip_address": "192.168.10.50", "subnet": "255.255.255.0", "gateway": "192.168.10.1"}, # NETWORK
        "firewall_configuration": {"default_policy": "ALLOW"},              # FIREWALL
        "firmware": "4.3.0",                                                 # FIRMWARE
        "safety_configuration": {"interlocks_active": False},               # SAFETY_CONFIG
        "plc_version": "v18",                                                # PLC_LOGIC
    }
    expected_changes = [
        {"category": "PARAMETERS", "parameter_name": "motor_speed_rpm", "to_value": 3200},
        {"category": "PLC_LOGIC", "parameter_name": "plc_version", "to_value": "v18"},
    ]

    diffs = detect_differences(
        baseline_state=baseline,
        current_state=current,
        expected_changes=expected_changes,
        actor_role="MAINTENANCE_ENGINEER",
    )

    categories_detected = {d["category"] for d in diffs}
    expected_categories = {
        ChangeCategory.PARAMETERS,
        ChangeCategory.NETWORK,
        ChangeCategory.FIREWALL,
        ChangeCategory.FIRMWARE,
        ChangeCategory.SAFETY_CONFIG,
        ChangeCategory.PLC_LOGIC,
    }
    assert expected_categories == categories_detected

    # Motor is expected & authorized
    motor_diff = next(d for d in diffs if d["parameter_name"] == "motor_speed_rpm")
    assert motor_diff["eval"].is_expected is True
    assert motor_diff["eval"].is_authorized is True

    # IP is unexpected & unauthorized
    ip_diff = next(d for d in diffs if d["parameter_name"] == "ip_address")
    assert ip_diff["eval"].is_expected is False
    assert ip_diff["eval"].is_authorized is False
    assert ip_diff["eval"].risk_level == ChangeRiskLevel.HIGH

    # Safety is critical
    safety_diff = next(d for d in diffs if "safety" in d["parameter_name"])
    assert safety_diff["eval"].risk_level == ChangeRiskLevel.CRITICAL
    assert safety_diff["eval"].requires_supervisor_approval is True


# ---------------------------------------------------------------------------
# 7. Demo Endpoints
# ---------------------------------------------------------------------------


def test_api_demo_expected_motor(client):
    """GET /api/changes/demo/expected-motor must return EXPECTED, AUTHORIZED."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        res = client.get("/api/changes/demo/expected-motor", headers=_AUTH)

    assert res.status_code == 200
    data = res.json()
    assert data["is_expected"] is True
    assert data["is_authorized"] is True
    assert data["expected_status"] == "EXPECTED"
    assert data["authorization_status"] == "AUTHORIZED"
    assert data["risk_level"] == "LOW"


def test_api_demo_unexpected_ip(client):
    """GET /api/changes/demo/unexpected-ip must return UNEXPECTED, UNAUTHORIZED, HIGH RISK."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        res = client.get("/api/changes/demo/unexpected-ip", headers=_AUTH)

    assert res.status_code == 200
    data = res.json()
    assert data["is_expected"] is False
    assert data["is_authorized"] is False
    assert data["expected_status"] == "UNEXPECTED"
    assert data["authorization_status"] == "UNAUTHORIZED"
    assert data["risk_level"] == "HIGH"
    assert data["requires_supervisor_approval"] is True


def test_api_demo_safety_plc(client):
    """GET /api/changes/demo/safety-plc must return CRITICAL, SUPERVISOR REVIEW REQUIRED."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        res = client.get("/api/changes/demo/safety-plc", headers=_AUTH)

    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "CRITICAL"
    assert data["requires_supervisor_approval"] is True
    assert "SUPERVISOR REVIEW REQUIRED" in data["supervisor_review_requirement"]


# ---------------------------------------------------------------------------
# 8. RBAC & Authorization Enforcement
# ---------------------------------------------------------------------------


def test_api_changes_requires_auth(client):
    res = client.get("/api/changes")
    assert res.status_code in (401, 403)


def test_engineer_cannot_review_change(client):
    """Engineers are forbidden from reviewing/authorizing changes (403)."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        res = client.post(
            f"/api/changes/{CHANGE_ID}/review",
            headers=_AUTH,
            json={"approved": True, "notes": "Engineer self-approval attempt"},
        )
    assert res.status_code == 403


def test_auditor_cannot_record_change(client):
    """Auditors cannot submit changes (403)."""
    with _patch_auth(UserRole.AUDITOR):
        res = client.post(
            "/api/changes",
            headers=_AUTH,
            json={
                "session_id": str(SESSION_ID),
                "machine_id": str(MACHINE_ID),
                "category": "PARAMETERS",
                "parameter_name": "motor_speed_rpm",
                "old_value": 3000,
                "new_value": 3200,
                "reason": "Auditor modification attempt",
            },
        )
    assert res.status_code == 403


def test_supervisor_can_review_and_approve(client):
    """Supervisors can review and approve changes."""
    mock_change = {
        "id": str(CHANGE_ID),
        "session_id": str(SESSION_ID),
        "machine_id": str(MACHINE_ID),
        "user_id": str(ENGINEER_ID),
        "user_role": "MAINTENANCE_ENGINEER",
        "category": "NETWORK",
        "parameter_name": "ip_address",
        "old_value": "192.168.10.20",
        "new_value": "192.168.10.50",
        "reason": "VLAN reassignment",
        "is_expected": False,
        "is_authorized": True,
        "risk_score": 75,
        "risk_level": "HIGH",
        "requires_supervisor_approval": True,
        "approval_status": "APPROVED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    from app.schemas.changes import ChangeRecordResponse
    mock_resp = ChangeRecordResponse(**mock_change)

    with patch("app.api.changes.change_service.review_change", new=AsyncMock(return_value=mock_resp)):
        with _patch_auth(UserRole.SUPERVISOR):
            res = client.post(
                f"/api/changes/{CHANGE_ID}/review",
                headers=_AUTH,
                json={"approved": True, "notes": "Approved network modification after review."},
            )

    assert res.status_code == 200
    data = res.json()
    assert data["is_authorized"] is True
    assert data["approval_status"] == "APPROVED"


def test_admin_can_review_and_reject(client):
    """Admins can review and reject changes."""
    mock_change = {
        "id": str(CHANGE_ID),
        "session_id": str(SESSION_ID),
        "machine_id": str(MACHINE_ID),
        "user_id": str(ENGINEER_ID),
        "user_role": "MAINTENANCE_ENGINEER",
        "category": "NETWORK",
        "parameter_name": "ip_address",
        "old_value": "192.168.10.20",
        "new_value": "192.168.10.50",
        "reason": "Unauthorized reconfiguration",
        "is_expected": False,
        "is_authorized": False,
        "risk_score": 75,
        "risk_level": "HIGH",
        "requires_supervisor_approval": True,
        "approval_status": "REJECTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    from app.schemas.changes import ChangeRecordResponse
    mock_resp = ChangeRecordResponse(**mock_change)

    with patch("app.api.changes.change_service.review_change", new=AsyncMock(return_value=mock_resp)):
        with _patch_auth(UserRole.ADMIN):
            res = client.post(
                f"/api/changes/{CHANGE_ID}/review",
                headers=_AUTH,
                json={"approved": False, "notes": "Rejected by security policy."},
            )

    assert res.status_code == 200
    data = res.json()
    assert data["is_authorized"] is False
    assert data["approval_status"] == "REJECTED"
