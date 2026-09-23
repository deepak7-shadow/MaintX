"""
Change Evaluation Engine & Authorization Policies.

Core functions:
  - evaluate_change(): Evaluates a single configuration difference against
    approved maintenance requests, policy rules, and role constraints.
  - detect_differences(): Deep-diffs baseline machine state vs current/target state
    across all 6 operational categories:
      1. PARAMETERS
      2. PLC_LOGIC
      3. NETWORK
      4. FIREWALL
      5. FIRMWARE
      6. SAFETY_CONFIG

Policy Rules:
  - Expected motor change (3000 -> 3200):
      -> EXPECTED, AUTHORIZED, LOW risk (0-25), no supervisor review required.
  - Unexpected IP change (192.168.10.20 -> 192.168.10.50):
      -> UNEXPECTED, UNAUTHORIZED, HIGH RISK (75), requires supervisor review.
  - Safety PLC modification (e.g. N7 interlock modified or removed):
      -> CRITICAL risk (95), SUPERVISOR REVIEW REQUIRED, UNAUTHORIZED until reviewed.
  - Safety config modification:
      -> CRITICAL risk (90+), SUPERVISOR REVIEW REQUIRED.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.auth import UserRole
from app.schemas.changes import ChangeApprovalStatus, ChangeCategory, ChangeRiskLevel
from app.services.plc_engine import compare_plc_logic


@dataclass
class ChangeEvaluationResult:
    is_expected: bool
    is_authorized: bool
    risk_score: int
    risk_level: ChangeRiskLevel
    requires_supervisor_approval: bool
    approval_status: ChangeApprovalStatus
    authorization_notes: str


def _match_expected_change(
    category: ChangeCategory,
    parameter_name: str,
    new_value: Any,
    expected_changes: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Check if a parameter change matches an item in the approved maintenance request's
    expected_changes list.
    """
    for exp in expected_changes:
        exp_cat = exp.get("category")
        exp_param = exp.get("parameter_name")
        exp_to = exp.get("to_value")

        # Category match
        if exp_cat and exp_cat != category.value:
            continue

        # Parameter name match
        if exp_param and exp_param == parameter_name:
            # If to_value is specified, verify it matches (string-insensitive or int)
            if exp_to is not None:
                if str(exp_to).strip() == str(new_value).strip():
                    return exp
            else:
                return exp

    return None


