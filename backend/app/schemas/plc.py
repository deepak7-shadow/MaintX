"""
Pydantic schemas for the software PLC simulator.

PLC logic is represented as structured JSON — no real hardware required.
A "network" is one rung on the PLC ladder diagram.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# PLC element types
# ---------------------------------------------------------------------------


class ContactType(str, Enum):
    NORMALLY_OPEN = "NORMALLY_OPEN"       # |  |
    NORMALLY_CLOSED = "NORMALLY_CLOSED"   # |/|


class CoilType(str, Enum):
    OUTPUT = "OUTPUT"                     # ( )
    LATCH = "LATCH"                       # (L)
    UNLATCH = "UNLATCH"                   # (U)


class InstructionType(str, Enum):
    TIMER_ON = "TON"         # Timer On-Delay
    TIMER_OFF = "TOF"        # Timer Off-Delay
    COUNTER_UP = "CTU"       # Count Up
    COUNTER_DOWN = "CTD"     # Count Down
    MOVE = "MOV"             # Move value
    COMPARE = "CMP"          # Compare
    MATH = "MATH"            # Math operation


# ---------------------------------------------------------------------------
# PLC network building blocks
# ---------------------------------------------------------------------------


class PLCContact(BaseModel):
    """A contact on a rung (normally open / closed)."""
    tag: str = Field(..., description="Tag address, e.g. N7:0/0, I:0/0")
    contact_type: ContactType = ContactType.NORMALLY_OPEN
    description: Optional[str] = None


class PLCCoil(BaseModel):
    """An output coil on a rung."""
    tag: str
    coil_type: CoilType = CoilType.OUTPUT
    description: Optional[str] = None


class PLCInstruction(BaseModel):
    """A function-block instruction (timer, counter, math, etc.)."""
    instruction_type: InstructionType
    tag: str
    preset: Optional[float] = None      # preset value (e.g. timer preset in ms)
    accumulator: Optional[float] = None
    source_a: Optional[str] = None      # source tag A
    source_b: Optional[str] = None      # source tag B
    dest: Optional[str] = None          # destination tag
    description: Optional[str] = None


class PLCNetwork(BaseModel):
    """
    A single rung in a PLC ladder program.
    Each network has a unique id, human-readable description,
    contacts (inputs), coils (outputs), and optional function instructions.
    """
    network_id: str = Field(..., description="Unique rung ID, e.g. 'N7', 'N1', 'RUNG_010'")
    description: str = ""
    contacts: List[PLCContact] = []
    coils: List[PLCCoil] = []
    instructions: List[PLCInstruction] = []
    enabled: bool = True
    safety_critical: bool = False


class PLCProgram(BaseModel):
    """
    A complete PLC program — a list of networks with metadata.
    This is the structured JSON representation of the PLC logic.
    """
    program_name: str
    version: str
    plc_type: str = "Allen-Bradley SLC 500"
    description: str = ""
    author: str = ""
    networks: List[PLCNetwork] = []
    data_files: Dict[str, Any] = {}     # N7, B3, T4, C5, etc.
    metadata: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Fingerprint and diff schemas
# ---------------------------------------------------------------------------


class PLCFingerprint(BaseModel):
    """SHA-256 fingerprint of a canonicalized PLC program."""
    program_name: str
    version: str
    sha256: str
    network_count: int
    canonical_representation: str       # The normalized JSON string that was hashed
    computed_at: datetime


class NetworkDiff(BaseModel):
    """Describes a change to a single PLC network rung."""
    network_id: str
    change_type: str   # ADDED | REMOVED | MODIFIED
    description: str
    severity: str      # INFO | WARNING | CRITICAL
    safety_critical: bool = False
    details: Dict[str, Any] = {}


class PLCDiffResult(BaseModel):
    """
    Semantic diff between two PLC programs.
    The diff engine detects: added/removed/modified networks,
    timer preset changes, setpoint changes, and interlock changes.
    """
    baseline_version: str
    current_version: str
    baseline_hash: str
    current_hash: str
    hash_match: bool
    integrity_status: str   # VERIFIED | HASH_MISMATCH | LOGIC_TAMPERED | INTEGRITY_FAILED
    integrity_message: str
    network_diffs: List[NetworkDiff] = []
    added_networks: List[str] = []
    removed_networks: List[str] = []
    modified_networks: List[str] = []
    safety_violations: List[str] = []
    total_changes: int = 0
    analysed_at: datetime


# ---------------------------------------------------------------------------
# DB-backed version / baseline schemas
# ---------------------------------------------------------------------------


class PLCVersionResponse(BaseModel):
    id: UUID
    machine_id: UUID
    version_tag: str
    description: str
    program_json: Dict[str, Any]
    sha256_hash: str
    is_baseline: bool
    is_active: bool
    created_by: UUID
    created_at: datetime


class PLCBaselineResponse(BaseModel):
    id: UUID
    machine_id: UUID
    version_id: UUID
    version_tag: str
    sha256_hash: str
    network_count: int
    established_by: UUID
    established_at: datetime
    notes: Optional[str] = None


class PLCIntegrityCheckResponse(BaseModel):
    machine_code: str
    machine_id: UUID
    checked_at: datetime
    baseline_version: str
    current_version: str
    baseline_hash: str
    current_hash: str
    integrity_status: str
    integrity_message: str
    diff: Optional[PLCDiffResult] = None
