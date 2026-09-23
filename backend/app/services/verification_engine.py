"""
Verification Engine — Deterministic Multi-Dimensional Maintenance Verification.

Compares:
  - Trusted baseline machine parameters + approved changes
  - Trusted baseline PLC logic + approved PLC logic changes
against:
  - Actual final machine state
  - Actual final PLC logic

Classifies every parameter and logic element into:
  - EXPECTED
  - UNEXPECTED
  - UNAUTHORIZED
  - UNRESOLVED

Determines overall verification status:
  - VERIFIED: All changes expected, authorized, PLC intact. Closure allowed.
  - REVIEW_REQUIRED: Minor unexpected or unapproved changes. Requires supervisor sign-off.
  - FAILED: Unresolved critical changes or safety interlock compromised. Closure STRICTLY BLOCKED.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from app.schemas.verification import (
    ChangeClassification,
    ParameterComparison,
    PLCVerificationDetail,
    PLCVerificationStatus,
    VerificationResultResponse,
    VerificationStatus,
)
from app.services.plc_engine import (
    calculate_plc_hash,
    compare_plc_logic,
)

# Parameters that are considered critical security or safety boundaries
CRITICAL_PARAMETERS = {
    "ip_address": "NETWORK",
    "gateway": "NETWORK",
    "subnet_mask": "NETWORK",
    "firmware_version": "FIRMWARE",
    "safety_category": "SAFETY_CONFIG",
    "emergency_stop_mode": "SAFETY_CONFIG",
    "interlock_status": "SAFETY_CONFIG",
}

# Standard operational parameters.
# NOTE: plc_version is intentionally excluded here — it is fully verified by
# the dedicated PLC hash/semantic-diff engine (verify_plc_logic_state). Including
# it in parameter comparison would create a spurious UNEXPECTED classification
# whenever an approved PLC upgrade bumps the version string.
OPERATIONAL_PARAMETERS = {
    "motor_speed_rpm": ("PARAMETERS", 3000),
    "temperature_limit_c": ("PARAMETERS", 80.0),
    "pressure_limit_bar": ("PARAMETERS", 5.0),
    "operating_mode": ("PARAMETERS", "AUTO"),
    "ip_address": ("NETWORK", "192.168.10.20"),
    "subnet_mask": ("NETWORK", "255.255.255.0"),
    "gateway": ("NETWORK", "192.168.10.1"),
    "firmware_version": ("FIRMWARE", "4.2.1"),
    "safety_category": ("SAFETY_CONFIG", "CAT_4"),
}


def normalize_approved_changes(
    approved_changes: Union[List[Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Normalize approved changes into a lookup dict: {param_name: approved_value}.
    Handles both list format ([{'parameter_name': '...', 'new_value': ...}])
    and simple dictionary format ({'motor_speed_rpm': 3200}).
    """
    if isinstance(approved_changes, dict):
        return dict(approved_changes)

    normalized: Dict[str, Any] = {}
    for item in approved_changes:
        if isinstance(item, dict):
            name = item.get("parameter_name") or item.get("parameter")
            val = item.get("new_value")
            if val is None:
                val = item.get("target_value")
            if name:
                normalized[name] = val
    return normalized


def compare_machine_parameters(
    baseline_params: Dict[str, Any],
    approved_changes: Union[List[Dict[str, Any]], Dict[str, Any]],
    actual_params: Dict[str, Any],
) -> List[ParameterComparison]:
    """
    Compare baseline + approved changes against actual final machine state.
    Classify each parameter as EXPECTED, UNEXPECTED, UNAUTHORIZED, or UNRESOLVED.
    """
    approved_dict = normalize_approved_changes(approved_changes)
    # plc_version is exclusively verified by the PLC hash engine — strip it from
    # parameter comparison to avoid spurious UNRESOLVED / UNEXPECTED classifications.
    approved_dict.pop("plc_version", None)

    # Gather union of all keys
    all_keys = set(OPERATIONAL_PARAMETERS.keys())
    all_keys.update(baseline_params.keys())
    all_keys.update(approved_dict.keys())
    all_keys.update(actual_params.keys())

    comparisons: List[ParameterComparison] = []

    for key in sorted(all_keys):
        category, default_val = OPERATIONAL_PARAMETERS.get(key, ("PARAMETERS", None))
        is_critical = key in CRITICAL_PARAMETERS

        base_val = baseline_params.get(key, default_val)
        actual_val = actual_params.get(key, base_val)
        has_approved_change = key in approved_dict
        approved_val = approved_dict[key] if has_approved_change else base_val

        # 1. Did actual value change from baseline?
        changed_from_baseline = str(actual_val) != str(base_val)
        changed_from_approved = str(actual_val) != str(approved_val)

        # Skip unchanged non-approved parameters
        if not changed_from_baseline and not has_approved_change:
            continue

        if has_approved_change:
            if not changed_from_approved:
                # Actual matches the approved change
                classification = ChangeClassification.EXPECTED
                risk_level = "LOW"
                details = f"Approved change implemented accurately: {base_val} → {actual_val}."
            else:
                # Was approved for approved_val, but actual differs
                classification = ChangeClassification.UNRESOLVED
                risk_level = "CRITICAL" if is_critical else "HIGH"
                details = (
                    f"Deviation from approved scope: expected {approved_val}, "
                    f"actual machine state is {actual_val}."
                )
        else:
            # Not in approved scope, but changed from baseline
            if is_critical:
                classification = ChangeClassification.UNAUTHORIZED
                risk_level = "CRITICAL"
                details = (
                    f"Unauthorized change to critical boundary parameter '{key}': "
                    f"baseline was {base_val}, changed to {actual_val} without authorization."
                )
            else:
                classification = ChangeClassification.UNEXPECTED
                risk_level = "MEDIUM"
                details = (
                    f"Unexpected operational change to '{key}': "
                    f"baseline was {base_val}, modified to {actual_val}."
                )

        comparisons.append(
            ParameterComparison(
                parameter_name=key,
                category=category,
                baseline_value=base_val,
                approved_value=approved_val if has_approved_change else None,
                actual_value=actual_val,
                classification=classification,
                risk_level=risk_level,
                details=details,
                is_critical=is_critical,
            )
        )

    return comparisons


