"""Thread-safe plant state shared between the control loop and Modbus server.

The control loop (one thread) writes measured/status fields and reads command
fields. The Modbus server (another thread) does the reverse. A single lock
guards all access, so neither side sees a half-updated snapshot.

Fields mirror the agreed Modbus map (src/modbus_map.py): level in mm + %,
inlet/outlet status, high-high + sensor alarms, manual-mode flag, the two HMI
command coils, and the three writable mm setpoints.

This object is also the choke point for the later SECURITY phase: every
external write lands here via the Modbus server, which is where write
validation, rate-limiting, and audit logging hook in.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

MODE_AUTO = 0      # Pi runs level logic
MODE_MANUAL = 1    # HMI drives pumps via command coils


@dataclass
class PlantState:
    # --- measured / reported (written by control loop) ---
    level_mm: int = 0            # current level in millimeters
    level_pct: int = 0           # current level 0-100 %
    inlet_on: bool = False       # inlet pump (Pump 1) actually energized
    outlet_on: bool = False      # outlet pump (Pump 2) actually energized
    alarm_highhigh: bool = False # level >= high-high threshold
    alarm_sensor: bool = False   # sensor reading invalid / lost

    # --- commands / mode (written by SCADA via Modbus coils) ---
    mode_manual: int = MODE_AUTO # MODE_AUTO | MODE_MANUAL
    inlet_cmd: bool = False      # HMI inlet command (honored in MANUAL)
    outlet_cmd: bool = False     # HMI outlet command (honored in MANUAL)

    # --- writable setpoints, millimeters (holding registers) ---
    low_setpoint_mm: int = 0     # auto: inlet ON below this
    high_setpoint_mm: int = 0    # auto: inlet OFF at/above this
    highhigh_mm: int = 0         # overflow guard: inlet OFF in ANY mode

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Context-manager access for compound reads/writes.
    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()
        return False
