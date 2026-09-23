"""
Deterministic Risk Engine.

Authoritative rule-based risk evaluation system.
Computes a deterministic score (0–100) mapped to risk tiers:
  - LOW:      0–29
  - MEDIUM:  30–59
  - HIGH:    60–84
  - CRITICAL: 85–100

Always returns:
  - risk_score: int
  - risk_level: ChangeRiskLevel
  - risk_reasons: List[str]
  - scoring_breakdown: Dict[str, Any]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.changes import ChangeCategory, ChangeRiskLevel


@dataclass
class DeterministicRiskResult:
    risk_score: int
    risk_level: ChangeRiskLevel
    risk_reasons: List[str]
    scoring_breakdown: Dict[str, Any]


def calculate_deterministic_risk(
    category: ChangeCategory,
    parameter_name: str,
    old_value: Any,
    new_value: Any,
    is_expected: bool,
    is_authorized: bool,
    user_role: str = "MAINTENANCE_ENGINEER",
) -> DeterministicRiskResult:
    """
    Calculate deterministic risk score and reasons using the authoritative
    MaintX additive scoring system.
    """
    score = 0
    reasons: List[str] = []
    breakdown: Dict[str, Any] = {}

    param_lower = parameter_name.lower()
    is_safety_interlock = (
        category == ChangeCategory.PLC_LOGIC
        and ("n7" in param_lower or "safety" in param_lower or "interlock" in param_lower or "estop" in param_lower)
    )

    # -----------------------------------------------------------------------
    # 1. Base Category Scoring
    # -----------------------------------------------------------------------
    base_points = 0
    if category == ChangeCategory.SAFETY_CONFIG:
        base_points = 50
        reasons.append("Base category SAFETY_CONFIG (+50 pts): direct modification of industrial safety controls.")
    elif is_safety_interlock:
        base_points = 50
        reasons.append(f"Base category PLC_LOGIC Safety Interlock '{parameter_name}' (+50 pts): modifies safety gating logic.")
    elif category == ChangeCategory.NETWORK:
        base_points = 35
        reasons.append("Base category NETWORK (+35 pts): perimeter boundary or network address modification.")
    elif category == ChangeCategory.FIREWALL:
        base_points = 35
        reasons.append("Base category FIREWALL (+35 pts): modifies ingress/egress packet access controls.")
    elif category == ChangeCategory.FIRMWARE:
        base_points = 30
        reasons.append("Base category FIRMWARE (+30 pts): controller binary or bootloader update.")
    elif category == ChangeCategory.PLC_LOGIC:
        base_points = 20
        reasons.append("Base category PLC_LOGIC (+20 pts): standard ladder logic rung change.")
    else:  # PARAMETERS
        base_points = 15
        reasons.append("Base category PARAMETERS (+15 pts): machine operational setpoint change.")

    score += base_points
    breakdown["category_base_points"] = base_points

    # -----------------------------------------------------------------------
    # 2. Expectation Factor
    # -----------------------------------------------------------------------
    if not is_expected:
        score += 25
        reasons.append("Unexpected Change (+25 pts): modification was not requested or scheduled in maintenance plan.")
        breakdown["unexpected_penalty"] = 25
    else:
        reasons.append("Expected Change (+0 pts): planned within approved maintenance scope.")
        breakdown["unexpected_penalty"] = 0

    # -----------------------------------------------------------------------
    # 3. Authorization Factor
    # -----------------------------------------------------------------------
    if not is_authorized:
        score += 20
        reasons.append("Unauthorized (+20 pts): change has not received required supervisor authorization.")
        breakdown["unauthorized_penalty"] = 20
    else:
        score = max(0, score - 10)
        reasons.append("Authorized (-10 pts): validated against approved supervisor work order.")
        breakdown["authorization_credit"] = -10

    # -----------------------------------------------------------------------
    # 4. Magnitude & Configuration Specific Factors
    # -----------------------------------------------------------------------
    magnitude_pts = 0
    if category == ChangeCategory.PARAMETERS:
        try:
            old_num = float(old_value)
            new_num = float(new_value)
            pct_delta = abs(new_num - old_num) / (abs(old_num) or 1.0)
            if pct_delta > 0.25:
                magnitude_pts = 15
                reasons.append(f"Significant Parameter Shift (+15 pts): {pct_delta:.1%} deviation exceeds 25% threshold.")
            elif pct_delta > 0.10:
                magnitude_pts = 5
                reasons.append(f"Moderate Parameter Shift (+5 pts): {pct_delta:.1%} deviation.")
        except (ValueError, TypeError):
            pass

    elif category == ChangeCategory.FIREWALL:
        # Check if default policy changed to ALLOW or rule opened
        if isinstance(new_value, dict) and new_value.get("default_policy") == "ALLOW":
            magnitude_pts = 20
            reasons.append("Insecure Firewall Policy (+20 pts): default action set to permissive ALLOW.")

    score += magnitude_pts
    breakdown["magnitude_points"] = magnitude_pts

    # -----------------------------------------------------------------------
    # 5. Deterministic Security Rules & Floors
    #    (Deterministic rules CANNOT be relaxed by ML)
    # -----------------------------------------------------------------------
    # Rule A: Safety Interlock Bypass (N7) is guaranteed CRITICAL (>= 95)
    if is_safety_interlock and (not is_authorized or not is_expected or "remove" in str(new_value).lower()):
        if score < 95:
            score = 95
        reasons.append("MANDATORY RULE ENFORCEMENT: Safety interlock (N7) modification clamped to CRITICAL (score >= 95).")
        breakdown["safety_interlock_floor"] = 95

    # Rule B: Safety Config modification is guaranteed CRITICAL (>= 85)
    elif category == ChangeCategory.SAFETY_CONFIG and not is_authorized:
        if score < 85:
            score = 85
        reasons.append("MANDATORY RULE ENFORCEMENT: Unauthorized safety configuration change clamped to CRITICAL (score >= 85).")
        breakdown["safety_config_floor"] = 85

    # Rule C: Unexpected Network / IP modification is guaranteed HIGH (>= 70)
    elif category == ChangeCategory.NETWORK and not is_expected:
        if score < 75:
            score = 75
        reasons.append("MANDATORY RULE ENFORCEMENT: Unexpected IP/network change clamped to HIGH RISK (score >= 75).")
        breakdown["network_perimeter_floor"] = 75

    # Rule D: Expected, authorized operational parameter change within envelope (<= 25)
    elif category == ChangeCategory.PARAMETERS and is_expected and is_authorized:
        score = min(score, 20)
        reasons.append("MANDATORY RULE ENFORCEMENT: Pre-authorized parameter change capped at LOW RISK (score <= 20).")
        breakdown["authorized_envelope_cap"] = 20

    # Clamp total score to [0, 100]
    final_score = max(0, min(100, int(score)))

    # Determine risk level from authoritative bands
    if final_score >= 85:
        risk_level = ChangeRiskLevel.CRITICAL
    elif final_score >= 60:
        risk_level = ChangeRiskLevel.HIGH
    elif final_score >= 30:
        risk_level = ChangeRiskLevel.MEDIUM
    else:
        risk_level = ChangeRiskLevel.LOW

    breakdown["final_score"] = final_score
    breakdown["risk_level"] = risk_level.value

    return DeterministicRiskResult(
        risk_score=final_score,
        risk_level=risk_level,
        risk_reasons=reasons,
        scoring_breakdown=breakdown,
    )
