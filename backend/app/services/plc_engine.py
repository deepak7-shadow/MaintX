"""
PLC Logic Engine — pure Python, no hardware required.

Implements three core operations:

  1. canonicalize_plc_logic(program)    → deterministic JSON string
  2. calculate_plc_hash(program)        → SHA-256 hex digest
  3. compare_plc_logic(baseline, curr)  → PLCDiffResult with semantic diff

The engine detects:
  - Added / removed / modified networks (rungs)
  - Timer preset changes
  - Setpoint changes (coil/contact tag changes)
  - Interlock changes (safety-critical rungs)

Design principle: the canonical form strips all runtime-state fields
(accumulator values, timestamps) and sorts everything deterministically
so that the same logic always produces the same hash.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.plc import (
    NetworkDiff,
    PLCDiffResult,
    PLCFingerprint,
    PLCNetwork,
    PLCProgram,
)

# ---------------------------------------------------------------------------
# Safety interlock tag prefixes / identifiers
# ---------------------------------------------------------------------------

# Networks whose network_id starts with one of these, or which are flagged
# safety_critical=True, are treated as safety interlocks.
SAFETY_NETWORK_PREFIXES = ("N7", "SAFETY", "ESTOP", "INTERLOCK", "SFT")

# Tags that indicate safety functions
SAFETY_TAG_PATTERNS = ("N7:", "SAFETY_", "ESTOP", "ENABLE", "GUARD", "STO")


def _is_safety_network(net: PLCNetwork) -> bool:
    """Return True if the network is classified as safety-critical."""
    if net.safety_critical:
        return True
    nid = net.network_id.upper()
    if any(nid.startswith(p) for p in SAFETY_NETWORK_PREFIXES):
        return True
    # Check tag names
    all_tags = (
        [c.tag for c in net.contacts]
        + [c.tag for c in net.coils]
        + [i.tag for i in net.instructions]
    )
    return any(
        any(pat in tag.upper() for pat in SAFETY_TAG_PATTERNS)
        for tag in all_tags
    )


# ---------------------------------------------------------------------------
# 1. Canonicalization
# ---------------------------------------------------------------------------


def _canonicalize_contact(c: dict) -> dict:
    """Return a minimal, sorted contact dict (no runtime fields)."""
    return {
        "tag": c.get("tag", ""),
        "contact_type": c.get("contact_type", "NORMALLY_OPEN"),
    }


def _canonicalize_coil(c: dict) -> dict:
    return {
        "tag": c.get("tag", ""),
        "coil_type": c.get("coil_type", "OUTPUT"),
    }


def _canonicalize_instruction(inst: dict) -> dict:
    """Strip accumulator (runtime) but keep preset (configuration)."""
    return {
        "instruction_type": inst.get("instruction_type", ""),
        "tag": inst.get("tag", ""),
        "preset": inst.get("preset"),    # keep — this is a setpoint
        "source_a": inst.get("source_a"),
        "source_b": inst.get("source_b"),
        "dest": inst.get("dest"),
    }


def _canonicalize_network(net: dict) -> dict:
    """Return a deterministic representation of a single rung."""
    return {
        "network_id": net.get("network_id", ""),
        "enabled": net.get("enabled", True),
        "safety_critical": net.get("safety_critical", False),
        # Sort contacts and coils by tag for determinism
        "contacts": sorted(
            [_canonicalize_contact(c) for c in net.get("contacts", [])],
            key=lambda x: x["tag"],
        ),
        "coils": sorted(
            [_canonicalize_coil(c) for c in net.get("coils", [])],
            key=lambda x: x["tag"],
        ),
        "instructions": [
            _canonicalize_instruction(i) for i in net.get("instructions", [])
        ],
    }


def canonicalize_plc_logic(program: dict | PLCProgram) -> str:
    """
    Convert a PLC program to a deterministic canonical JSON string.

    Rules:
    - Networks sorted by network_id
    - Contacts and coils sorted by tag
    - Runtime fields (accumulator, description, metadata, author) stripped
    - data_files included (N7 safety bits are setpoints)
    - Output is compact JSON with sorted keys
    """
    if isinstance(program, PLCProgram):
        program = program.model_dump()

    networks = program.get("networks", [])
    canonical = {
        "program_name": program.get("program_name", ""),
        "version": program.get("version", ""),
        "plc_type": program.get("plc_type", ""),
        "networks": sorted(
            [_canonicalize_network(n) for n in networks],
            key=lambda n: n["network_id"],
        ),
        "data_files": program.get("data_files", {}),
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# 2. SHA-256 fingerprint
# ---------------------------------------------------------------------------


def calculate_plc_hash(program: dict | PLCProgram) -> str:
    """
    Return the SHA-256 hex digest of the canonical PLC program representation.

    This is the tamper-detection fingerprint. Any change to logic, setpoints,
    interlocks, or enabled state will produce a different hash.
    """
    canonical = canonicalize_plc_logic(program)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint(program: dict | PLCProgram) -> PLCFingerprint:
    """Return a full PLCFingerprint with hash + metadata."""
    if isinstance(program, dict):
        prog_name = program.get("program_name", "unknown")
        version = program.get("version", "unknown")
    else:
        prog_name = program.program_name
        version = program.version
        program = program.model_dump()

    canonical = canonicalize_plc_logic(program)
    sha256 = hashlib.sha256(canonical.encode()).hexdigest()
    network_count = len(program.get("networks", []))

    return PLCFingerprint(
        program_name=prog_name,
        version=version,
        sha256=sha256,
        network_count=network_count,
        canonical_representation=canonical,
        computed_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 3. Semantic diff
# ---------------------------------------------------------------------------


def _diff_contacts(
    baseline_contacts: list, current_contacts: list, network_id: str
) -> List[dict]:
    """Return diff details for contact changes within a network."""
    details = []
    b_map = {c.get("tag"): c for c in baseline_contacts}
    c_map = {c.get("tag"): c for c in current_contacts}

    for tag, b_c in b_map.items():
        if tag not in c_map:
            details.append({"type": "CONTACT_REMOVED", "tag": tag, "network": network_id})
        elif b_c.get("contact_type") != c_map[tag].get("contact_type"):
            details.append({
                "type": "CONTACT_TYPE_CHANGED",
                "tag": tag,
                "network": network_id,
                "from": b_c.get("contact_type"),
                "to": c_map[tag].get("contact_type"),
            })
    for tag in c_map:
        if tag not in b_map:
            details.append({"type": "CONTACT_ADDED", "tag": tag, "network": network_id})
    return details


def _diff_instructions(
    baseline_insts: list, current_insts: list, network_id: str
) -> Tuple[List[dict], bool]:
    """
    Return diff details for instruction/timer changes.
    Returns (details_list, setpoint_changed).
    """
    details = []
    setpoint_changed = False
    b_map = {i.get("tag"): i for i in baseline_insts}
    c_map = {i.get("tag"): i for i in current_insts}

    for tag, b_i in b_map.items():
        if tag not in c_map:
            details.append({"type": "INSTRUCTION_REMOVED", "tag": tag, "network": network_id})
            continue
        c_i = c_map[tag]
        # Check preset (timer setpoints, counter presets)
        if b_i.get("preset") != c_i.get("preset"):
            setpoint_changed = True
            details.append({
                "type": "SETPOINT_CHANGED",
                "tag": tag,
                "network": network_id,
                "parameter": "preset",
                "from": b_i.get("preset"),
                "to": c_i.get("preset"),
            })
        # Check instruction type
        if b_i.get("instruction_type") != c_i.get("instruction_type"):
            details.append({
                "type": "INSTRUCTION_TYPE_CHANGED",
                "tag": tag,
                "network": network_id,
                "from": b_i.get("instruction_type"),
                "to": c_i.get("instruction_type"),
            })

    for tag in c_map:
        if tag not in b_map:
            details.append({"type": "INSTRUCTION_ADDED", "tag": tag, "network": network_id})

    return details, setpoint_changed


def compare_plc_logic(
    baseline: dict | PLCProgram,
    current: dict | PLCProgram,
) -> PLCDiffResult:
    """
    Perform a semantic diff between baseline and current PLC programs.

    Detects:
    - Added networks (rungs)
    - Removed networks (rungs) — CRITICAL if safety-critical
    - Modified networks: contact changes, coil changes, timer/setpoint changes
    - Interlock changes (N7 safety networks)

    Returns a PLCDiffResult with:
    - Hash comparison result
    - Per-network diff list
    - Safety violations list
    - Overall integrity_status
    """
    if isinstance(baseline, PLCProgram):
        baseline = baseline.model_dump()
    if isinstance(current, PLCProgram):
        current = current.model_dump()

    baseline_hash = calculate_plc_hash(baseline)
    current_hash = calculate_plc_hash(current)
    hash_match = baseline_hash == current_hash

    now = datetime.now(timezone.utc)

    # Index networks by network_id
    b_networks: Dict[str, dict] = {
        n["network_id"]: n for n in baseline.get("networks", [])
    }
    c_networks: Dict[str, dict] = {
        n["network_id"]: n for n in current.get("networks", [])
    }

    network_diffs: List[NetworkDiff] = []
    added_networks: List[str] = []
    removed_networks: List[str] = []
    modified_networks: List[str] = []
    safety_violations: List[str] = []

    # --- Removed networks ---
    for nid, b_net in b_networks.items():
        if nid not in c_networks:
            is_safety = _is_safety_network(PLCNetwork(**b_net))
            severity = "CRITICAL" if is_safety else "WARNING"
            removed_networks.append(nid)

            viol_msg = None
            if is_safety:
                viol_msg = (
                    f"SAFETY INTERLOCK REMOVED: network {nid} "
                    f"({b_net.get('description', '')}) has been removed from the PLC program."
                )
                safety_violations.append(viol_msg)

            network_diffs.append(NetworkDiff(
                network_id=nid,
                change_type="REMOVED",
                description=(
                    f"Network {nid} REMOVED"
                    + (f" — SAFETY INTERLOCK: {b_net.get('description', '')}" if is_safety else "")
                ),
                severity=severity,
                safety_critical=is_safety,
                details={
                    "baseline_description": b_net.get("description", ""),
                    "contacts": [c.get("tag") for c in b_net.get("contacts", [])],
                    "coils": [c.get("tag") for c in b_net.get("coils", [])],
                    "violation": viol_msg,
                },
            ))

    # --- Added networks ---
    for nid, c_net in c_networks.items():
        if nid not in b_networks:
            is_safety = _is_safety_network(PLCNetwork(**c_net))
            added_networks.append(nid)
            network_diffs.append(NetworkDiff(
                network_id=nid,
                change_type="ADDED",
                description=f"Network {nid} ADDED ({c_net.get('description', '')})",
                severity="WARNING" if is_safety else "INFO",
                safety_critical=is_safety,
                details={
                    "description": c_net.get("description", ""),
                    "contacts": [c.get("tag") for c in c_net.get("contacts", [])],
                    "coils": [c.get("tag") for c in c_net.get("coils", [])],
                },
            ))

    # --- Modified networks ---
    for nid in b_networks:
        if nid not in c_networks:
            continue  # already handled as removed

        b_net = b_networks[nid]
        c_net = c_networks[nid]

        # Canonicalize both for comparison
        b_canon = _canonicalize_network(b_net)
        c_canon = _canonicalize_network(c_net)

        if b_canon == c_canon:
            continue  # identical

        is_safety = _is_safety_network(PLCNetwork(**b_net))
        modified_networks.append(nid)
        details: Dict[str, Any] = {"network_id": nid}

        # Enabled state change
        if b_net.get("enabled", True) != c_net.get("enabled", True):
            details["enabled_changed"] = {
                "from": b_net.get("enabled", True),
                "to": c_net.get("enabled", True),
            }
            if is_safety and not c_net.get("enabled", True):
                viol = f"SAFETY INTERLOCK DISABLED: network {nid} has been disabled."
                safety_violations.append(viol)
                details["violation"] = viol

        # Contact diffs
        contact_diffs = _diff_contacts(
            b_canon.get("contacts", []), c_canon.get("contacts", []), nid
        )
        if contact_diffs:
            details["contact_changes"] = contact_diffs
            if is_safety:
                for cd in contact_diffs:
                    if cd["type"] in ("CONTACT_REMOVED", "CONTACT_TYPE_CHANGED"):
                        viol = f"INTERLOCK CHANGE in {nid}: {cd}"
                        safety_violations.append(viol)

        # Coil diffs
        b_coil_tags = {c["tag"] for c in b_canon.get("coils", [])}
        c_coil_tags = {c["tag"] for c in c_canon.get("coils", [])}
        if b_coil_tags != c_coil_tags:
            details["coil_changes"] = {
                "removed": list(b_coil_tags - c_coil_tags),
                "added": list(c_coil_tags - b_coil_tags),
            }
            if is_safety:
                for removed_tag in b_coil_tags - c_coil_tags:
                    viol = f"INTERLOCK OUTPUT REMOVED in {nid}: coil {removed_tag} removed."
                    safety_violations.append(viol)

        # Instruction / setpoint diffs
        inst_diffs, setpoint_changed = _diff_instructions(
            b_canon.get("instructions", []), c_canon.get("instructions", []), nid
        )
        if inst_diffs:
            details["instruction_changes"] = inst_diffs
            if setpoint_changed and is_safety:
                viol = f"SETPOINT CHANGED in safety network {nid}: {inst_diffs}"
                safety_violations.append(viol)

        severity = "CRITICAL" if (is_safety and safety_violations) else ("WARNING" if is_safety else "INFO")

        network_diffs.append(NetworkDiff(
            network_id=nid,
            change_type="MODIFIED",
            description=f"Network {nid} MODIFIED" + (" — SAFETY CRITICAL" if is_safety else ""),
            severity=severity,
            safety_critical=is_safety,
            details=details,
        ))

    # ---------------------------------------------------------------------------
    # Overall integrity status
    # ---------------------------------------------------------------------------
    total_changes = len(added_networks) + len(removed_networks) + len(modified_networks)

    if hash_match:
        integrity_status = "VERIFIED"
        integrity_message = (
            f"PLC LOGIC INTEGRITY VERIFIED — hash match confirmed. "
            f"Version: {baseline.get('version')}. No changes detected."
        )
    elif safety_violations:
        integrity_status = "INTEGRITY_FAILED"
        integrity_message = (
            f"PLC LOGIC INTEGRITY FAILED — "
            f"PLC HASH MISMATCH detected. "
            f"{len(safety_violations)} SAFETY VIOLATION(S): "
            + " | ".join(safety_violations)
        )
    else:
        integrity_status = "HASH_MISMATCH"
        integrity_message = (
            f"PLC HASH MISMATCH — logic changed between "
            f"version {baseline.get('version')} and {current.get('version')}. "
            f"{total_changes} network(s) changed."
        )

    return PLCDiffResult(
        baseline_version=baseline.get("version", "unknown"),
        current_version=current.get("version", "unknown"),
        baseline_hash=baseline_hash,
        current_hash=current_hash,
        hash_match=hash_match,
        integrity_status=integrity_status,
        integrity_message=integrity_message,
        network_diffs=network_diffs,
        added_networks=added_networks,
        removed_networks=removed_networks,
        modified_networks=modified_networks,
        safety_violations=safety_violations,
        total_changes=total_changes,
        analysed_at=now,
    )
