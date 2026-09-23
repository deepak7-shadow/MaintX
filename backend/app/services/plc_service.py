"""
PLC service — database-backed PLC version management.

Stores and retrieves PLC logic versions, baselines, and
integrity check records using the Supabase tables:
  - plc_logic_versions
  - plc_logic_baselines
  - plc_logic_diffs
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException

from app.db.client import get_supabase_client
from app.schemas.auth import UserProfileResponse
from app.schemas.plc import (
    PLCBaselineResponse,
    PLCDiffResult,
    PLCFingerprint,
    PLCIntegrityCheckResponse,
    PLCVersionResponse,
)
from app.services.plc_engine import (
    calculate_plc_hash,
    canonicalize_plc_logic,
    compare_plc_logic,
    fingerprint,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_version(row: dict) -> PLCVersionResponse:
    return PLCVersionResponse(
        id=row["id"],
        machine_id=row["machine_id"],
        version_tag=row["version_tag"],
        description=row.get("description", ""),
        program_json=row["program_json"],
        sha256_hash=row["sha256_hash"],
        is_baseline=row.get("is_baseline", False),
        is_active=row.get("is_active", True),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _row_to_baseline(row: dict) -> PLCBaselineResponse:
    return PLCBaselineResponse(
        id=row["id"],
        machine_id=row["machine_id"],
        version_id=row["version_id"],
        version_tag=row["version_tag"],
        sha256_hash=row["sha256_hash"],
        network_count=row.get("network_count", 0),
        established_by=row["established_by"],
        established_at=row["established_at"],
        notes=row.get("notes"),
    )


# ---------------------------------------------------------------------------
# PLC version CRUD
# ---------------------------------------------------------------------------


async def store_plc_version(
    machine_id: UUID,
    program: dict,
    version_tag: str,
    description: str,
    actor: UserProfileResponse,
    set_as_baseline: bool = False,
) -> PLCVersionResponse:
    """
    Hash, canonicalize, and store a new PLC logic version.
    Optionally establishes it as the trusted baseline.
    """
    client = get_supabase_client()

    sha256 = calculate_plc_hash(program)
    canon = canonicalize_plc_logic(program)
    network_count = len(program.get("networks", []))

    try:
        result = client.table("plc_logic_versions").insert({
            "machine_id": str(machine_id),
            "version_tag": version_tag,
            "description": description,
            "program_json": program,
            "canonical_json": canon,
            "sha256_hash": sha256,
            "network_count": network_count,
            "is_baseline": set_as_baseline,
            "is_active": True,
            "created_by": str(actor.id),
        }).execute()
    except Exception as exc:
        logger.error("Failed to store PLC version: %s", exc)
        raise HTTPException(status_code=503, detail="Failed to store PLC logic version.")

    row = result.data[0]

    if set_as_baseline:
        await _establish_baseline(machine_id, row["id"], version_tag, sha256, network_count, actor)

    return _row_to_version(row)


async def _establish_baseline(
    machine_id: UUID,
    version_id: str,
    version_tag: str,
    sha256: str,
    network_count: int,
    actor: UserProfileResponse,
    notes: Optional[str] = None,
) -> None:
    """Mark a version as the trusted baseline in plc_logic_baselines."""
    client = get_supabase_client()
    # Deactivate previous baselines for this machine
    client.table("plc_logic_baselines").update({"is_active": False}).eq("machine_id", str(machine_id)).execute()
    client.table("plc_logic_baselines").insert({
        "machine_id": str(machine_id),
        "version_id": version_id,
        "version_tag": version_tag,
        "sha256_hash": sha256,
        "network_count": network_count,
        "established_by": str(actor.id),
        "is_active": True,
        "notes": notes,
    }).execute()


async def list_plc_versions(machine_id: UUID) -> List[PLCVersionResponse]:
    client = get_supabase_client()
    try:
        result = (
            client.table("plc_logic_versions")
            .select("*")
            .eq("machine_id", str(machine_id))
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="DB error listing PLC versions.")
    return [_row_to_version(r) for r in (result.data or [])]


async def get_plc_version(version_id: UUID) -> PLCVersionResponse:
    client = get_supabase_client()
    try:
        result = (
            client.table("plc_logic_versions")
            .select("*")
            .eq("id", str(version_id))
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="PLC version not found.")
    return _row_to_version(result.data)


async def get_active_baseline(machine_id: UUID) -> Optional[PLCBaselineResponse]:
    client = get_supabase_client()
    try:
        result = (
            client.table("plc_logic_baselines")
            .select("*")
            .eq("machine_id", str(machine_id))
            .eq("is_active", True)
            .order("established_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        return None
    if not result.data:
        return None
    return _row_to_baseline(result.data[0])


# ---------------------------------------------------------------------------
# Integrity check: compare current version against baseline
# ---------------------------------------------------------------------------


async def run_integrity_check(
    machine_id: UUID,
    machine_code: str,
    current_version_id: UUID,
) -> PLCIntegrityCheckResponse:
    """
    Compare the specified PLC version against the established baseline
    and return a full integrity check result including semantic diff.
    """
    baseline_row = await get_active_baseline(machine_id)
    if baseline_row is None:
        raise HTTPException(
            status_code=404,
            detail="No active PLC baseline found for this machine. Establish a baseline first.",
        )

    # Fetch baseline program
    client = get_supabase_client()
    b_ver_res = (
        client.table("plc_logic_versions")
        .select("*")
        .eq("id", str(baseline_row.version_id))
        .single()
        .execute()
    )
    if not b_ver_res.data:
        raise HTTPException(status_code=404, detail="Baseline PLC version program not found.")

    # Fetch current program
    c_ver_res = (
        client.table("plc_logic_versions")
        .select("*")
        .eq("id", str(current_version_id))
        .single()
        .execute()
    )
    if not c_ver_res.data:
        raise HTTPException(status_code=404, detail="Current PLC version not found.")

    baseline_prog = b_ver_res.data["program_json"]
    current_prog = c_ver_res.data["program_json"]

    diff = compare_plc_logic(baseline_prog, current_prog)

    return PLCIntegrityCheckResponse(
        machine_code=machine_code,
        machine_id=machine_id,
        checked_at=datetime.now(timezone.utc),
        baseline_version=diff.baseline_version,
        current_version=diff.current_version,
        baseline_hash=diff.baseline_hash,
        current_hash=diff.current_hash,
        integrity_status=diff.integrity_status,
        integrity_message=diff.integrity_message,
        diff=diff,
    )


async def quick_hash_check(
    machine_id: UUID,
    machine_code: str,
    program: dict,
) -> PLCIntegrityCheckResponse:
    """
    Quick integrity check: compute hash of provided program and compare
    against the stored baseline hash (no full diff required).
    Performs full diff if hashes differ.
    """
    baseline_row = await get_active_baseline(machine_id)
    if baseline_row is None:
        raise HTTPException(status_code=404, detail="No active PLC baseline.")

    current_hash = calculate_plc_hash(program)
    hash_match = current_hash == baseline_row.sha256_hash
    now = datetime.now(timezone.utc)

    diff: Optional[PLCDiffResult] = None
    if not hash_match:
        # Fetch baseline program for full diff
        client = get_supabase_client()
        b_res = (
            client.table("plc_logic_versions")
            .select("program_json")
            .eq("id", str(baseline_row.version_id))
            .single()
            .execute()
        )
        if b_res.data:
            diff = compare_plc_logic(b_res.data["program_json"], program)

    if hash_match:
        status = "VERIFIED"
        message = f"PLC LOGIC INTEGRITY VERIFIED — hash match. Baseline: {baseline_row.version_tag}."
    elif diff and diff.safety_violations:
        status = "INTEGRITY_FAILED"
        message = diff.integrity_message
    else:
        status = "HASH_MISMATCH"
        message = f"PLC HASH MISMATCH — current hash differs from baseline {baseline_row.version_tag}."

    return PLCIntegrityCheckResponse(
        machine_code=machine_code,
        machine_id=machine_id,
        checked_at=now,
        baseline_version=baseline_row.version_tag,
        current_version=program.get("version", "UNKNOWN"),
        baseline_hash=baseline_row.sha256_hash,
        current_hash=current_hash,
        integrity_status=status,
        integrity_message=message,
        diff=diff,
    )
