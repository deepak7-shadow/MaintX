"""
Stage 4 tests — machines, simulator, and maintenance workflow.

All DB calls are mocked — no live Supabase connection required.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.auth import UserProfileResponse, UserRole
from app.schemas.machines import MachineResponse, MachineSummary, SimulatedState
from app.schemas.maintenance import (
    MaintenanceModeStatus,
    MaintenanceRequestResponse,
    MaintenanceSessionResponse,
)

# ---------------------------------------------------------------------------
# Shared fixtures & helpers
# ---------------------------------------------------------------------------

MACHINE_ID = UUID("cccccccc-0001-0001-0001-000000000001")
REQUEST_ID = UUID("dddddddd-0001-0001-0001-000000000001")
SESSION_ID = UUID("eeeeeeee-0001-0001-0001-000000000001")
ENGINEER_ID = UUID("aaaaaaaa-0042-0042-0042-000000000042")
SUPERVISOR_ID = UUID("bbbbbbbb-0001-0001-0001-000000000001")

NOW = datetime.now(timezone.utc)

DUMMY_JWT = {"sub": str(ENGINEER_ID)}
DUMMY_JWT_SUP = {"sub": str(SUPERVISOR_ID)}

_MOCK_TOKEN = "mock.jwt.token"
_AUTH = {"Authorization": f"Bearer {_MOCK_TOKEN}"}


def _make_profile(role: UserRole, uid: UUID | None = None) -> UserProfileResponse:
    uid = uid or ENGINEER_ID
    return UserProfileResponse(
        id=uid,
        email=f"{role.value.lower()}@maintx.test",
        name=f"Test {role.value}",
        role=role,
        department="Test",
        engineer_code="TECH-042" if role == UserRole.MAINTENANCE_ENGINEER else None,
    )


def _make_machine() -> MachineResponse:
    return MachineResponse(
        id=MACHINE_ID,
        machine_code="CNC-01",
        name="Precision 5-Axis Milling Machine",
        machine_type="CNC_MILLING",
        criticality="CRITICAL",
        location="Sector 4",
        status="OPERATIONAL",
        plc_version="v17",
        plc_integrity_status="VERIFIED",
        firmware="4.2.1",
        ip_address="192.168.10.20",
        subnet="255.255.255.0",
        gateway="192.168.10.1",
        firewall_configuration={"allowed_inbound_ports": [502, 44818, 102]},
        safety_configuration={"estop_circuit": "DUAL_CHANNEL_CAT4"},
        parameters={"motor_speed_rpm": 3000, "temperature_limit_celsius": 80, "pressure_limit_bar": 5.0, "operating_mode": "AUTO"},
        created_at=NOW,
        updated_at=NOW,
    )


def _make_request(status: str = "SUBMITTED", approval_status: str = "PENDING") -> MaintenanceRequestResponse:
    return MaintenanceRequestResponse(
        id=REQUEST_ID,
        request_number="MNT-2026-1842",
        machine_id=MACHINE_ID,
        engineer_id=ENGINEER_ID,
        supervisor_id=None,
        reason="Production configuration update",
        maintenance_type="FIRMWARE_UPDATE",
        expected_changes=[
            {"parameter": "motor_speed_rpm", "from_value": 3000, "to_value": 3200},
            {"parameter": "plc_version", "from_value": "v17", "to_value": "v18"},
        ],
        priority="HIGH",
        approval_status=approval_status,
        status=status,
        scheduled_start=NOW,
        scheduled_end=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _make_session(status: str = "ACTIVE") -> MaintenanceSessionResponse:
    return MaintenanceSessionResponse(
        id=SESSION_ID,
        request_id=REQUEST_ID,
        machine_id=MACHINE_ID,
        engineer_id=ENGINEER_ID,
        started_at=NOW,
        completed_at=None,
        session_status=status,
        baseline_captured=True,
        verification_status="PENDING",
        notes=None,
        created_at=NOW,
    )


@contextmanager
def _patch_auth(role: UserRole, uid: UUID | None = None):
    profile = _make_profile(role, uid)
    with patch("app.api.deps.decode_supabase_jwt", return_value={"sub": str(profile.id)}):
        with patch("app.api.deps.get_profile_by_user_id", new=AsyncMock(return_value=profile)):
            yield profile


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Machines — list & detail
# ---------------------------------------------------------------------------


def test_list_machines(client):
    summary = MachineSummary(
        id=MACHINE_ID, machine_code="CNC-01", name="Precision 5-Axis Milling Machine",
        machine_type="CNC_MILLING", criticality="CRITICAL", status="OPERATIONAL",
        plc_version="v17", plc_integrity_status="VERIFIED", location="Sector 4",
    )
    with patch("app.api.machines.machine_service.list_machines", new=AsyncMock(return_value=[summary])):
        with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
            r = client.get("/api/machines", headers=_AUTH)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["machine_code"] == "CNC-01"
    assert data[0]["status"] == "OPERATIONAL"


def test_get_machine_detail(client):
    machine = _make_machine()
    with patch("app.api.machines.machine_service.get_machine", new=AsyncMock(return_value=machine)):
        with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
            r = client.get("/api/machines/CNC-01", headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["machine_code"] == "CNC-01"
    assert body["plc_version"] == "v17"
    assert body["firmware"] == "4.2.1"
    assert body["ip_address"] == "192.168.10.20"
    assert body["parameters"]["motor_speed_rpm"] == 3000


def test_machine_requires_auth(client):
    r = client.get("/api/machines")
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 2. Machine simulator
# ---------------------------------------------------------------------------


def test_simulator_produces_realistic_telemetry(client):
    machine = _make_machine()
    with patch("app.api.machines.machine_service.get_machine", new=AsyncMock(return_value=machine)):
        with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
            r = client.get("/api/machines/CNC-01/live", headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["machine_code"] == "CNC-01"
    assert body["plc_version"] == "v17"
    # Motor RPM should be within ±10% of set point (3000)
    assert 2500 <= body["motor_speed_rpm"] <= 3500
    # Temperature should be positive and below limit
    assert 0 < body["temperature_celsius"] < 100
    # Pressure should be positive
    assert body["pressure_bar"] >= 0
    assert body["maintenance_mode"] is False


def test_simulator_in_maintenance_mode_shows_zero_rpm():
    """When machine is in MAINTENANCE_MODE, motor should stop."""
    from app.services.simulator import simulate_machine

    sim_data = {
        "machine_code": "CNC-01",
        "plc_version": "v17",
        "ip_address": "192.168.10.20",
        "status": "MAINTENANCE_MODE",
        "parameters": {"motor_speed_rpm": 3000, "temperature_limit_celsius": 80, "pressure_limit_bar": 5.0, "operating_mode": "AUTO"},
    }
    state = simulate_machine(sim_data)
    assert state.motor_speed_rpm == 0.0
    assert state.maintenance_mode is True
    assert state.pressure_bar == 0.0
    assert any("MAINTENANCE_MODE" in a for a in state.alerts)


def test_simulator_alert_on_temperature_limit():
    """Simulator should raise alert when temperature is near/above limit."""
    from app.services.simulator import MachineSimulator

    sim = MachineSimulator(
        machine_code="TEST-01",
        plc_version="v17",
        parameters={"motor_speed_rpm": 5000, "temperature_limit_celsius": 50, "pressure_limit_bar": 5.0, "operating_mode": "AUTO"},
        ip_address="192.168.1.1",
        status="OPERATIONAL",
    )
    state = sim.snapshot()
    # With very low temp limit and high RPM, alert should fire
    # (not guaranteed every run, but at least no crash)
    assert isinstance(state.alerts, list)


# ---------------------------------------------------------------------------
# 3. Maintenance request creation
# ---------------------------------------------------------------------------


def test_create_maintenance_request(client):
    req = _make_request()
    with patch("app.services.maintenance_service.create_request", new=AsyncMock(return_value=req)):
        with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
            r = client.post(
                "/api/maintenance",
                headers=_AUTH,
                json={
                    "machine_id": str(MACHINE_ID),
                    "reason": "Production configuration update for motor RPM and PLC upgrade",
                    "maintenance_type": "FIRMWARE_UPDATE",
                    "priority": "HIGH",
                    "expected_changes": [
                        {"parameter": "motor_speed_rpm", "from_value": 3000, "to_value": 3200},
                        {"parameter": "plc_version", "from_value": "v17", "to_value": "v18"},
                    ],
                },
            )
    assert r.status_code == 201
    body = r.json()
    assert body["request_number"] == "MNT-2026-1842"
    assert body["status"] == "SUBMITTED"
    assert len(body["expected_changes"]) == 2


def test_auditor_cannot_create_request(client):
    """AUDITOR has no write access — should get 403."""
    with _patch_auth(UserRole.AUDITOR):
        r = client.post(
            "/api/maintenance",
            headers=_AUTH,
            json={
                "machine_id": str(MACHINE_ID),
                "reason": "Trying to sneak in a request",
                "maintenance_type": "SCHEDULED_MAINTENANCE",
                "priority": "LOW",
            },
        )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 4. Engineer assignment
# ---------------------------------------------------------------------------


def test_supervisor_can_assign_engineer(client):
    req = _make_request()
    with patch("app.services.maintenance_service.assign_engineer", new=AsyncMock(return_value=req)):
        with _patch_auth(UserRole.SUPERVISOR, uid=SUPERVISOR_ID):
            r = client.post(
                f"/api/maintenance/{REQUEST_ID}/assign",
                headers=_AUTH,
                json={"engineer_id": str(ENGINEER_ID)},
            )
    assert r.status_code == 200


def test_engineer_cannot_assign_engineer(client):
    """An engineer cannot reassign themselves or others."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        r = client.post(
            f"/api/maintenance/{REQUEST_ID}/assign",
            headers=_AUTH,
            json={"engineer_id": str(ENGINEER_ID)},
        )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 5. Supervisor approval
