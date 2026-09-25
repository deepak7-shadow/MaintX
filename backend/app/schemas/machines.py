"""
Pydantic schemas for machines and machine states.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MachineParameters(BaseModel):
    motor_speed_rpm: float = 3000.0
    temperature_limit_celsius: float = 80.0
    pressure_limit_bar: float = 5.0
    operating_mode: str = "AUTO"


class MachineStateSnapshot(BaseModel):
    motor_speed_rpm: Optional[float] = None
    temperature_celsius: Optional[float] = None
    pressure_bar: Optional[float] = None
    operating_mode: str = "AUTO"
    ip_address: Optional[str] = None
    plc_version: Optional[str] = None
    plc_hash: Optional[str] = None
    parameters: Dict[str, Any] = {}


class MachineCreateRequest(BaseModel):
    machine_code: str
    name: str
    machine_type: str = "5_AXIS_CNC"
    criticality: str = "HIGH"
    location: str
    status: str = "OPERATIONAL"
    plc_version: str = "v17"
    plc_integrity_status: str = "VERIFIED"
    firmware: str = "4.9.0"
    ip_address: str
    subnet: str = "255.255.255.0"
    gateway: Optional[str] = None
    firewall_configuration: Dict[str, Any] = Field(default_factory=lambda: {"mac_filtering": True, "inspection_mode": "STRICT"})
    safety_configuration: Dict[str, Any] = Field(default_factory=lambda: {"estop_circuit": "DUAL_CHANNEL_CAT4"})
    parameters: Dict[str, Any] = Field(default_factory=dict)


class MachineResponse(BaseModel):
    id: UUID
    machine_code: str
    name: str
    machine_type: str
    criticality: str
    location: str
    status: str
    plc_version: str
    plc_integrity_status: str
    firmware: str
    ip_address: str
    subnet: str
    gateway: str
    firewall_configuration: Dict[str, Any] = {}
    safety_configuration: Dict[str, Any] = {}
    parameters: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class MachineSummary(BaseModel):
    id: UUID
    machine_code: str
    name: str
    machine_type: str
    criticality: str
    status: str
    plc_version: str
    plc_integrity_status: str
    location: str


class MachineStateResponse(BaseModel):
    id: UUID
    machine_id: UUID
    recorded_at: datetime
    motor_speed_rpm: Optional[float] = None
    temperature_celsius: Optional[float] = None
    pressure_bar: Optional[float] = None
    operating_mode: str
    ip_address: Optional[str] = None
    plc_version: Optional[str] = None
    parameters: Dict[str, Any] = {}


class SimulatedState(BaseModel):
    """Live simulated telemetry for a machine."""
    machine_code: str
    motor_speed_rpm: float
    temperature_celsius: float
    pressure_bar: float
    operating_mode: str
    ip_address: str
    plc_version: str
    status: str
    maintenance_mode: bool
    timestamp: datetime
    alerts: list[str] = []
