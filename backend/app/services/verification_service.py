"""
Verification Service — database persistence, audit logging, and demo scenarios
for final maintenance verification.
"""
from __future__ import annotations

import copy
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.db.client import get_supabase_client
from app.schemas.audit import AuditEventCreate, AuditEventType
from app.schemas.verification import (
    ChangeClassification,
    ParameterComparison,
    PLCVerificationDetail,
    PLCVerificationStatus,
    VerificationResultResponse,
    VerificationStatus,
    VerifySessionRequest,
)
from app.services import audit_service
from app.services.plc_demo import BASELINE_V17, TAMPERED_V17
from app.services.verification_engine import (
    OPERATIONAL_PARAMETERS,
    execute_final_verification,
)

logger = logging.getLogger(__name__)

# Pre-built Approved V18 PLC Program (Matches approved work order: Motor 3200 RPM + PLC v18)
APPROVED_V18 = copy.deepcopy(BASELINE_V17)
APPROVED_V18["version"] = "v18"
APPROVED_V18["description"] = "CNC-01 Precision 5-Axis Milling Machine — Production Logic v18 (Approved)"
if "data_files" in APPROVED_V18 and "N7" in APPROVED_V18["data_files"]:
    if "N7:10" in APPROVED_V18["data_files"]["N7"]:
        APPROVED_V18["data_files"]["N7"]["N7:10"]["value"] = 3200

# Update network N2 description for v18
for net in APPROVED_V18.get("networks", []):
    if net.get("network_id") == "N2":
        net["description"] = "Spindle Motor Speed Control — 3200 RPM"