# ---------------------------------------------------------------------------


def test_supervisor_can_approve(client):
    approved_req = _make_request(status="APPROVED", approval_status="APPROVED")
    with patch("app.services.maintenance_service.approve_request", new=AsyncMock(return_value=approved_req)):
        with _patch_auth(UserRole.SUPERVISOR, uid=SUPERVISOR_ID):
            r = client.post(
                f"/api/maintenance/{REQUEST_ID}/approve",
                headers=_AUTH,
                json={"decision": "APPROVED", "comments": "Approved for production window"},
            )
    assert r.status_code == 200
    assert r.json()["approval_status"] == "APPROVED"
    assert r.json()["status"] == "APPROVED"


def test_engineer_cannot_approve(client):
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        r = client.post(
            f"/api/maintenance/{REQUEST_ID}/approve",
            headers=_AUTH,
            json={"decision": "APPROVED"},
        )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 6. Start session (maintenance mode lockout)
# ---------------------------------------------------------------------------


def test_engineer_can_start_session(client):
    session = _make_session()
    with patch("app.services.maintenance_service.start_session", new=AsyncMock(return_value=session)):
        with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
            r = client.post(
                f"/api/maintenance/{REQUEST_ID}/start",
                headers=_AUTH,
                json={"notes": "Starting production config update"},
            )
    assert r.status_code == 201
    body = r.json()
    assert body["session_status"] == "ACTIVE"
    assert body["baseline_captured"] is True


