"""
Machine simulator — generates deterministic, realistic telemetry.

The simulator produces live-like state snapshots for demo machines
without requiring actual PLC hardware.  Values follow a sinusoidal
baseline with bounded Gaussian noise so they look realistic in charts.
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timezone
from typing import Any, Dict

from app.schemas.machines import SimulatedState


class MachineSimulator:
    """
    Stateless, deterministic simulator for a single machine.

    Given a machine's configuration, it produces a `SimulatedState`
    snapshot that represents what the machine's telemetry would look like
    at the current moment.
    """

    # Simulation constants
    TEMP_BASELINE = 45.0   # °C idle temperature
    TEMP_AMPLITUDE = 12.0  # oscillation amplitude
    TEMP_PERIOD_S = 300    # 5-minute thermal cycle

    PRESSURE_BASELINE = 3.2  # bar idle
    PRESSURE_AMPLITUDE = 0.6

    NOISE_SEED_OFFSET = 42

    def __init__(
        self,
        machine_code: str,
        plc_version: str,
        parameters: Dict[str, Any],
        ip_address: str,
        status: str,
    ):
        self.machine_code = machine_code
        self.plc_version = plc_version
        self.parameters = parameters
        self.ip_address = ip_address
        self.status = status

        # Derive a stable per-machine seed from the machine code
        self._seed = int(hashlib.md5(machine_code.encode()).hexdigest()[:8], 16)

    def _noise(self, amplitude: float, t: float, phase: float = 0.0) -> float:
        """Deterministic pseudo-noise using time + per-machine seed."""
        rng = random.Random(int(t * 1000) ^ self._seed ^ int(phase * 1000))
        return rng.gauss(0, amplitude * 0.1)

    def snapshot(self) -> SimulatedState:
        """Generate a telemetry snapshot for the current moment."""
        now = datetime.now(timezone.utc)
        t = now.timestamp()

        maintenance_mode = self.status == "MAINTENANCE_MODE"
        motor_speed: float = self.parameters.get("motor_speed_rpm", 3000.0)
        temp_limit: float = self.parameters.get("temperature_limit_celsius", 80.0)
        pressure_limit: float = self.parameters.get("pressure_limit_bar", 5.0)
        operating_mode: str = self.parameters.get("operating_mode", "AUTO")

        # During maintenance, motor is at 0
        if maintenance_mode:
            simulated_rpm = 0.0
            simulated_temp = self.TEMP_BASELINE + self._noise(2.0, t)
            simulated_pressure = 0.0
        else:
            # Sinusoidal RPM variation ±2% around set point
            rpm_variation = math.sin(2 * math.pi * t / 120) * (motor_speed * 0.02)
            simulated_rpm = motor_speed + rpm_variation + self._noise(motor_speed * 0.005, t)
            simulated_rpm = max(0.0, simulated_rpm)

            # Temperature rises with load, follows 5-min thermal cycle
            temp_load = (simulated_rpm / 3000.0) * 28.0
            temp_cycle = math.sin(2 * math.pi * t / self.TEMP_PERIOD_S) * self.TEMP_AMPLITUDE
            simulated_temp = (
                self.TEMP_BASELINE + temp_load + temp_cycle + self._noise(1.5, t, 1.0)
            )

            # Pressure follows load
            simulated_pressure = (
                self.PRESSURE_BASELINE
                + (simulated_rpm / 3000.0) * self.PRESSURE_AMPLITUDE
                + self._noise(0.05, t, 2.0)
            )

        # Round for realism
        simulated_rpm = round(simulated_rpm, 1)
        simulated_temp = round(simulated_temp, 2)
        simulated_pressure = round(simulated_pressure, 3)

        # Build alerts
        alerts: list[str] = []
        if simulated_temp > temp_limit * 0.90:
            alerts.append(f"WARNING: Temperature {simulated_temp}°C approaching limit ({temp_limit}°C)")
        if simulated_temp > temp_limit:
            alerts.append(f"CRITICAL: Temperature {simulated_temp}°C EXCEEDS limit ({temp_limit}°C)!")
        if simulated_pressure > pressure_limit * 0.90:
            alerts.append(f"WARNING: Pressure {simulated_pressure} bar approaching limit ({pressure_limit} bar)")
        if maintenance_mode:
            alerts.append("MAINTENANCE_MODE ACTIVE — machine is locked for maintenance.")

        return SimulatedState(
            machine_code=self.machine_code,
            motor_speed_rpm=simulated_rpm,
            temperature_celsius=simulated_temp,
            pressure_bar=simulated_pressure,
            operating_mode=operating_mode if not maintenance_mode else "MAINTENANCE",
            ip_address=self.ip_address,
            plc_version=self.plc_version,
            status=self.status,
            maintenance_mode=maintenance_mode,
            timestamp=now,
            alerts=alerts,
        )


def simulate_machine(machine_data: Dict[str, Any]) -> SimulatedState:
    """
    Convenience function: build simulator from a machine DB row dict
    and return a snapshot.
    """
    sim = MachineSimulator(
        machine_code=machine_data["machine_code"],
        plc_version=machine_data["plc_version"],
        parameters=machine_data.get("parameters") or {},
        ip_address=str(machine_data.get("ip_address", "")),
        status=machine_data.get("status", "OPERATIONAL"),
    )
    return sim.snapshot()
