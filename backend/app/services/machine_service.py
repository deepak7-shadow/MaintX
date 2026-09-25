"""
Machine service — CRUD operations and live state queries.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.db.client import get_supabase_client
from app.schemas.machines import (
    MachineCreateRequest,
    MachineResponse,
    MachineSummary,
    MachineStateResponse,
)

logger = logging.getLogger(__name__)


def _row_to_machine(row: dict) -> MachineResponse:
    return MachineResponse(
        id=row["id"],
        machine_code=row["machine_code"],
        name=row["name"],
        machine_type=row["machine_type"],
        criticality=row["criticality"],
        location=row["location"],
        status=row["status"],
        plc_version=row["plc_version"],
        plc_integrity_status=row["plc_integrity_status"],
        firmware=row["firmware"],
        ip_address=str(row["ip_address"]),
        subnet=row["subnet"],
        gateway=str(row["gateway"]),
        firewall_configuration=row.get("firewall_configuration") or {},
        safety_configuration=row.get("safety_configuration") or {},
        parameters=row.get("parameters") or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_machines() -> List[MachineSummary]:
    """Return summary list of all non-decommissioned machines."""
    client = get_supabase_client()
    try:
        result = (
            client.table("machines")
            .select("id, machine_code, name, machine_type, criticality, status, plc_version, plc_integrity_status, location")
            .neq("status", "DECOMMISSIONED")
            .order("machine_code")
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to list machines: %s", exc)
        raise HTTPException(status_code=503, detail="Database error listing machines.")

    return [
        MachineSummary(
            id=row["id"],
            machine_code=row["machine_code"],
            name=row["name"],
            machine_type=row["machine_type"],
            criticality=row["criticality"],
            status=row["status"],
            plc_version=row["plc_version"],
            plc_integrity_status=row["plc_integrity_status"],
            location=row["location"],
        )
        for row in (result.data or [])
    ]


async def get_machine(machine_code: str) -> MachineResponse:
    """Return full machine details by machine_code."""
    client = get_supabase_client()
    try:
        result = (
            client.table("machines")
            .select("*")
            .eq("machine_code", machine_code)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to get machine %s: %s", machine_code, exc)
        raise HTTPException(status_code=404, detail=f"Machine '{machine_code}' not found.")

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Machine '{machine_code}' not found.")

    return _row_to_machine(result.data)


async def get_machine_by_id(machine_id: UUID) -> MachineResponse:
    """Return full machine details by UUID."""
    client = get_supabase_client()
    try:
        result = (
            client.table("machines")
            .select("*")
            .eq("id", str(machine_id))
            .single()
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to get machine by id %s: %s", machine_id, exc)
        raise HTTPException(status_code=404, detail="Machine not found.")

    return _row_to_machine(result.data)


async def get_machine_states(machine_id: UUID, limit: int = 50) -> List[MachineStateResponse]:
    """Return recent machine state records."""
    client = get_supabase_client()
    try:
        result = (
            client.table("machine_states")
            .select("*")
            .eq("machine_id", str(machine_id))
            .order("recorded_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to get states for machine %s: %s", machine_id, exc)
        raise HTTPException(status_code=503, detail="Database error fetching machine states.")

    return [
        MachineStateResponse(
            id=row["id"],
            machine_id=row["machine_id"],
            recorded_at=row["recorded_at"],
            motor_speed_rpm=row.get("motor_speed_rpm"),
            temperature_celsius=row.get("temperature_celsius"),
            pressure_bar=row.get("pressure_bar"),
            operating_mode=row.get("operating_mode", "AUTO"),
            ip_address=str(row["ip_address"]) if row.get("ip_address") else None,
            plc_version=row.get("plc_version"),
            parameters=row.get("parameters") or {},
        )
        for row in (result.data or [])
    ]


async def set_machine_maintenance_mode(machine_id: UUID, enable: bool) -> None:
    """Toggle machine status between OPERATIONAL and MAINTENANCE_MODE."""
    client = get_supabase_client()
    new_status = "MAINTENANCE_MODE" if enable else "OPERATIONAL"
    try:
        client.table("machines").update({"status": new_status}).eq("id", str(machine_id)).execute()
    except Exception as exc:
        logger.error("Failed to set maintenance mode for %s: %s", machine_id, exc)
        raise HTTPException(status_code=503, detail="Failed to update machine status.")


async def create_machine(data: MachineCreateRequest) -> MachineResponse:
    """Insert a new machine into Supabase database."""
    client = get_supabase_client()
    row = data.model_dump()
    row["machine_code"] = row["machine_code"].strip().upper()

    if not row.get("gateway"):
        parts = row["ip_address"].strip().split(".")
        row["gateway"] = f"{parts[0]}.{parts[1]}.{parts[2]}.1" if len(parts) == 4 else "192.168.10.1"

    # Status mapping to match DB constraint
    if row["status"] == "MAINTENANCE":
        row["status"] = "MAINTENANCE_MODE"
    elif row["status"] == "CRITICAL":
        row["status"] = "COMPROMISED"
    elif row["status"] == "OFFLINE":
        row["status"] = "IDLE"

    try:
        result = client.table("machines").insert(row).execute()
    except Exception as exc:
        logger.error("Failed to create machine: %s", exc)
        raise HTTPException(status_code=400, detail=f"Failed to create machine: {exc}")

    if not result.data:
        raise HTTPException(status_code=500, detail="Machine insertion returned no data.")

    return _row_to_machine(result.data[0])