async def run_session_verification(
    session_id: UUID,
    actor_id: Optional[UUID] = None,
    request_body: Optional[VerifySessionRequest] = None,
) -> VerificationResultResponse:
    """
    Execute full verification for an active or completed maintenance session.
    Compares baseline + approved changes against actual final state.
    Persists to `verification_results` and logs an audit event.
    """
    sb = get_supabase_client()

    # 1. Fetch session
    try:
        ses_resp = sb.table("maintenance_sessions").select("*").eq("id", str(session_id)).single().execute()
        if not ses_resp.data:
            raise HTTPException(status_code=404, detail=f"Maintenance session {session_id} not found.")
        session_row = ses_resp.data
    except Exception as exc:
        logger.error("Failed to fetch session %s: %s", session_id, exc)
        raise HTTPException(status_code=503, detail="Database query failed for session.")

    machine_id = session_row["machine_id"]
    request_id = session_row["request_id"]

    # 2. Fetch machine and request
    req_resp = sb.table("maintenance_requests").select("*").eq("id", str(request_id)).single().execute()
    req_row = req_resp.data or {}
    approved_changes = req_row.get("expected_changes") or []

    # 3. Determine baseline parameters
    baseline_params = {
        "motor_speed_rpm": 3000,
        "temperature_limit_c": 80.0,
        "pressure_limit_bar": 5.0,
        "operating_mode": "AUTO",
        "ip_address": "192.168.10.20",
        "subnet_mask": "255.255.255.0",
        "gateway": "192.168.10.1",
        "firmware_version": "4.2.1",
        "safety_category": "CAT_4",
    }

    # 4. Determine actual final parameters
    if request_body and request_body.final_machine_state:
        final_params = request_body.final_machine_state
    else:
        # Fetch current state of machine
        mach_resp = sb.table("machines").select("*").eq("id", str(machine_id)).single().execute()
        mach_row = mach_resp.data or {}
        final_params = {
            "motor_speed_rpm": mach_row.get("motor_speed_rpm", 3200),
            "temperature_limit_c": mach_row.get("temperature_limit_c", 80.0),
            "pressure_limit_bar": mach_row.get("pressure_limit_bar", 5.0),
            "operating_mode": mach_row.get("operating_mode", "AUTO"),
            "ip_address": mach_row.get("ip_address", "192.168.10.20"),
            "subnet_mask": mach_row.get("subnet_mask", "255.255.255.0"),
            "gateway": mach_row.get("gateway", "192.168.10.1"),
            "firmware_version": mach_row.get("firmware_version", "4.2.1"),
            "safety_category": mach_row.get("safety_category", "CAT_4"),
        }

    # 5. Determine PLC programs
    baseline_plc = BASELINE_V17
    approved_plc = APPROVED_V18

    if request_body and request_body.final_plc_logic:
        actual_plc = request_body.final_plc_logic
    else:
        actual_plc = APPROVED_V18

    # 6. Execute core verification
    result = execute_final_verification(
        baseline_params=baseline_params,
        approved_changes=approved_changes,
        final_params=final_params,
        baseline_plc=baseline_plc,
        actual_plc=actual_plc,
        approved_plc=approved_plc,
    )

    result.session_id = session_id
    result.machine_id = UUID(str(machine_id))
    result.verified_by = actor_id

    # 7. Persist to public.verification_results
    verif_id = uuid.uuid4()
    result.id = verif_id

    db_row = {
        "id": str(verif_id),
        "session_id": str(session_id),
        "machine_id": str(machine_id),
        "verified_by": str(actor_id) if actor_id else "0e2b777c-bdb6-43ec-a15b-1aca9a209280",
        "final_status": result.final_status.value,
        "plc_integrity_passed": result.plc_integrity_passed,
        "all_changes_authorized": result.all_changes_authorized,
        "unresolved_critical_changes": result.unresolved_critical_changes,
        "expected_changes_count": result.expected_changes_count,
        "unexpected_changes_count": result.unexpected_changes_count,
        "unauthorized_changes_count": result.unauthorized_changes_count,
        "verification_report": result.model_dump(mode="json"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        sb.table("verification_results").insert(db_row).execute()
        # Update session verification status
        sb.table("maintenance_sessions").update({
            "verification_status": result.final_status.value
        }).eq("id", str(session_id)).execute()
    except Exception as exc:
        logger.warning("Could not persist verification_results to database: %s", exc)

    # 8. Record audit log event
    try:
        event_type = (
            AuditEventType.CRITICAL_RISK_FLAGGED
            if result.final_status == VerificationStatus.FAILED
            else AuditEventType.PLC_INTEGRITY_CHECKED
        )
        await audit_service.record_event(
            AuditEventCreate(
                event_type=event_type,
                machine_id=result.machine_id,
                session_id=result.session_id,
                user_id=actor_id,
                event_data={
                    "verification_id": str(verif_id),
                    "final_status": result.final_status.value,
                    "unresolved_critical_changes": result.unresolved_critical_changes,
                    "plc_integrity_passed": result.plc_integrity_passed,
                    "all_changes_authorized": result.all_changes_authorized,
                    "closure_allowed": result.closure_allowed,
                },
            ),
            actor_id=actor_id,
        )
    except Exception as exc:
        logger.warning("Failed to record verification audit event: %s", exc)

    return result


async def get_latest_session_verification(session_id: UUID) -> Optional[VerificationResultResponse]:
    """Retrieve the most recent verification result for a session."""
    sb = get_supabase_client()
    try:
        resp = (
            sb.table("verification_results")
            .select("*")
            .eq("session_id", str(session_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            report_data = resp.data[0]["verification_report"]
            return VerificationResultResponse(**report_data)
    except Exception as exc:
        logger.warning("Could not fetch verification result for session %s: %s", session_id, exc)
    return None


def get_demo_verification(scenario_id: str) -> VerificationResultResponse:
    """
    Generate instant deterministic demo verification results.
    Supported scenarios:
      - 'verified'
      - 'review-required'
      - 'failed-safety'
    """
    baseline_params = {
        "motor_speed_rpm": 3000,
        "temperature_limit_c": 80.0,
        "pressure_limit_bar": 5.0,
        "operating_mode": "AUTO",
        "ip_address": "192.168.10.20",
        "subnet_mask": "255.255.255.0",
        "gateway": "192.168.10.1",
        "firmware_version": "4.2.1",
        "safety_category": "CAT_4",
        "plc_version": "v17",
    }

    approved_changes = [
        {
            "parameter_name": "motor_speed_rpm",
            "category": "PARAMETERS",
            "old_value": 3000,
            "new_value": 3200,
            "is_authorized": True,
        },
        {
            "parameter_name": "plc_version",
            "category": "PLC_LOGIC",
            "old_value": "v17",
            "new_value": "v18",
            "is_authorized": True,
        },
    ]

    demo_session_id = UUID("cccccccc-1111-2222-3333-444444444444")
    demo_machine_id = UUID("bbbbbbbb-1111-2222-3333-444444444444")

    if scenario_id == "verified":
        # 1. Clean Approved Maintenance
        final_params = copy.deepcopy(baseline_params)
        final_params["motor_speed_rpm"] = 3200
        final_params["plc_version"] = "v18"

        res = execute_final_verification(
            baseline_params=baseline_params,
            approved_changes=approved_changes,
            final_params=final_params,
            baseline_plc=BASELINE_V17,
            actual_plc=APPROVED_V18,
            approved_plc=APPROVED_V18,
        )
        res.id = uuid.uuid4()
        res.session_id = demo_session_id
        res.machine_id = demo_machine_id
        return res

    elif scenario_id in ("review-required", "review_required"):
        # 2. Minor Discrepancy (Unexpected operational setpoint change)
        final_params = copy.deepcopy(baseline_params)
        final_params["motor_speed_rpm"] = 3200
        final_params["plc_version"] = "v18"
        final_params["pressure_limit_bar"] = 5.2  # Unexpected parameter change

        res = execute_final_verification(
            baseline_params=baseline_params,
            approved_changes=approved_changes,
            final_params=final_params,
            baseline_plc=BASELINE_V17,
            actual_plc=APPROVED_V18,
            approved_plc=APPROVED_V18,
        )
        res.id = uuid.uuid4()
        res.session_id = demo_session_id
        res.machine_id = demo_machine_id
        return res

    elif scenario_id in ("failed-safety", "failed", "safety-compromised"):
        # 3. Critical Tampering: Rogue IP .50 + N7 Safety Interlock Removed
        final_params = copy.deepcopy(baseline_params)
        final_params["motor_speed_rpm"] = 3200
        final_params["ip_address"] = "192.168.10.50"  # Unauthorized network modification

        res = execute_final_verification(
            baseline_params=baseline_params,
            approved_changes=approved_changes,
            final_params=final_params,
            baseline_plc=BASELINE_V17,
            actual_plc=TAMPERED_V17,  # N7 Removed
            approved_plc=APPROVED_V18,
        )
        res.id = uuid.uuid4()
        res.session_id = demo_session_id
        res.machine_id = demo_machine_id
        return res

    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown verification scenario '{scenario_id}'. Valid scenarios: 'verified', 'review-required', 'failed-safety'.",
        )
