"""
Machines API router.

Endpoints
---------
GET  /api/machines                        — List all machines (summary)
GET  /api/machines/{machine_code}         — Full machine details
GET  /api/machines/{machine_code}/states  — Recent telemetry state records
GET  /api/machines/{machine_code}/live    — Live simulated telemetry snapshot
GET  /api/machines/{machine_code}/maintenance-status — Current maintenance mode status
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, require_engineer
from app.schemas.auth import UserProfileResponse
from app.schemas.machines import MachineResponse, MachineSummary, MachineStateResponse, SimulatedState
from app.schemas.maintenance import MaintenanceModeStatus
from app.services import machine_service, maintenance_service
from app.services.simulator import simulate_machine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/machines", tags=["Machines"])


@router.get(
    "",
    response_model=List[MachineSummary],
    summary="List all machines",
    description="Returns a summary list of all registered (non-decommissioned) machines.",
)
async def list_machines(
    _: UserProfileResponse = Depends(get_current_user),
) -> List[MachineSummary]:
    return await machine_service.list_machines()


@router.get(
    "/{machine_code}",
    response_model=MachineResponse,
    summary="Get machine details",
    description="Returns full details for a machine, including network config, parameters, and PLC info.",
)
async def get_machine(
    machine_code: str,
    _: UserProfileResponse = Depends(get_current_user),
) -> MachineResponse:
    return await machine_service.get_machine(machine_code)


@router.get(
    "/{machine_code}/states",
    response_model=List[MachineStateResponse],
    summary="Get machine state history",
    description="Returns recent recorded telemetry snapshots for a machine.",
)
async def get_machine_states(
    machine_code: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: UserProfileResponse = Depends(get_current_user),
) -> List[MachineStateResponse]:
    machine = await machine_service.get_machine(machine_code)
    return await machine_service.get_machine_states(machine.id, limit=limit)


@router.get(
    "/{machine_code}/live",
    response_model=SimulatedState,
    summary="Live simulated telemetry",
    description=(
        "Returns a live-simulated telemetry snapshot for the machine. "
        "Values are deterministically generated from the machine's current configuration "
        "and the current timestamp — no hardware required."
    ),
)
async def get_live_state(
    machine_code: str,
    _: UserProfileResponse = Depends(get_current_user),
) -> SimulatedState:
    machine = await machine_service.get_machine(machine_code)
    return simulate_machine(machine.model_dump())


@router.get(
    "/{machine_code}/maintenance-status",
    response_model=MaintenanceModeStatus,
    summary="Maintenance mode status",
    description="Returns whether the machine is in maintenance mode and details of any active session.",
)
async def maintenance_status(
    machine_code: str,
    _: UserProfileResponse = Depends(get_current_user),
) -> MaintenanceModeStatus:
    machine = await machine_service.get_machine(machine_code)
    return await maintenance_service.get_maintenance_mode_status(machine.id)
