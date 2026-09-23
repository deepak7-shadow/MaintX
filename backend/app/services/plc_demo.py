"""
Pre-built demo PLC programs for CNC-01.

These are the programs used by the tamper detection demo endpoint and tests.
They model a realistic Allen-Bradley SLC 500 program for a CNC milling machine.

BASELINE_V17 — The trusted, safe baseline:
  - N7 network present: SAFETY_OK → MACHINE_ENABLE (safety interlock)
  - N1: E-stop circuit
  - N2: Spindle motor control (3000 RPM setpoint)
  - N3: Thermal protection (80°C limit)
  - N4: Pressure monitoring (5.0 bar setpoint)
  - N5: Coolant pump control
  - N6: Axis drive enable

TAMPERED_V17 — Same program with N7 (safety interlock) removed:
  - N7 network MISSING — MACHINE_ENABLE no longer gated by SAFETY_OK
  - This represents an attacker bypassing the safety interlock

Expected diff result:
  - integrity_status: INTEGRITY_FAILED
  - safety_violations: ["SAFETY INTERLOCK REMOVED: network N7 ..."]
"""

# ---------------------------------------------------------------------------
# CNC-01 Baseline PLC Program — version v17
# ---------------------------------------------------------------------------

BASELINE_V17 = {
    "program_name": "CNC-01",
    "version": "v17",
    "plc_type": "Allen-Bradley SLC 500",
    "description": "CNC-01 Precision 5-Axis Milling Machine — Production Logic v17",
    "author": "TECH-042",
    "networks": [
        {
            "network_id": "N1",
            "description": "E-Stop Circuit — Dual Channel Safety",
            "safety_critical": True,
            "enabled": True,
            "contacts": [
                {"tag": "I:0/0", "contact_type": "NORMALLY_CLOSED", "description": "E-Stop PB1"},
                {"tag": "I:0/1", "contact_type": "NORMALLY_CLOSED", "description": "E-Stop PB2"},
                {"tag": "B3:0/0", "contact_type": "NORMALLY_OPEN", "description": "Reset latch"},
            ],
            "coils": [
                {"tag": "O:0/0", "coil_type": "OUTPUT", "description": "E-Stop relay K1"},
            ],
            "instructions": [],
        },
        {
            "network_id": "N2",
            "description": "Spindle Motor Speed Control — 3000 RPM",
            "safety_critical": False,
            "enabled": True,
            "contacts": [
                {"tag": "B3:0/1", "contact_type": "NORMALLY_OPEN", "description": "Motor enable bit"},
                {"tag": "O:0/0", "contact_type": "NORMALLY_OPEN", "description": "E-Stop OK"},
            ],
            "coils": [
                {"tag": "O:0/1", "coil_type": "OUTPUT", "description": "VFD run signal"},
            ],
            "instructions": [
                {
                    "instruction_type": "MOV",
                    "tag": "N7:10",
                    "source_a": "3000",
                    "dest": "N7:10",
                    "preset": 3000,
                    "description": "Motor speed setpoint 3000 RPM",
                },
            ],
        },
        {
            "network_id": "N3",
            "description": "Thermal Protection — 80°C Overtemperature Limit",
            "safety_critical": True,
            "enabled": True,
            "contacts": [
                {"tag": "I:1/0", "contact_type": "NORMALLY_OPEN", "description": "Temp sensor signal"},
            ],
            "coils": [
                {"tag": "B3:0/2", "coil_type": "OUTPUT", "description": "Overtemperature flag"},
            ],
            "instructions": [
                {
                    "instruction_type": "CMP",
                    "tag": "T4:0",
                    "source_a": "I:1/0",
                    "source_b": "80",
                    "preset": 80,
                    "description": "Compare temperature against 80°C limit",
                },
            ],
        },
        {
            "network_id": "N4",
            "description": "Hydraulic Pressure Monitor — 5.0 bar Setpoint",
            "safety_critical": True,
            "enabled": True,
            "contacts": [
                {"tag": "I:1/1", "contact_type": "NORMALLY_OPEN", "description": "Pressure transducer"},
            ],
            "coils": [
                {"tag": "B3:0/3", "coil_type": "OUTPUT", "description": "Low pressure alarm"},
            ],
            "instructions": [
                {
                    "instruction_type": "CMP",
                    "tag": "T4:1",
                    "source_a": "I:1/1",
                    "source_b": "5.0",
                    "preset": 5.0,
                    "description": "Compare pressure against 5.0 bar setpoint",
                },
            ],
        },
        {
            "network_id": "N5",
            "description": "Coolant Pump — Cycle Timer 30s ON / 10s OFF",
            "safety_critical": False,
            "enabled": True,
            "contacts": [
                {"tag": "O:0/0", "contact_type": "NORMALLY_OPEN", "description": "E-Stop OK"},
                {"tag": "T4:2/DN", "contact_type": "NORMALLY_CLOSED", "description": "Coolant timer done"},
            ],
            "coils": [
                {"tag": "O:0/2", "coil_type": "OUTPUT", "description": "Coolant pump relay"},
            ],
            "instructions": [
                {
                    "instruction_type": "TON",
                    "tag": "T4:2",
                    "preset": 30000,
                    "description": "Coolant on-timer 30s",
                },
            ],
        },
        {
            "network_id": "N6",
            "description": "Axis Drive Enable — All axes clear",
            "safety_critical": False,
            "enabled": True,
            "contacts": [
                {"tag": "O:0/0", "contact_type": "NORMALLY_OPEN", "description": "E-Stop OK"},
                {"tag": "B3:0/2", "contact_type": "NORMALLY_CLOSED", "description": "Overtemp NOT active"},
                {"tag": "B3:0/3", "contact_type": "NORMALLY_CLOSED", "description": "Low pressure NOT active"},
            ],
            "coils": [
                {"tag": "O:0/3", "coil_type": "OUTPUT", "description": "Axis drive enable"},
            ],
            "instructions": [],
        },
        # ── N7 SAFETY INTERLOCK ─────────────────────────────────────────────
        # This is the critical network. SAFETY_OK (N7:0/0) must be TRUE
        # for MACHINE_ENABLE (N7:1/0) to energise.
        # Removing this network bypasses all safety gating.
        {
            "network_id": "N7",
            "description": "MASTER SAFETY INTERLOCK — SAFETY_OK → MACHINE_ENABLE",
            "safety_critical": True,
            "enabled": True,
            "contacts": [
                {"tag": "N7:0/0", "contact_type": "NORMALLY_OPEN", "description": "SAFETY_OK — all safety conditions met"},
                {"tag": "B3:0/2", "contact_type": "NORMALLY_CLOSED", "description": "Overtemperature NOT active"},
                {"tag": "B3:0/3", "contact_type": "NORMALLY_CLOSED", "description": "Low pressure NOT active"},
            ],
            "coils": [
                {"tag": "N7:1/0", "coil_type": "OUTPUT", "description": "MACHINE_ENABLE — gates all motion"},
            ],
            "instructions": [],
        },
    ],
    "data_files": {
        "N7": {
            "description": "Safety Integer File",
            "N7:0": {"description": "Safety status word", "N7:0/0": "SAFETY_OK"},
            "N7:1": {"description": "Enable status word", "N7:1/0": "MACHINE_ENABLE"},
            "N7:10": {"description": "Motor speed setpoint", "value": 3000, "unit": "RPM"},
        },
        "B3": {"description": "Bit storage file"},
        "T4": {"description": "Timer file"},
        "I": {"description": "Input image file"},
        "O": {"description": "Output image file"},
    },
    "metadata": {
        "last_modified": "2026-09-23T00:00:00Z",
        "safety_category": "PLd_CAT3",
        "cycle_time_ms": 10,
        "plc_firmware": "FRN 10.0",
    },
}