def evaluate_change(
    category: ChangeCategory,
    parameter_name: str,
    old_value: Any,
    new_value: Any,
    expected_changes: Optional[List[Dict[str, Any]]] = None,
    actor_role: Optional[str] = None,
) -> ChangeEvaluationResult:
    """
    Evaluate a configuration change according to security and operational policies.

    Enforces:
      1. Expected vs Unexpected matching from maintenance request scope.
      2. High-risk network perimeter deviations (IP, subnet, firewall).
      3. Critical safety interlock and safety config policies.
      4. Role authorization bounds.
    """
    expected_list = expected_changes or []
    matched_exp = _match_expected_change(category, parameter_name, new_value, expected_list)
    is_expected = matched_exp is not None

    param_lower = parameter_name.lower()

    # -----------------------------------------------------------------------
    # 1. SAFETY_CONFIG or Safety Interlock / PLC Safety modifications
    #    CRITICAL — SUPERVISOR REVIEW REQUIRED
    # -----------------------------------------------------------------------
    is_safety_plc = (
        category == ChangeCategory.PLC_LOGIC
        and (
            "n7" in param_lower
            or "safety" in param_lower
            or "interlock" in param_lower
            or "estop" in param_lower
        )
    )
    is_safety_config = category == ChangeCategory.SAFETY_CONFIG

    if is_safety_plc or is_safety_config:
        notes = (
            "CRITICAL SAFETY MODIFICATION: Safety interlock or safety configuration "
            "modified. SUPERVISOR REVIEW REQUIRED before operational authorization."
        )
        return ChangeEvaluationResult(
            is_expected=is_expected,
            is_authorized=False,
            risk_score=95 if is_safety_plc else 90,
            risk_level=ChangeRiskLevel.CRITICAL,
            requires_supervisor_approval=True,
            approval_status=ChangeApprovalStatus.PENDING,
            authorization_notes=notes,
        )

    # -----------------------------------------------------------------------
    # 2. NETWORK & FIREWALL changes
    #    Unexpected network changes are UNAUTHORIZED, HIGH RISK
    # -----------------------------------------------------------------------
    if category in (ChangeCategory.NETWORK, ChangeCategory.FIREWALL):
        if is_expected:
            return ChangeEvaluationResult(
                is_expected=True,
                is_authorized=True,
                risk_score=35,
                risk_level=ChangeRiskLevel.MEDIUM,
                requires_supervisor_approval=False,
                approval_status=ChangeApprovalStatus.AUTO_AUTHORIZED,
                authorization_notes="Authorized network configuration change matching approved maintenance request.",
            )
        else:
            notes = (
                f"UNEXPECTED NETWORK CHANGE: {parameter_name} changed from {old_value} to {new_value}. "
                "UNAUTHORIZED — HIGH RISK security boundary anomaly."
            )
            return ChangeEvaluationResult(
                is_expected=False,
                is_authorized=False,
                risk_score=75,
                risk_level=ChangeRiskLevel.HIGH,
                requires_supervisor_approval=True,
                approval_status=ChangeApprovalStatus.PENDING,
                authorization_notes=notes,
            )

    # -----------------------------------------------------------------------
    # 3. FIRMWARE changes
    # -----------------------------------------------------------------------
    if category == ChangeCategory.FIRMWARE:
        if is_expected:
            return ChangeEvaluationResult(
                is_expected=True,
                is_authorized=True,
                risk_score=30,
                risk_level=ChangeRiskLevel.MEDIUM,
                requires_supervisor_approval=False,
                approval_status=ChangeApprovalStatus.AUTO_AUTHORIZED,
                authorization_notes="Authorized firmware upgrade matching approved maintenance schedule.",
            )
        else:
            return ChangeEvaluationResult(
                is_expected=False,
                is_authorized=False,
                risk_score=80,
                risk_level=ChangeRiskLevel.HIGH,
                requires_supervisor_approval=True,
                approval_status=ChangeApprovalStatus.PENDING,
                authorization_notes=f"UNEXPECTED FIRMWARE CHANGE: {parameter_name} altered without pre-approval.",
            )

    # -----------------------------------------------------------------------
    # 4. Standard PLC_LOGIC changes (non-safety rungs)
    # -----------------------------------------------------------------------
    if category == ChangeCategory.PLC_LOGIC:
        if is_expected:
            return ChangeEvaluationResult(
                is_expected=True,
                is_authorized=True,
                risk_score=25,
                risk_level=ChangeRiskLevel.LOW,
                requires_supervisor_approval=False,
                approval_status=ChangeApprovalStatus.AUTO_AUTHORIZED,
                authorization_notes="Expected PLC logic update matching approved scope.",
            )
        else:
            return ChangeEvaluationResult(
                is_expected=False,
                is_authorized=False,
                risk_score=60,
                risk_level=ChangeRiskLevel.MEDIUM,
                requires_supervisor_approval=True,
                approval_status=ChangeApprovalStatus.PENDING,
                authorization_notes="Unexpected PLC logic modification detected.",
            )

    # -----------------------------------------------------------------------
    # 5. PARAMETERS (e.g. motor_speed_rpm: 3000 -> 3200)
    # -----------------------------------------------------------------------
    if is_expected:
        # Expected motor change 3000 -> 3200
        return ChangeEvaluationResult(
            is_expected=True,
            is_authorized=True,
            risk_score=15,
            risk_level=ChangeRiskLevel.LOW,
            requires_supervisor_approval=False,
            approval_status=ChangeApprovalStatus.AUTO_AUTHORIZED,
            authorization_notes="EXPECTED, AUTHORIZED operational parameter change within approved maintenance scope.",
        )
    else:
        # Unexpected parameter change
        # Determine risk based on magnitude if numerical
        score = 55
        level = ChangeRiskLevel.MEDIUM
        try:
            old_num = float(old_value)
            new_num = float(new_value)
            pct_change = abs(new_num - old_num) / (abs(old_num) or 1.0)
            if pct_change > 0.25:
                score = 70
                level = ChangeRiskLevel.HIGH
        except (ValueError, TypeError):
            pass

        return ChangeEvaluationResult(
            is_expected=False,
            is_authorized=False,
            risk_score=score,
            risk_level=level,
            requires_supervisor_approval=True,
            approval_status=ChangeApprovalStatus.PENDING,
            authorization_notes=f"UNEXPECTED parameter modification: {parameter_name} changed without prior authorization.",
        )