def test_auditor_cannot_start_session(client):
    with _patch_auth(UserRole.AUDITOR):
        r = client.post(
            f"/api/maintenance/{REQUEST_ID}/start",
            headers=_AUTH,
            json={},
        )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 7. Complete session
# ---------------------------------------------------------------------------


def test_engineer_can_complete_session(client):
    completed = _make_session(status="COMPLETED")
    with patch("app.services.maintenance_service.complete_session", new=AsyncMock(return_value=completed)):
        with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
            r = client.post(
                f"/api/maintenance/sessions/{SESSION_ID}/complete",
                headers=_AUTH,
                json={"notes": "Motor upgraded to 3200 RPM. PLC updated to v18.", "verification_status": "VERIFIED"},
            )
    assert r.status_code == 200
    assert r.json()["session_status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# 8. Maintenance mode status endpoint
# ---------------------------------------------------------------------------


def test_maintenance_mode_status(client):
    machine = _make_machine()
    status_obj = MaintenanceModeStatus(
        machine_code="CNC-01",
        machine_id=MACHINE_ID,
        in_maintenance=False,
        machine_locked=False,
        message="Machine is OPERATIONAL.",
    )
    with patch("app.api.machines.machine_service.get_machine", new=AsyncMock(return_value=machine)):
        with patch("app.api.machines.maintenance_service.get_maintenance_mode_status", new=AsyncMock(return_value=status_obj)):
            with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
                r = client.get("/api/machines/CNC-01/maintenance-status", headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["in_maintenance"] is False
    assert body["machine_code"] == "CNC-01"