# ---------------------------------------------------------------------------
# CNC-01 TAMPERED Program — N7 safety interlock REMOVED
# ---------------------------------------------------------------------------
# This represents what an attacker or rogue insider would produce:
# the N7 network has been silently removed, meaning MACHINE_ENABLE
# is no longer gated by SAFETY_OK.  The machine can now run even when
# safety conditions are NOT met.
# ---------------------------------------------------------------------------

TAMPERED_V17 = {
    "program_name": "CNC-01",
    "version": "v17",   # Same version label — attacker disguising the change
    "plc_type": "Allen-Bradley SLC 500",
    "description": "CNC-01 Precision 5-Axis Milling Machine — Production Logic v17",
    "author": "TECH-042",
    "networks": [
        # N1 through N6 identical to baseline
        {
            "network_id": "N1",
            "description": "E-Stop Circuit — Dual Channel Safety",
            "safety_critical": True,
            "enabled": True,
            "contacts": [
                {"tag": "I:0/0", "contact_type": "NORMALLY_CLOSED", "description": "E-Stop PB1"},
                {"tag": "I:0/1", "contact_type": "NORMALLY_CLOSED", "description": "E-Stop PB2"},
                {"tag": "B3:0/0", "contact_type": "NORMALLY_OPEN", "description": "Reset latch"},
            ],
            "coils": [
                {"tag": "O:0/0", "coil_type": "OUTPUT", "description": "E-Stop relay K1"},
            ],
            "instructions": [],
        },
        {
            "network_id": "N2",
            "description": "Spindle Motor Speed Control — 3000 RPM",
            "safety_critical": False,
            "enabled": True,
            "contacts": [
                {"tag": "B3:0/1", "contact_type": "NORMALLY_OPEN", "description": "Motor enable bit"},
                {"tag": "O:0/0", "contact_type": "NORMALLY_OPEN", "description": "E-Stop OK"},
            ],
            "coils": [
                {"tag": "O:0/1", "coil_type": "OUTPUT", "description": "VFD run signal"},
            ],
            "instructions": [
                {
                    "instruction_type": "MOV",
                    "tag": "N7:10",
                    "source_a": "3000",
                    "dest": "N7:10",
                    "preset": 3000,
                    "description": "Motor speed setpoint 3000 RPM",
                },
            ],
        },
        {
            "network_id": "N3",
            "description": "Thermal Protection — 80°C Overtemperature Limit",
            "safety_critical": True,
            "enabled": True,
            "contacts": [
                {"tag": "I:1/0", "contact_type": "NORMALLY_OPEN", "description": "Temp sensor signal"},
            ],
            "coils": [
                {"tag": "B3:0/2", "coil_type": "OUTPUT", "description": "Overtemperature flag"},
            ],
            "instructions": [
                {
                    "instruction_type": "CMP",
                    "tag": "T4:0",
                    "source_a": "I:1/0",
                    "source_b": "80",
                    "preset": 80,
                    "description": "Compare temperature against 80°C limit",
                },
            ],
        },
        {
            "network_id": "N4",
            "description": "Hydraulic Pressure Monitor — 5.0 bar Setpoint",
            "safety_critical": True,
            "enabled": True,
            "contacts": [
                {"tag": "I:1/1", "contact_type": "NORMALLY_OPEN", "description": "Pressure transducer"},
            ],
            "coils": [
                {"tag": "B3:0/3", "coil_type": "OUTPUT", "description": "Low pressure alarm"},
            ],
            "instructions": [
                {
                    "instruction_type": "CMP",
                    "tag": "T4:1",
                    "source_a": "I:1/1",
                    "source_b": "5.0",
                    "preset": 5.0,
                    "description": "Compare pressure against 5.0 bar setpoint",
                },
            ],
        },
        {
            "network_id": "N5",
            "description": "Coolant Pump — Cycle Timer 30s ON / 10s OFF",
            "safety_critical": False,
            "enabled": True,
            "contacts": [
                {"tag": "O:0/0", "contact_type": "NORMALLY_OPEN", "description": "E-Stop OK"},
                {"tag": "T4:2/DN", "contact_type": "NORMALLY_CLOSED", "description": "Coolant timer done"},
            ],
            "coils": [
                {"tag": "O:0/2", "coil_type": "OUTPUT", "description": "Coolant pump relay"},
            ],
            "instructions": [
                {
                    "instruction_type": "TON",
                    "tag": "T4:2",
                    "preset": 30000,
                    "description": "Coolant on-timer 30s",
                },
            ],
        },
        {
            "network_id": "N6",
            "description": "Axis Drive Enable — All axes clear",
            "safety_critical": False,
            "enabled": True,
            "contacts": [
                {"tag": "O:0/0", "contact_type": "NORMALLY_OPEN", "description": "E-Stop OK"},
                {"tag": "B3:0/2", "contact_type": "NORMALLY_CLOSED", "description": "Overtemp NOT active"},
                {"tag": "B3:0/3", "contact_type": "NORMALLY_CLOSED", "description": "Low pressure NOT active"},
            ],
            "coils": [
                {"tag": "O:0/3", "coil_type": "OUTPUT", "description": "Axis drive enable"},
            ],
            "instructions": [],
        },
        # ── N7 REMOVED ── N7 is not present in this program ─────────────────
        # MACHINE_ENABLE (N7:1/0) is now ungated — SAFETY_OK no longer required
    ],
    "data_files": {
        "N7": {
            "description": "Safety Integer File",
            "N7:0": {"description": "Safety status word", "N7:0/0": "SAFETY_OK"},
            "N7:1": {"description": "Enable status word", "N7:1/0": "MACHINE_ENABLE"},
            "N7:10": {"description": "Motor speed setpoint", "value": 3000, "unit": "RPM"},
        },
        "B3": {"description": "Bit storage file"},
        "T4": {"description": "Timer file"},
        "I": {"description": "Input image file"},
        "O": {"description": "Output image file"},
    },
    "metadata": {
        "last_modified": "2026-09-23T00:00:00Z",
        "safety_category": "PLd_CAT3",
        "cycle_time_ms": 10,
        "plc_firmware": "FRN 10.0",
    },
}
