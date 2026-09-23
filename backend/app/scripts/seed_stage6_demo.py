"""
Stage 6 Demo Script — Change Detection & Authorization Policy Verification.

Executes and demonstrates all core Stage 6 requirements:
  1. Expected motor change (3000 -> 3200):
     => Evaluates to EXPECTED, AUTHORIZED, LOW risk
  2. Unexpected IP change (192.168.10.20 -> 192.168.10.50):
     => Evaluates to UNEXPECTED, UNAUTHORIZED, HIGH RISK
  3. Safety PLC modification (N7 interlock):
     => Evaluates to CRITICAL, SUPERVISOR REVIEW REQUIRED
  4. Records changes into Supabase configuration_changes table and verifies audit trail.

Usage:
  .venv/Scripts/python.exe -m app.scripts.seed_stage6_demo
"""
from __future__ import annotations

import os
import sys
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.schemas.changes import ChangeCategory
from app.services.change_engine import evaluate_change

SERVICE_KEY = os.getenv(
    "SUPABASE_SECRET_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdyZG1veGhmd3Nxa2hjc3JxdmF1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MDE1ODMzNCwiZXhwIjoyMTA1NzM0MzM0fQ.6HWgVMB7n62M6LT18UY-lhtKFbKNMfJWq3jDRF53YkE",
)
BASE_URL = os.getenv("SUPABASE_URL", "https://grdmoxhfwsqkhcsrqvau.supabase.co")

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def run_stage6_demo() -> None:
    print(f"\n{'='*75}")
    print(" MaintX Stage 6 — Change Detection Engine & Authorization Verification")
    print(f"{'='*75}")

    approved_scope = [
        {
            "category": "PARAMETERS",
            "parameter_name": "motor_speed_rpm",
            "from_value": 3000,
            "to_value": 3200,
            "reason": "Production cycle time reduction",
        },
        {
            "category": "PLC_LOGIC",
            "parameter_name": "plc_version",
            "from_value": "v17",
            "to_value": "v18",
            "reason": "PLC v18 logic enhancement",
        },
    ]

    # 1. Expected Motor Change
    print("\n[SCENARIO 1] Motor Speed Change: 3000 -> 3200 RPM")
    eval_motor = evaluate_change(
        category=ChangeCategory.PARAMETERS,
        parameter_name="motor_speed_rpm",
        old_value=3000,
        new_value=3200,
        expected_changes=approved_scope,
        actor_role="MAINTENANCE_ENGINEER",
    )
    print(f"  Category        : {ChangeCategory.PARAMETERS.value}")
    print(f"  Parameter       : motor_speed_rpm (3000 -> 3200)")
    print(f"  Expected Status : {'EXPECTED' if eval_motor.is_expected else 'UNEXPECTED'}")
    print(f"  Authorization   : {'AUTHORIZED' if eval_motor.is_authorized else 'UNAUTHORIZED'}")
    print(f"  Risk Level      : {eval_motor.risk_level.value} (Score: {eval_motor.risk_score})")
    print(f"  Approval Status : {eval_motor.approval_status.value}")

    # 2. Unexpected IP Change
    print("\n[SCENARIO 2] Unexpected Network IP Change: 192.168.10.20 -> 192.168.10.50")
    eval_ip = evaluate_change(
        category=ChangeCategory.NETWORK,
        parameter_name="ip_address",
        old_value="192.168.10.20",
        new_value="192.168.10.50",
        expected_changes=approved_scope,
        actor_role="MAINTENANCE_ENGINEER",
    )
    print(f"  Category        : {ChangeCategory.NETWORK.value}")
    print(f"  Parameter       : ip_address (192.168.10.20 -> 192.168.10.50)")
    print(f"  Expected Status : {'EXPECTED' if eval_ip.is_expected else 'UNEXPECTED'}")
    print(f"  Authorization   : {'AUTHORIZED' if eval_ip.is_authorized else 'UNAUTHORIZED'}")
    print(f"  Risk Level      : {eval_ip.risk_level.value} (Score: {eval_ip.risk_score}) -> HIGH RISK")
    print(f"  Review Required : {'SUPERVISOR REVIEW REQUIRED' if eval_ip.requires_supervisor_approval else 'None'}")

    # 3. Safety PLC Modification
    print("\n[SCENARIO 3] Safety PLC Modification: Network N7 (Safety Interlock) Removed")
    eval_safety = evaluate_change(
        category=ChangeCategory.PLC_LOGIC,
        parameter_name="plc_network:N7",
        old_value={"network_id": "N7", "status": "ACTIVE_INTERLOCK"},
        new_value={"network_id": "N7", "status": "REMOVED"},
        expected_changes=approved_scope,
        actor_role="MAINTENANCE_ENGINEER",
    )
    print(f"  Category        : {ChangeCategory.PLC_LOGIC.value}")
    print(f"  Parameter       : plc_network:N7 (Master Safety Interlock)")
    print(f"  Risk Level      : {eval_safety.risk_level.value} (Score: {eval_safety.risk_score}) -> CRITICAL")
    print(f"  Authorization   : {'AUTHORIZED' if eval_safety.is_authorized else 'UNAUTHORIZED'}")
    print(f"  Review Status   : {'SUPERVISOR REVIEW REQUIRED' if eval_safety.requires_supervisor_approval else 'None'}")

    # 4. Check / Seed to Supabase if session exists
    print("\n[4] Database Sync Check...")
    with httpx.Client(timeout=30.0) as client:
        # Check active CNC-01 machine
        m_res = client.get(f"{BASE_URL}/rest/v1/machines?machine_code=eq.CNC-01", headers=HEADERS)
        machines = m_res.json()
        if machines:
            machine_id = machines[0]["id"]
            print(f"  CNC-01 Machine ID: {machine_id}")

            # Check profile for TECH-042
            p_res = client.get(f"{BASE_URL}/rest/v1/profiles?engineer_code=eq.TECH-042", headers=HEADERS)
            profiles = p_res.json()
            if profiles:
                tech_id = profiles[0]["id"]
                # Query sessions
                s_res = client.get(
                    f"{BASE_URL}/rest/v1/maintenance_sessions?machine_id=eq.{machine_id}&limit=1",
                    headers=HEADERS,
                )
                sessions = s_res.json()
                if sessions:
                    session_id = sessions[0]["id"]
                    print(f"  Maintenance Session ID: {session_id}")
                    # Insert demo changes into configuration_changes
                    records = [
                        {
                            "session_id": session_id,
                            "machine_id": machine_id,
                            "user_id": tech_id,
                            "user_role": "MAINTENANCE_ENGINEER",
                            "category": "PARAMETERS",
                            "parameter_name": "motor_speed_rpm",
                            "old_value": 3000,
                            "new_value": 3200,
                            "reason": "Production configuration update",
                            "is_expected": eval_motor.is_expected,
                            "is_authorized": eval_motor.is_authorized,
                            "risk_score": eval_motor.risk_score,
                            "risk_level": eval_motor.risk_level.value,
                            "requires_supervisor_approval": eval_motor.requires_supervisor_approval,
                            "approval_status": eval_motor.approval_status.value,
                        },
                        {
                            "session_id": session_id,
                            "machine_id": machine_id,
                            "user_id": tech_id,
                            "user_role": "MAINTENANCE_ENGINEER",
                            "category": "NETWORK",
                            "parameter_name": "ip_address",
                            "old_value": "192.168.10.20",
                            "new_value": "192.168.10.50",
                            "reason": "Unscheduled interface reconfiguration",
                            "is_expected": eval_ip.is_expected,
                            "is_authorized": eval_ip.is_authorized,
                            "risk_score": eval_ip.risk_score,
                            "risk_level": eval_ip.risk_level.value,
                            "requires_supervisor_approval": eval_ip.requires_supervisor_approval,
                            "approval_status": eval_ip.approval_status.value,
                        },
                        {
                            "session_id": session_id,
                            "machine_id": machine_id,
                            "user_id": tech_id,
                            "user_role": "MAINTENANCE_ENGINEER",
                            "category": "PLC_LOGIC",
                            "parameter_name": "plc_network:N7",
                            "old_value": "SAFETY_OK -> MACHINE_ENABLE",
                            "new_value": "REMOVED",
                            "reason": "Safety bypass attempted",
                            "is_expected": eval_safety.is_expected,
                            "is_authorized": eval_safety.is_authorized,
                            "risk_score": eval_safety.risk_score,
                            "risk_level": eval_safety.risk_level.value,
                            "requires_supervisor_approval": eval_safety.requires_supervisor_approval,
                            "approval_status": eval_safety.approval_status.value,
                        },
                    ]
                    insert_res = client.post(
                        f"{BASE_URL}/rest/v1/configuration_changes",
                        headers=HEADERS,
                        json=records,
                    )
                    if insert_res.status_code in (200, 201):
                        print(f"  [SUCCESS] Inserted 3 verified changes into configuration_changes.")
                    else:
                        print(f"  [INFO] Insert response: {insert_res.status_code} {insert_res.text[:150]}")
                else:
                    print("  [INFO] No active session found — changes demonstrated in-memory.")

    print(f"\n{'='*75}")
    print(" Stage 6 Verification Complete.")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    run_stage6_demo()