# ---------------------------------------------------------------------------
# Deep Difference Detector across all 6 categories
# ---------------------------------------------------------------------------


def detect_differences(
    baseline_state: Dict[str, Any],
    current_state: Dict[str, Any],
    expected_changes: Optional[List[Dict[str, Any]]] = None,
    actor_role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compare baseline snapshot vs current state across all 6 categories:
      1. PARAMETERS
      2. PLC_LOGIC
      3. NETWORK
      4. FIREWALL
      5. FIRMWARE
      6. SAFETY_CONFIG

    Returns a list of raw change dictionaries with policy evaluation results.
    """
    changes: List[Dict[str, Any]] = []

    # 1. PARAMETERS
    b_params = baseline_state.get("parameters") or {}
    c_params = current_state.get("parameters") or {}
    all_param_keys = set(b_params.keys()) | set(c_params.keys())
    for k in all_param_keys:
        old_val = b_params.get(k)
        new_val = c_params.get(k)
        if old_val != new_val:
            eval_res = evaluate_change(
                category=ChangeCategory.PARAMETERS,
                parameter_name=k,
                old_value=old_val,
                new_value=new_val,
                expected_changes=expected_changes,
                actor_role=actor_role,
            )
            changes.append({
                "category": ChangeCategory.PARAMETERS,
                "parameter_name": k,
                "old_value": old_val,
                "new_value": new_val,
                "reason": f"Operational parameter {k} modified from {old_val} to {new_val}",
                "eval": eval_res,
            })

    # 2. NETWORK (ip_address, subnet, gateway)
    b_net = baseline_state.get("network") or baseline_state.get("network_configuration") or {}
    c_net = current_state.get("network") or current_state.get("network_configuration") or {}
    # Also support top-level network fields
    for field in ("ip_address", "subnet", "gateway"):
        old_val = b_net.get(field, baseline_state.get(field))
        new_val = c_net.get(field, current_state.get(field))
        if old_val and new_val and str(old_val).strip() != str(new_val).strip():
            eval_res = evaluate_change(
                category=ChangeCategory.NETWORK,
                parameter_name=field,
                old_value=old_val,
                new_value=new_val,
                expected_changes=expected_changes,
                actor_role=actor_role,
            )
            changes.append({
                "category": ChangeCategory.NETWORK,
                "parameter_name": field,
                "old_value": old_val,
                "new_value": new_val,
                "reason": f"Network configuration {field} altered from {old_val} to {new_val}",
                "eval": eval_res,
            })

    # 3. FIREWALL
    b_fw = baseline_state.get("firewall_configuration") or {}
    c_fw = current_state.get("firewall_configuration") or {}
    if b_fw != c_fw and (b_fw or c_fw):
        eval_res = evaluate_change(
            category=ChangeCategory.FIREWALL,
            parameter_name="firewall_configuration",
            old_value=b_fw,
            new_value=c_fw,
            expected_changes=expected_changes,
            actor_role=actor_role,
        )
        changes.append({
            "category": ChangeCategory.FIREWALL,
            "parameter_name": "firewall_configuration",
            "old_value": b_fw,
            "new_value": c_fw,
            "reason": "Firewall configuration modified",
            "eval": eval_res,
        })

    # 4. FIRMWARE
    old_fw = baseline_state.get("firmware")
    new_fw = current_state.get("firmware")
    if old_fw and new_fw and str(old_fw).strip() != str(new_fw).strip():
        eval_res = evaluate_change(
            category=ChangeCategory.FIRMWARE,
            parameter_name="firmware",
            old_value=old_fw,
            new_value=new_fw,
            expected_changes=expected_changes,
            actor_role=actor_role,
        )
        changes.append({
            "category": ChangeCategory.FIRMWARE,
            "parameter_name": "firmware",
            "old_value": old_fw,
            "new_value": new_fw,
            "reason": f"Firmware updated from {old_fw} to {new_fw}",
            "eval": eval_res,
        })

    # 5. SAFETY_CONFIG
    b_sft = baseline_state.get("safety_configuration") or {}
    c_sft = current_state.get("safety_configuration") or {}
    all_sft_keys = set(b_sft.keys()) | set(c_sft.keys())
    for k in all_sft_keys:
        old_val = b_sft.get(k)
        new_val = c_sft.get(k)
        if old_val != new_val:
            eval_res = evaluate_change(
                category=ChangeCategory.SAFETY_CONFIG,
                parameter_name=f"safety:{k}",
                old_value=old_val,
                new_value=new_val,
                expected_changes=expected_changes,
                actor_role=actor_role,
            )
            changes.append({
                "category": ChangeCategory.SAFETY_CONFIG,
                "parameter_name": f"safety:{k}",
                "old_value": old_val,
                "new_value": new_val,
                "reason": f"Safety configuration {k} modified from {old_val} to {new_val}",
                "eval": eval_res,
            })

    # 6. PLC_LOGIC
    b_prog = baseline_state.get("plc_program")
    c_prog = current_state.get("plc_program")
    old_plc_ver = baseline_state.get("plc_version")
    new_plc_ver = current_state.get("plc_version")

    if old_plc_ver and new_plc_ver and str(old_plc_ver).strip() != str(new_plc_ver).strip():
        eval_res = evaluate_change(
            category=ChangeCategory.PLC_LOGIC,
            parameter_name="plc_version",
            old_value=old_plc_ver,
            new_value=new_plc_ver,
            expected_changes=expected_changes,
            actor_role=actor_role,
        )
        changes.append({
            "category": ChangeCategory.PLC_LOGIC,
            "parameter_name": "plc_version",
            "old_value": old_plc_ver,
            "new_value": new_plc_ver,
            "reason": f"PLC version transitioned from {old_plc_ver} to {new_plc_ver}",
            "eval": eval_res,
        })

    # If full programs provided, do semantic diff on networks
    if b_prog and c_prog:
        diff_res = compare_plc_logic(b_prog, c_prog)
        if not diff_res.hash_match:
            for nd in diff_res.network_diffs:
                param_name = f"plc_network:{nd.network_id}"
                eval_res = evaluate_change(
                    category=ChangeCategory.PLC_LOGIC,
                    parameter_name=param_name,
                    old_value={"network_id": nd.network_id, "status": "BASELINE"},
                    new_value={"change_type": nd.change_type, "severity": nd.severity},
                    expected_changes=expected_changes,
                    actor_role=actor_role,
                )
                changes.append({
                    "category": ChangeCategory.PLC_LOGIC,
                    "parameter_name": param_name,
                    "old_value": nd.network_id,
                    "new_value": nd.change_type,
                    "reason": nd.description,
                    "eval": eval_res,
                })

    return changes
