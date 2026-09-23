"""
Risk service — orchestrates deterministic risk evaluation, prototype ML anomaly scoring,
database storage, and dashboard analytics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.db.client import get_supabase_client
from app.schemas.auth import UserProfileResponse
from app.schemas.changes import ChangeCategory, ChangeRiskLevel
from app.schemas.risk import RiskAssessmentRequest, RiskAssessmentResponse
from app.services.anomaly_detector import get_anomaly_detector
from app.services.risk_engine import calculate_deterministic_risk

logger = logging.getLogger(__name__)


async def evaluate_and_record_risk(
    request: RiskAssessmentRequest,
    actor: Optional[UserProfileResponse] = None,
) -> RiskAssessmentResponse:
    """
    Evaluate deterministic risk score (authoritative) and calculate advisory
    Isolation Forest anomaly score.
    Persists the assessment into `risk_assessments` and updates `configuration_changes`.
    """
    user_role = actor.role.value if actor else request.user_role

    # 1. Deterministic Rule-Based Risk (Authoritative)
    det_res = calculate_deterministic_risk(
        category=request.category,
        parameter_name=request.parameter_name,
        old_value=request.old_value,
        new_value=request.new_value,
        is_expected=request.is_expected,
        is_authorized=request.is_authorized,
        user_role=user_role,
    )

    # 2. Prototype ML Anomaly Detector (Advisory Only)
    # Guaranteed non-crashing — if ML fails, deterministic risk still functions
    detector = get_anomaly_detector()
    ml_res = detector.predict_anomaly(
        category=request.category,
        parameter_name=request.parameter_name,
        old_value=request.old_value,
        new_value=request.new_value,
        is_expected=request.is_expected,
        is_authorized=request.is_authorized,
        user_role=user_role,
    )

    now = datetime.now(timezone.utc)

    # 3. Persist to DB if change_id or session_id provided
    try:
        client = get_supabase_client()
        db_payload: Dict[str, Any] = {
            "calculated_score": det_res.risk_score,
            "risk_level": det_res.risk_level.value,
            "scoring_breakdown": det_res.scoring_breakdown,
            "ai_anomaly_score": ml_res.ai_anomaly_score,
            "ai_explanation": ml_res.ai_explanation,
            "engine_version": "1.0.0-deterministic+ML-prototype",
        }
        if request.change_id:
            db_payload["change_id"] = str(request.change_id)
        if request.session_id:
            db_payload["session_id"] = str(request.session_id)

        client.table("risk_assessments").insert(db_payload).execute()

        # Also update ai_anomaly_score on configuration_changes if change_id provided
        if request.change_id and ml_res.ai_anomaly_score is not None:
            client.table("configuration_changes").update({
                "ai_anomaly_score": ml_res.ai_anomaly_score,
            }).eq("id", str(request.change_id)).execute()

    except Exception as exc:
        logger.warning("Could not persist risk assessment to Supabase: %s", exc)

    return RiskAssessmentResponse(
        risk_score=det_res.risk_score,
        risk_level=det_res.risk_level,
        risk_reasons=det_res.risk_reasons,
        scoring_breakdown=det_res.scoring_breakdown,
        ai_anomaly_score=ml_res.ai_anomaly_score,
        model_name=ml_res.model_name,
        ml_label=ml_res.ml_label,
        ai_explanation=ml_res.ai_explanation,
        evaluated_at=now,
        rule_override_prevented=True,
    )


async def get_dashboard_risk_summary(machine_code: str = "CNC-01") -> Dict[str, Any]:
    """
    Provide aggregated statistics and live demo data for dashboard visualization.
    """
    # Evaluate 3 canonical demo changes
    exp_motor = calculate_deterministic_risk(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        is_expected=True,
        is_authorized=True,
    )
    detector = get_anomaly_detector()
    ml_motor = detector.predict_anomaly(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        is_expected=True,
        is_authorized=True,
    )

    unexp_ip = calculate_deterministic_risk(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        is_expected=False,
        is_authorized=False,
    )
    ml_ip = detector.predict_anomaly(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        is_expected=False,
        is_authorized=False,
    )

    safety_plc = calculate_deterministic_risk(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value="ACTIVE",
        new_value="REMOVED",
        is_expected=False,
        is_authorized=False,
    )
    ml_safety = detector.predict_anomaly(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value="ACTIVE",
        new_value="REMOVED",
        is_expected=False,
        is_authorized=False,
    )

    return {
        "machine_code": machine_code,
        "engine": "Deterministic Risk Engine v1.0",
        "ml_assistant": "scikit-learn Isolation Forest (Prototype)",
        "ml_label": "Prototype ML anomaly score",
        "governance_rule": "AI must NOT override deterministic security rules",
        "scenarios": [
            {
                "id": "motor",
                "title": "Expected Motor Speed Adjustment (3000 -> 3200 RPM)",
                "category": "PARAMETERS",
                "risk_score": exp_motor.risk_score,
                "risk_level": exp_motor.risk_level.value,
                "risk_reasons": exp_motor.risk_reasons,
                "ai_anomaly_score": ml_motor.ai_anomaly_score,
                "model_name": ml_motor.model_name,
                "ml_label": ml_motor.ml_label,
                "ai_explanation": ml_motor.ai_explanation,
            },
            {
                "id": "ip",
                "title": "Unexpected Network IP Change (192.168.10.20 -> 192.168.10.50)",
                "category": "NETWORK",
                "risk_score": unexp_ip.risk_score,
                "risk_level": unexp_ip.risk_level.value,
                "risk_reasons": unexp_ip.risk_reasons,
                "ai_anomaly_score": ml_ip.ai_anomaly_score,
                "model_name": ml_ip.model_name,
                "ml_label": ml_ip.ml_label,
                "ai_explanation": ml_ip.ai_explanation,
            },
            {
                "id": "safety",
                "title": "Safety PLC Modification (N7 Interlock Removed)",
                "category": "PLC_LOGIC",
                "risk_score": safety_plc.risk_score,
                "risk_level": safety_plc.risk_level.value,
                "risk_reasons": safety_plc.risk_reasons,
                "ai_anomaly_score": ml_safety.ai_anomaly_score,
                "model_name": ml_safety.model_name,
                "ml_label": ml_safety.ml_label,
                "ai_explanation": ml_safety.ai_explanation,
            },
        ],
    }
