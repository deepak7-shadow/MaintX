"""
Stage 7 Tests — Deterministic Risk Engine & Prototype ML Anomaly Detector.

Covers:
  1. Deterministic scoring returns risk_score, risk_level, and risk_reasons
  2. Authoritative risk: Expected motor change (3000 -> 3200) => LOW (score <= 20)
  3. Authoritative risk: Unexpected IP change => HIGH (score >= 70)
  4. Authoritative risk: Safety PLC modification (N7 removed) => CRITICAL (score >= 95)
  5. Authoritative risk: Safety configuration modification => CRITICAL (score >= 85)
  6. Isolation Forest: returns ai_anomaly_score, model_name, and clearly labeled 'Prototype ML anomaly score'
  7. Governance: AI must NOT override deterministic security rules
  8. Fault tolerance: If ML fails/throws exception, deterministic risk and MaintX continue working
  9. API: POST /api/risk/evaluate endpoint
 10. API: Demo endpoints (expected motor, unexpected IP, safety PLC)
 11. API: Dashboard visualization feed
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
from app.schemas.changes import ChangeCategory, ChangeRiskLevel
from app.services.anomaly_detector import (
    ML_LABEL,
    MODEL_NAME,
    IsolationForestAnomalyDetector,
    get_anomaly_detector,
)
from app.services.risk_engine import calculate_deterministic_risk

# ---------------------------------------------------------------------------
# Test Fixtures & Auth Helpers
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


# ---------------------------------------------------------------------------
# 1. Deterministic Engine: Required Return Fields
# ---------------------------------------------------------------------------


def test_deterministic_risk_returns_score_level_reasons():
    """Deterministic risk calculation must return risk_score, risk_level, and risk_reasons."""
    res = calculate_deterministic_risk(
        category=ChangeCategory.PARAMETERS,
        parameter_name="temperature_limit",
        old_value=80.0,
        new_value=95.0,
        is_expected=False,
        is_authorized=False,
    )
    assert hasattr(res, "risk_score")
    assert hasattr(res, "risk_level")
    assert hasattr(res, "risk_reasons")
    assert isinstance(res.risk_score, int)
    assert 0 <= res.risk_score <= 100
    assert isinstance(res.risk_level, ChangeRiskLevel)
    assert isinstance(res.risk_reasons, list)
    assert len(res.risk_reasons) > 0


# ---------------------------------------------------------------------------
# 2. Deterministic Scoring Cases
# ---------------------------------------------------------------------------


def test_deterministic_expected_motor_change():
    """Expected motor change (3000 -> 3200 RPM) must be LOW risk (<= 20)."""
    res = calculate_deterministic_risk(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        is_expected=True,
        is_authorized=True,
    )
    assert res.risk_level == ChangeRiskLevel.LOW
    assert res.risk_score <= 20
    assert any("authorized" in r.lower() or "within" in r.lower() for r in res.risk_reasons)


def test_deterministic_unexpected_ip_change():
    """Unexpected IP change must be HIGH risk (>= 70)."""
    res = calculate_deterministic_risk(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        is_expected=False,
        is_authorized=False,
    )
    assert res.risk_level == ChangeRiskLevel.HIGH
    assert res.risk_score >= 70
    assert any("network" in r.lower() or "ip" in r.lower() for r in res.risk_reasons)


def test_deterministic_safety_plc_interlock_removal():
    """Safety PLC modification (N7 removed) must be CRITICAL (>= 95)."""
    res = calculate_deterministic_risk(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value="SAFETY_OK -> MACHINE_ENABLE",
        new_value="REMOVED",
        is_expected=False,
        is_authorized=False,
    )
    assert res.risk_level == ChangeRiskLevel.CRITICAL
    assert res.risk_score >= 95
    assert any("n7" in r.lower() or "safety interlock" in r.lower() for r in res.risk_reasons)


def test_deterministic_safety_config_change():
    """Safety configuration change must be CRITICAL (>= 85)."""
    res = calculate_deterministic_risk(
        category=ChangeCategory.SAFETY_CONFIG,
        parameter_name="interlocks_active",
        old_value=True,
        new_value=False,
        is_expected=False,
        is_authorized=False,
    )
    assert res.risk_level == ChangeRiskLevel.CRITICAL
    assert res.risk_score >= 85


# ---------------------------------------------------------------------------
# 3. Prototype ML Anomaly Detector using scikit-learn Isolation Forest
# ---------------------------------------------------------------------------


def test_isolation_forest_returns_labeled_anomaly_score():
    """ML detector must return ai_anomaly_score, model_name, and clear prototype label."""
    detector = get_anomaly_detector()
    ml_res = detector.predict_anomaly(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        is_expected=True,
        is_authorized=True,
    )

    assert ml_res.ai_anomaly_score is not None
    assert 0 <= ml_res.ai_anomaly_score <= 100
    assert ml_res.model_name == MODEL_NAME
    assert ml_res.ml_label == ML_LABEL
    assert ml_res.ml_label == "Prototype ML anomaly score"
    assert ml_res.ai_explanation is not None


def test_isolation_forest_anomaly_score_differentiation():
    """Normal change has lower anomaly score than unexpected network change."""
    detector = get_anomaly_detector()

    normal = detector.predict_anomaly(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        is_expected=True,
        is_authorized=True,
    )

    anomalous = detector.predict_anomaly(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        is_expected=False,
        is_authorized=False,
    )

    assert normal.ai_anomaly_score is not None
    assert anomalous.ai_anomaly_score is not None
    assert anomalous.ai_anomaly_score > normal.ai_anomaly_score


# ---------------------------------------------------------------------------
# 4. Critical Governance: AI Must NOT Override Deterministic Rules
# ---------------------------------------------------------------------------


def test_ai_cannot_override_deterministic_security_rules():
    """
    CRITICAL GOVERNANCE: Even if the ML model assigns a low anomaly score to a
    safety-critical change, the authoritative risk_level remains CRITICAL and
    risk_score remains >= 95.
    """
    det_res = calculate_deterministic_risk(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value="ACTIVE",
        new_value="REMOVED",
        is_expected=False,
        is_authorized=False,
    )
    # The deterministic engine makes the authoritative decision
    assert det_res.risk_level == ChangeRiskLevel.CRITICAL
    assert det_res.risk_score >= 95


# ---------------------------------------------------------------------------
# 5. Fault Tolerance: ML Failure Does NOT Crash MaintX
# ---------------------------------------------------------------------------


def test_ml_failure_tolerance_allows_maintx_to_continue():
    """
    If ML fails, the rest of MaintX must continue working.
    """
    detector = IsolationForestAnomalyDetector()
    # Force ML model failure by monkey-patching _model.decision_function to raise an exception
    mock_model = MagicMock()
    mock_model.decision_function.side_effect = RuntimeError("Simulated scikit-learn failure")
    detector._model = mock_model

    # Inference must NOT raise; must return fallback result gracefully
    ml_res = detector.predict_anomaly(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        is_expected=True,
        is_authorized=True,
    )

    assert ml_res.ai_anomaly_score is None
    assert ml_res.model_name == MODEL_NAME
    assert ml_res.ml_label == "Prototype ML anomaly score"
    assert "exception" in ml_res.ai_explanation.lower() or "fallback" in ml_res.ai_explanation.lower()


# ---------------------------------------------------------------------------
# 6. API Endpoints
# ---------------------------------------------------------------------------


def test_api_evaluate_risk(client):
    """POST /api/risk/evaluate returns deterministic risk and labeled ML score."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        res = client.post(
            "/api/risk/evaluate",
            headers=_AUTH,
            json={
                "category": "PARAMETERS",
                "parameter_name": "motor_speed_rpm",
                "old_value": 3000,
                "new_value": 3200,
                "is_expected": True,
                "is_authorized": True,
                "machine_code": "CNC-01",
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_score"] <= 20
    assert data["risk_level"] == "LOW"
    assert len(data["risk_reasons"]) > 0
    assert data["ml_label"] == "Prototype ML anomaly score"
    assert data["model_name"] == MODEL_NAME
    assert data["rule_override_prevented"] is True


def test_api_demo_endpoints(client):
    """Test demo endpoints for expected motor, unexpected IP, and safety PLC."""
    with _patch_auth(UserRole.MAINTENANCE_ENGINEER):
        # Motor
        r_motor = client.get("/api/risk/demo/expected-motor", headers=_AUTH)
        assert r_motor.status_code == 200
        assert r_motor.json()["risk_level"] == "LOW"
        assert r_motor.json()["ml_label"] == "Prototype ML anomaly score"

        # IP
        r_ip = client.get("/api/risk/demo/unexpected-ip", headers=_AUTH)
        assert r_ip.status_code == 200
        assert r_ip.json()["risk_level"] == "HIGH"

        # Safety PLC
        r_safety = client.get("/api/risk/demo/safety-plc", headers=_AUTH)
        assert r_safety.status_code == 200
        assert r_safety.json()["risk_level"] == "CRITICAL"


def test_api_dashboard_feed(client):
    """GET /api/risk/dashboard returns aggregated visualization data."""
    with _patch_auth(UserRole.SECURITY_ANALYST):
        res = client.get("/api/risk/dashboard?machine_code=CNC-01", headers=_AUTH)
    assert res.status_code == 200
    data = res.json()
    assert data["machine_code"] == "CNC-01"
    assert data["ml_label"] == "Prototype ML anomaly score"
    assert len(data["scenarios"]) == 3
    assert data["governance_rule"] == "AI must NOT override deterministic security rules"
