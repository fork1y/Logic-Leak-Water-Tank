"""Async Modbus TCP server backed by live PlantState.

Each Modbus block is a thin adapter over the shared PlantState, so a SCADA
poll always reflects the real plant and a SCADA write lands in the control
loop on its next tick.

Writes (coils + holding regs) pass through the `modbus.audit` logger — the
hook the SECURITY phase extends with validation / rate-limiting / source
checks.

Baseline note: this is intentionally plain Modbus TCP — no auth, no
encryption. That is realistic ICS behavior and is what makes the injection /
replay attacks succeed. Hardening goes *around* it, not inside the protocol.
"""
from __future__ import annotations

import logging

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

from . import modbus_map as M
from .config import Config
from .state import MODE_AUTO, MODE_MANUAL, PlantState

log = logging.getLogger("modbus")
audit = logging.getLogger("modbus.audit")


class _StateBlock(ModbusSequentialDataBlock):
    """Maps one Modbus block type onto PlantState via getter/setter tables."""

    def __init__(self, state: PlantState, size: int, readers, writers=None):
        self.state = state
        self.readers = readers          # {address: callable() -> int}
        self.writers = writers or {}    # {address: callable(int)}
        super().__init__(0, [0] * size)

    def getValues(self, address, count=1):  # noqa: N802 (pymodbus API)
        base = address                  # zero_mode=True -> address is 0-based
        out = []
        with self.state:
            for i in range(count):
                reader = self.readers.get(base + i)
                out.append(int(reader()) if reader else 0)
        return out

    def setValues(self, address, values):  # noqa: N802 (pymodbus API)
        base = address                  # zero_mode=True -> address is 0-based
        with self.state:
            for i, v in enumerate(values):
                addr = base + i
                writer = self.writers.get(addr)
                if writer:
                    audit.info("WRITE block_addr=%d value=%s", addr, v)
                    writer(int(v))
                else:
                    audit.warning("WRITE to read-only/undefined addr=%d ignored", addr)


def _u16(v: int) -> int:
    """Clamp to an unsigned 16-bit register range."""
    return max(0, min(65535, int(v)))


def build_context(state: PlantState) -> ModbusServerContext:
    s = state

    # ---- Coils (RW): HMI commands + mode ----
    coil_readers = {
        M.COIL_INLET_CMD: lambda: s.inlet_cmd,
        M.COIL_OUTLET_CMD: lambda: s.outlet_cmd,
        M.COIL_MODE_MANUAL: lambda: s.mode_manual == MODE_MANUAL,
    }
    coil_writers = {
        M.COIL_INLET_CMD: lambda v: setattr(s, "inlet_cmd", bool(v)),
        M.COIL_OUTLET_CMD: lambda v: setattr(s, "outlet_cmd", bool(v)),
        M.COIL_MODE_MANUAL: lambda v: setattr(s, "mode_manual", MODE_MANUAL if v else MODE_AUTO),
    }
    coils = _StateBlock(s, M.NUM_COILS, coil_readers, coil_writers)

    # ---- Discrete inputs (RO): status + alarms ----
    di_readers = {
        M.DI_INLET_STATE: lambda: s.inlet_on,
        M.DI_OUTLET_STATE: lambda: s.outlet_on,
        M.DI_ALARM_HIGHHIGH: lambda: s.alarm_highhigh,
        M.DI_ALARM_SENSOR: lambda: s.alarm_sensor,
    }
    discretes = _StateBlock(s, M.NUM_DISCRETE, di_readers)

    # ---- Holding registers (RW): level readback + setpoints ----
    hr_readers = {
        M.HR_LEVEL_MM: lambda: s.level_mm,
        M.HR_LEVEL_PCT: lambda: s.level_pct,
        M.HR_LOW_SETPOINT_MM: lambda: s.low_setpoint_mm,
        M.HR_HIGH_SETPOINT_MM: lambda: s.high_setpoint_mm,
        M.HR_HIGHHIGH_MM: lambda: s.highhigh_mm,
    }
    hr_writers = {
        # LEVEL_* are overwritten by the control loop each tick; a client write
        # is transient (good for demonstrating a spoofed reading that snaps back)
        M.HR_LEVEL_MM: lambda v: setattr(s, "level_mm", _u16(v)),
        M.HR_LEVEL_PCT: lambda v: setattr(s, "level_pct", max(0, min(100, v))),
        M.HR_LOW_SETPOINT_MM: lambda v: setattr(s, "low_setpoint_mm", _u16(v)),
        M.HR_HIGH_SETPOINT_MM: lambda v: setattr(s, "high_setpoint_mm", _u16(v)),
        M.HR_HIGHHIGH_MM: lambda v: setattr(s, "highhigh_mm", _u16(v)),
    }
    holdings = _StateBlock(s, M.NUM_HOLDING_REGS, hr_readers, hr_writers)

    slave = ModbusSlaveContext(
        di=discretes, co=coils, ir=None, hr=holdings, zero_mode=True
    )
    return ModbusServerContext(slaves=slave, single=True)


async def run_server(cfg: Config, state: PlantState) -> None:
    context = build_context(state)
    log.info("Modbus TCP server listening on %s:%d (unit %d)",
             cfg.modbus.host, cfg.modbus.port, cfg.modbus.unit_id)
    await StartAsyncTcpServer(
        context=context,
        address=(cfg.modbus.host, cfg.modbus.port),
    )
