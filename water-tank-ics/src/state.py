"""Thread-safe plant state shared between the control loop and Modbus server.

The control loop (one thread) writes sensor/status fields and reads command
fields. The Modbus server (another thread) does the reverse. A single lock
guards all access, so neither side sees a half-updated snapshot.

This object is also the natural choke point for the later SECURITY phase:
every external command write lands through the Modbus block writers, which is
where write validation, rate-limiting, and audit logging hook in.

Levels are stored in MILLIMETERS because Modbus registers are 16-bit integers
with no decimals; the sensor maps distance -> mm using the tank geometry.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

log = logging.getLogger("state")

MODE_AUTO = 0
MODE_MANUAL = 1


@dataclass
class PlantState:
    # --- measured / reported (written by the control loop) ---
    level_mm: int = 0
    level_pct: int = 0
    inlet_on: bool = False
    outlet_on: bool = False
    alarm_highhigh: bool = False     # level reached high-high (overflow guard)
    alarm_sensor: bool = False       # sensor reading lost / out of range

    # --- commands / setpoints (written by the HMI via Modbus) ---
    mode_manual: int = MODE_AUTO     # MODE_AUTO | MODE_MANUAL
    inlet_cmd: bool = False          # honored only in MANUAL mode
    outlet_cmd: bool = False         # honored only in MANUAL mode
    low_setpoint_mm: int = 44        # AUTO: inlet ON below this
    high_setpoint_mm: int = 94       # AUTO: inlet OFF at/above this
    highhigh_mm: int = 134           # overflow guard: inlet OFF in ANY mode

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Context-manager access for compound reads/writes from the control loop.
    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()
        return False
