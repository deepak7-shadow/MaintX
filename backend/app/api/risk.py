"""
Risk Evaluation & ML Anomaly API Router.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, require_engineer
from app.schemas.auth import UserProfileResponse
from app.schemas.changes import ChangeCategory
from app.schemas.risk import RiskAssessmentRequest, RiskAssessmentResponse
from app.services import risk_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["Deterministic Risk & ML Anomaly Engine"])


@router.post(
    "/evaluate",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate deterministic risk and ML anomaly score",
    description=(
        "Executes the authoritative deterministic risk scoring engine and calculates an advisory "
        "Isolation Forest anomaly score. Deterministic security rules are strictly un-overridable by AI."
    ),
)
async def evaluate_risk(
    body: RiskAssessmentRequest,
    current_user: UserProfileResponse = Depends(get_current_user),
) -> RiskAssessmentResponse:
    return await risk_service.evaluate_and_record_risk(request=body, actor=current_user)


@router.get(
    "/dashboard",
    summary="Dashboard risk visualization feed",
    description="Returns pre-computed and aggregated risk and ML anomaly metrics for the dashboard visualization.",
)
async def get_dashboard_data(
    machine_code: str = Query(default="CNC-01"),
    _: UserProfileResponse = Depends(get_current_user),
) -> Dict[str, Any]:
    return await risk_service.get_dashboard_risk_summary(machine_code=machine_code)


@router.get(
    "/demo/expected-motor",
    response_model=RiskAssessmentResponse,
    summary="Demo: Expected Motor Change (3000 -> 3200 RPM)",
)
async def demo_expected_motor(
    _: UserProfileResponse = Depends(get_current_user),
) -> RiskAssessmentResponse:
    req = RiskAssessmentRequest(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        is_expected=True,
        is_authorized=True,
    )
    return await risk_service.evaluate_and_record_risk(request=req)


@router.get(
    "/demo/unexpected-ip",
    response_model=RiskAssessmentResponse,
    summary="Demo: Unexpected IP Change (192.168.10.20 -> 192.168.10.50)",
)
async def demo_unexpected_ip(
    _: UserProfileResponse = Depends(get_current_user),
) -> RiskAssessmentResponse:
    req = RiskAssessmentRequest(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        is_expected=False,
        is_authorized=False,
    )
    return await risk_service.evaluate_and_record_risk(request=req)


@router.get(
    "/demo/safety-plc",
    response_model=RiskAssessmentResponse,
    summary="Demo: Safety PLC Modification (N7 Interlock Removed)",
)
async def demo_safety_plc(
    _: UserProfileResponse = Depends(get_current_user),
) -> RiskAssessmentResponse:
    req = RiskAssessmentRequest(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value="ACTIVE",
        new_value="REMOVED",
        is_expected=False,
        is_authorized=False,
    )
    return await risk_service.evaluate_and_record_risk(request=req)
