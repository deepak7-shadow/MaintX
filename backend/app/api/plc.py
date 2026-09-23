"""
PLC API router — software PLC simulator endpoints.

Endpoints
---------
POST /api/plc/{machine_code}/versions          — Store a new PLC logic version
GET  /api/plc/{machine_code}/versions          — List all versions for a machine
GET  /api/plc/{machine_code}/versions/{id}     — Get a specific version
GET  /api/plc/{machine_code}/baseline          — Get active baseline
POST /api/plc/{machine_code}/baseline          — Establish a new baseline
POST /api/plc/{machine_code}/fingerprint       — Compute hash of a provided program
POST /api/plc/{machine_code}/check             — Full integrity check vs baseline
POST /api/plc/diff                             — Ad-hoc diff between two programs
GET  /api/plc/{machine_code}/demo-tamper       — Demo: run N7 interlock removal scenario
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query

from app.api.deps import get_current_user, require_engineer
from app.schemas.auth import UserProfileResponse
from app.schemas.plc import (
    PLCBaselineResponse,
    PLCDiffResult,
    PLCFingerprint,
    PLCIntegrityCheckResponse,
    PLCVersionResponse,
)
from app.services import machine_service, plc_service
from app.services.plc_engine import (
    calculate_plc_hash,
    canonicalize_plc_logic,
    compare_plc_logic,
    fingerprint,
)
from app.services.plc_demo import BASELINE_V17, TAMPERED_V17

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plc", tags=["PLC Logic Integrity"])


# ---------------------------------------------------------------------------
# Store PLC version
# ---------------------------------------------------------------------------


class StorePLCVersionRequest:
    pass


@router.post(
    "/{machine_code}/versions",
    response_model=PLCVersionResponse,
    status_code=201,
    summary="Store PLC logic version",
    description="Hash, canonicalize, and store a PLC logic version for a machine.",
)
async def store_version(
    machine_code: str,
    body: Dict[str, Any] = Body(..., description="PLC program JSON"),
    set_as_baseline: bool = Query(default=False),
    version_tag: str = Query(..., description="Version tag, e.g. 'v17', 'v18'"),
    description: str = Query(default=""),
    current_user: UserProfileResponse = Depends(require_engineer),
) -> PLCVersionResponse:
    machine = await machine_service.get_machine(machine_code)
    return await plc_service.store_plc_version(
        machine_id=machine.id,
        program=body,
        version_tag=version_tag,
        description=description,
        actor=current_user,
        set_as_baseline=set_as_baseline,
    )


@router.get(
    "/{machine_code}/versions",
    response_model=List[PLCVersionResponse],
    summary="List PLC versions for a machine",
)
async def list_versions(
    machine_code: str,
    _: UserProfileResponse = Depends(get_current_user),
) -> List[PLCVersionResponse]:
    machine = await machine_service.get_machine(machine_code)
    return await plc_service.list_plc_versions(machine.id)


@router.get(
    "/{machine_code}/versions/{version_id}",
    response_model=PLCVersionResponse,
    summary="Get specific PLC version",
)
async def get_version(
    machine_code: str,
    version_id: UUID,
    _: UserProfileResponse = Depends(get_current_user),
) -> PLCVersionResponse:
    return await plc_service.get_plc_version(version_id)


# ---------------------------------------------------------------------------
# Baseline management
# ---------------------------------------------------------------------------


@router.get(
    "/{machine_code}/baseline",
    response_model=Optional[PLCBaselineResponse],
    summary="Get active PLC baseline",
    description="Returns the currently active trusted baseline for the machine.",
)
async def get_baseline(
    machine_code: str,
    _: UserProfileResponse = Depends(get_current_user),
) -> Optional[PLCBaselineResponse]:
    machine = await machine_service.get_machine(machine_code)
    return await plc_service.get_active_baseline(machine.id)


# ---------------------------------------------------------------------------
# Fingerprint — compute hash of a submitted program (no DB required)
# ---------------------------------------------------------------------------


@router.post(
    "/{machine_code}/fingerprint",
    response_model=PLCFingerprint,
    summary="Compute PLC program fingerprint",
    description=(
        "Canonicalizes and computes the SHA-256 fingerprint of a provided PLC program JSON. "
        "No database write — pure computation."
    ),
)
async def compute_fingerprint(
    machine_code: str,
    body: Dict[str, Any] = Body(..., description="PLC program JSON"),
    _: UserProfileResponse = Depends(get_current_user),
) -> PLCFingerprint:
    return fingerprint(body)


# ---------------------------------------------------------------------------
# Full integrity check vs stored baseline
# ---------------------------------------------------------------------------


@router.post(
    "/{machine_code}/check",
    response_model=PLCIntegrityCheckResponse,
    summary="PLC integrity check",
    description=(
        "Computes the hash of the provided PLC program and compares it against "
        "the stored baseline. If hashes differ, performs a full semantic diff to "
        "identify added/removed/modified networks and safety violations."
    ),
)
async def integrity_check(
    machine_code: str,
    body: Dict[str, Any] = Body(..., description="Current PLC program JSON to verify"),
    _: UserProfileResponse = Depends(get_current_user),
) -> PLCIntegrityCheckResponse:
    machine = await machine_service.get_machine(machine_code)
    return await plc_service.quick_hash_check(
        machine_id=machine.id,
        machine_code=machine_code,
        program=body,
    )


# ---------------------------------------------------------------------------
# Ad-hoc semantic diff (no DB)
# ---------------------------------------------------------------------------


class DiffRequest:
    baseline: Dict[str, Any]
    current: Dict[str, Any]


@router.post(
    "/diff",
    response_model=PLCDiffResult,
    summary="Semantic diff between two PLC programs",
    description=(
        "Performs a semantic diff between a baseline and current PLC program. "
        "Detects added/removed networks, timer changes, setpoint changes, "
        "and interlock violations. No database required."
    ),
)
async def diff_programs(
    body: Dict[str, Any] = Body(
        ...,
        examples={
            "n7_tamper": {
                "summary": "N7 interlock removal",
                "value": {
                    "baseline": {"program_name": "CNC-01", "version": "v17", "networks": []},
                    "current":  {"program_name": "CNC-01", "version": "v18", "networks": []},
                },
            }
        },
    ),
    _: UserProfileResponse = Depends(get_current_user),
) -> PLCDiffResult:
    baseline = body.get("baseline")
    current = body.get("current")
    if not baseline or not current:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Body must contain 'baseline' and 'current' keys.")
    return compare_plc_logic(baseline, current)


# ---------------------------------------------------------------------------
# Demo: N7 interlock tamper scenario
# ---------------------------------------------------------------------------


@router.get(
    "/{machine_code}/demo-tamper",
    response_model=PLCDiffResult,
    summary="Demo: N7 interlock removal tamper detection",
    description=(
        "Runs the pre-built tamper detection demo for CNC-01.\n\n"
        "**Baseline (v17)**: Network N7 — SAFETY_OK → MACHINE_ENABLE interlock present.\n"
        "**Tampered**: N7 network removed from the PLC program.\n\n"
        "Expected result: PLC HASH MISMATCH → PLC LOGIC INTEGRITY FAILED → "
        "SAFETY INTERLOCK REMOVED alert."
    ),
)
async def demo_tamper_detection(
    machine_code: str,
    _: UserProfileResponse = Depends(get_current_user),
) -> PLCDiffResult:
    """
    Demonstrates the N7 safety interlock removal scenario.
    Uses pre-built CNC-01 v17 programs — no DB required.
    """
    return compare_plc_logic(BASELINE_V17, TAMPERED_V17)