def verify_plc_logic_state(
    baseline_plc: Dict[str, Any],
    approved_plc: Optional[Dict[str, Any]],
    actual_plc: Dict[str, Any],
    approved_logic_changes: Optional[List[Dict[str, Any]]] = None,
) -> PLCVerificationDetail:
    """
    Verify PLC logic state across hash, semantic AST diff, safety interlocks, and approved logic.
    """
    # 1. Hashes
    baseline_hash = calculate_plc_hash(baseline_plc)
    target_plc = approved_plc if approved_plc else baseline_plc
    approved_hash = calculate_plc_hash(target_plc)
    actual_hash = calculate_plc_hash(actual_plc)

    hash_matches = (actual_hash == approved_hash)

    # 2. Semantic Diff (actual vs baseline)
    diff_vs_baseline = compare_plc_logic(baseline_plc, actual_plc)
    semantic_diff = diff_vs_baseline.model_dump()

    # 3. Safety Changes Analysis (N7 safety interlock check)
    safety_changes_detected = False
    safety_interlock_compromised = False
    details: List[str] = []

    # Check for removed networks that are safety critical
    baseline_nets = {n.get("network_id"): n for n in baseline_plc.get("networks", [])}
    actual_nets = {n.get("network_id"): n for n in actual_plc.get("networks", [])}

    # Check N7 specifically
    if "N7" in baseline_nets and "N7" not in actual_nets:
        safety_changes_detected = True
        safety_interlock_compromised = True
        details.append(
            "CRITICAL VIOLATION: Safety interlock network 'N7' (SAFETY_OK → MACHINE_ENABLE) was REMOVED."
        )

    # Check other safety networks
    for nid, net in baseline_nets.items():
        if net.get("safety_critical"):
            if nid not in actual_nets:
                safety_changes_detected = True
                safety_interlock_compromised = True
                details.append(f"CRITICAL VIOLATION: Safety network '{nid}' was removed.")
            else:
                # Check if instructions or contacts were altered
                act = actual_nets[nid]
                if act.get("contacts") != net.get("contacts") or act.get("instructions") != net.get("instructions"):
                    safety_changes_detected = True
                    details.append(f"WARNING: Safety network '{nid}' logic was modified.")

    # 4. Approved Logic Changes check
    approved_logic_matches = True
    if approved_plc is not None:
        diff_vs_approved = compare_plc_logic(approved_plc, actual_plc)
        if diff_vs_approved.modified_networks or diff_vs_approved.added_networks or diff_vs_approved.removed_networks:
            approved_logic_matches = False
            details.append("PLC logic contains unapproved modifications relative to target approved logic.")
    else:
        # If no approved PLC change, actual must match baseline
        if actual_hash != baseline_hash:
            approved_logic_matches = False
            details.append("No PLC logic changes were approved, but actual logic was modified.")

    # Determine PLC Status
    if safety_interlock_compromised:
        status = PLCVerificationStatus.SAFETY_INTERLOCK_COMPROMISED
    elif not hash_matches:
        if not approved_logic_matches:
            status = PLCVerificationStatus.UNAPPROVED_LOGIC
        else:
            status = PLCVerificationStatus.HASH_MISMATCH
    else:
        status = PLCVerificationStatus.VERIFIED
        details.append("PLC logic integrity 100% verified. Hash matches approved logic.")

    return PLCVerificationDetail(
        baseline_hash=baseline_hash,
        approved_hash=approved_hash,
        actual_hash=actual_hash,
        hash_matches=hash_matches,
        semantic_diff=semantic_diff,
        safety_changes_detected=safety_changes_detected,
        safety_interlock_compromised=safety_interlock_compromised,
        approved_logic_matches=approved_logic_matches,
        status=status,
        details=details,
    )


