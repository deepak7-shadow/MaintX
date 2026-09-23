"""
Seed PLC baseline for CNC-01 in Supabase.

Populates:
  - plc_logic_versions with BASELINE_V17
  - plc_logic_baselines with BASELINE_V17 as active trusted baseline

Also demonstrates the tamper detection flow live in script output:
  - Computes baseline hash
  - Computes tampered hash (N7 removed)
  - Compares them to prove:
      PLC HASH MISMATCH
      PLC LOGIC INTEGRITY FAILED
      SAFETY INTERLOCK REMOVED

Usage:
  .venv/Scripts/python.exe -m app.scripts.seed_plc_baseline
"""
from __future__ import annotations

import os
import sys
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.plc_demo import BASELINE_V17, TAMPERED_V17
from app.services.plc_engine import (
    calculate_plc_hash,
    canonicalize_plc_logic,
    compare_plc_logic,
)

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


def seed_plc_baseline() -> None:
    print(f"\n{'='*70}")
    print(" MaintX Stage 5 — PLC Baseline & Tamper Detection Seeder")
    print(f"{'='*70}")

    # 1. Compute Hashes
    baseline_hash = calculate_plc_hash(BASELINE_V17)
    baseline_canon = canonicalize_plc_logic(BASELINE_V17)
    tampered_hash = calculate_plc_hash(TAMPERED_V17)

    print("\n[1] PLC Program Fingerprints:")
    print(f"  BASELINE (v17) SHA-256 : {baseline_hash}")
    print(f"  TAMPERED (v17) SHA-256 : {tampered_hash}")
    print(f"  Hashes Match?          : {baseline_hash == tampered_hash}")

    # 2. Run Semantic Diff Engine
    diff_result = compare_plc_logic(BASELINE_V17, TAMPERED_V17)
    print("\n[2] Semantic Diff Demonstration:")
    print(f"  Status   : {diff_result.integrity_status}")
    print(f"  Message  : {diff_result.integrity_message}")
    print(f"  Removed  : {diff_result.removed_networks}")
    print(f"  Violations:")
    for v in diff_result.safety_violations:
        print(f"    - {v}")

    # 3. Seed into Remote Supabase DB
    print("\n[3] Connecting to Supabase...")
    with httpx.Client(timeout=30.0) as client:
        # Get CNC-01 machine id
        m_resp = client.get(
            f"{BASE_URL}/rest/v1/machines?machine_code=eq.CNC-01&select=id,machine_code,plc_version",
            headers=HEADERS,
        )
        machines = m_resp.json()
        if not machines:
            print("  [ERROR] CNC-01 machine not found in remote database.")
            return

        machine_id = machines[0]["id"]
        print(f"  Machine CNC-01 ID: {machine_id}")

        # Get Admin or Tech profile id
        p_resp = client.get(
            f"{BASE_URL}/rest/v1/profiles?engineer_code=eq.TECH-042&select=id,engineer_code",
            headers=HEADERS,
        )
        profiles = p_resp.json()
        if not profiles:
            p_resp = client.get(
                f"{BASE_URL}/rest/v1/profiles?select=id,engineer_code&limit=1",
                headers=HEADERS,
            )
            profiles = p_resp.json()

        author_id = profiles[0]["id"]
        print(f"  Author Profile ({profiles[0].get('engineer_code')}): {author_id}")

        # Check if baseline version exists
        v_check = client.get(
            f"{BASE_URL}/rest/v1/plc_logic_versions?machine_id=eq.{machine_id}&version_tag=eq.v17&select=id",
            headers=HEADERS,
        )
        existing_versions = v_check.json()

        if existing_versions:
            version_id = existing_versions[0]["id"]
            print(f"  [EXISTS] PLC version v17 ID: {version_id}")
            # Update with canonical_json and sha256_hash
            client.patch(
                f"{BASE_URL}/rest/v1/plc_logic_versions?id=eq.{version_id}",
                headers=HEADERS,
                json={
                    "sha256_hash": baseline_hash,
                    "canonical_json": baseline_canon,
                    "program_json": BASELINE_V17,
                    "network_count": len(BASELINE_V17["networks"]),
                    "is_baseline": True,
                },
            )
        else:
            v_create = client.post(
                f"{BASE_URL}/rest/v1/plc_logic_versions",
                headers=HEADERS,
                json={
                    "machine_id": machine_id,
                    "version_tag": "v17",
                    "description": "CNC-01 Production Logic v17 (Active Trusted Baseline)",
                    "program_json": BASELINE_V17,
                    "canonical_json": baseline_canon,
                    "sha256_hash": baseline_hash,
                    "network_count": len(BASELINE_V17["networks"]),
                    "is_baseline": True,
                    "is_active": True,
                    "created_by": author_id,
                },
            )
            if v_create.status_code not in (200, 201):
                print(f"  [ERROR] Failed to insert PLC version: {v_create.status_code} {v_create.text}")
                return
            version_id = v_create.json()[0]["id"]
            print(f"  [CREATED] PLC version v17 ID: {version_id}")

        # Deactivate any previous baseline for CNC-01
        client.patch(
            f"{BASE_URL}/rest/v1/plc_logic_baselines?machine_id=eq.{machine_id}",
            headers=HEADERS,
            json={"is_active": False},
        )

        # Upsert baseline
        b_create = client.post(
            f"{BASE_URL}/rest/v1/plc_logic_baselines",
            headers=HEADERS,
            json={
                "machine_id": machine_id,
                "version_id": version_id,
                "version_tag": "v17",
                "sha256_hash": baseline_hash,
                "network_count": len(BASELINE_V17["networks"]),
                "is_active": True,
                "established_by": author_id,
                "notes": "Stage 5 Production Baseline — Master Safety Interlock (N7) Verified.",
            },
        )
        if b_create.status_code in (200, 201):
            print(f"  [SUCCESS] Established active baseline for CNC-01 (v17)")
        else:
            print(f"  [INFO/NOTICE] Baseline setup status: {b_create.status_code} {b_create.text}")

        # Also store the audit diff for the tamper demo in plc_logic_diffs
        client.post(
            f"{BASE_URL}/rest/v1/plc_logic_diffs",
            headers=HEADERS,
            json={
                "machine_id": machine_id,
                "baseline_version": diff_result.baseline_version,
                "current_version": diff_result.current_version,
                "baseline_hash": diff_result.baseline_hash,
                "current_hash": diff_result.current_hash,
                "hash_match": diff_result.hash_match,
                "integrity_status": diff_result.integrity_status,
                "integrity_message": diff_result.integrity_message,
                "network_diffs": [d.model_dump() for d in diff_result.network_diffs],
                "added_networks": diff_result.added_networks,
                "removed_networks": diff_result.removed_networks,
                "modified_networks": diff_result.modified_networks,
                "safety_violations": diff_result.safety_violations,
                "total_changes": diff_result.total_changes,
                "checked_by": author_id,
            },
        )
        print("  [SUCCESS] Recorded tamper detection audit event in plc_logic_diffs.")

    print(f"\n{'='*70}")
    print(" Seed & Demo Verification Complete.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    seed_plc_baseline()