def execute_final_verification(
    baseline_params: Dict[str, Any],
    approved_changes: Union[List[Dict[str, Any]], Dict[str, Any]],
    final_params: Dict[str, Any],
    baseline_plc: Dict[str, Any],
    actual_plc: Dict[str, Any],
    approved_plc: Optional[Dict[str, Any]] = None,
) -> VerificationResultResponse:
    """
    Primary verification entrypoint. Compares baseline + approved changes against
    actual machine state + actual PLC logic.
    """
    # Explicitly strip plc_version from parameter dicts if callers injected it —
    # PLC logic is verified exclusively by verify_plc_logic_state via hash + semantic diff.
    final_params = {k: v for k, v in final_params.items() if k != "plc_version"}
    baseline_params = {k: v for k, v in baseline_params.items() if k != "plc_version"}

    # 1. Compare machine parameters
    param_comparisons = compare_machine_parameters(
        baseline_params=baseline_params,
        approved_changes=approved_changes,
        actual_params=final_params,
    )

    # 2. Verify PLC logic
    plc_detail = verify_plc_logic_state(
        baseline_plc=baseline_plc,
        approved_plc=approved_plc,
        actual_plc=actual_plc,
    )

    # 3. Count classifications
    expected_count = sum(1 for p in param_comparisons if p.classification == ChangeClassification.EXPECTED)
    unexpected_count = sum(1 for p in param_comparisons if p.classification == ChangeClassification.UNEXPECTED)
    unauthorized_count = sum(1 for p in param_comparisons if p.classification == ChangeClassification.UNAUTHORIZED)
    unresolved_count = sum(1 for p in param_comparisons if p.classification == ChangeClassification.UNRESOLVED)

    # Calculate unresolved critical changes
    unresolved_critical_params = sum(
        1 for p in param_comparisons
        if p.is_critical and p.classification in (ChangeClassification.UNAUTHORIZED, ChangeClassification.UNRESOLVED)
    )

    unresolved_critical_total = unresolved_critical_params
    if plc_detail.safety_interlock_compromised:
        unresolved_critical_total += 1
    if not plc_detail.approved_logic_matches and plc_detail.safety_changes_detected:
        unresolved_critical_total += 1

    plc_integrity_passed = (
        plc_detail.hash_matches
        and not plc_detail.safety_interlock_compromised
        and plc_detail.status == PLCVerificationStatus.VERIFIED
    )

    all_changes_authorized = (
        unauthorized_count == 0
        and not plc_detail.safety_interlock_compromised
    )

    # 4. Final status determination
    now_ts = datetime.now(timezone.utc)

    if unresolved_critical_total > 0 or plc_detail.safety_interlock_compromised:
        final_status = VerificationStatus.FAILED
        closure_allowed = False
        message = (
            f"VERIFICATION FAILED: {unresolved_critical_total} unresolved critical change(s) detected. "
            f"Safety interlocks or unauthorized perimeter changes must be resolved. Maintenance closure BLOCKED."
        )
    elif unexpected_count > 0 or unauthorized_count > 0 or not plc_integrity_passed or unresolved_count > 0:
        final_status = VerificationStatus.REVIEW_REQUIRED
        closure_allowed = False
        message = (
            f"VERIFICATION REVIEW REQUIRED: Discrepancies detected ({unexpected_count} unexpected, "
            f"{unresolved_count} unresolved). Supervisor sign-off required prior to maintenance closure."
        )
    else:
        final_status = VerificationStatus.VERIFIED
        closure_allowed = True
        message = (
            f"VERIFICATION PASSED: Machine parameters and PLC logic perfectly match approved maintenance baseline. "
            f"All {expected_count} expected change(s) verified. Machine ready to return to OPERATIONAL status."
        )

    return VerificationResultResponse(
        final_status=final_status,
        plc_integrity_passed=plc_integrity_passed,
        all_changes_authorized=all_changes_authorized,
        unresolved_critical_changes=unresolved_critical_total,
        expected_changes_count=expected_count,
        unexpected_changes_count=unexpected_count,
        unauthorized_changes_count=unauthorized_count,
        unresolved_changes_count=unresolved_count,
        parameters_comparison=param_comparisons,
        plc_verification=plc_detail,
        closure_allowed=closure_allowed,
        message=message,
        verified_at=now_ts,
    )
