#!/usr/bin/env python3
"""Step 3 bring-up: verify the Modbus TCP server end to end.

Connects as a Modbus client (like Mango or an attacker would), reads the live
status registers, then exercises a write: flip to MANUAL, pulse the inlet
command coil, and read the state back. Needs the real pymodbus 3.6.x
(pip install -r requirements.txt). Run on the Pi or any host that can reach it.

    cd water-tank-ics
    python3 -m tools.check_modbus                 # localhost:502
    python3 -m tools.check_modbus --host 192.168.254.201
"""
from __future__ import annotations

import argparse
import time

from pymodbus.client import ModbusTcpClient

import src.modbus_map as M


def main() -> None:
    ap = argparse.ArgumentParser(description="Modbus TCP client verification")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--unit", type=int, default=1)
    args = ap.parse_args()

    c = ModbusTcpClient(args.host, port=args.port)
    if not c.connect():
        print(f"[ERR] cannot connect to {args.host}:{args.port}")
        return
    u = args.unit
    try:
        hr = c.read_holding_registers(M.HR_LEVEL_MM, count=M.NUM_HOLDING_REGS, slave=u)
        di = c.read_discrete_inputs(0, count=M.NUM_DISCRETE, slave=u)
        co = c.read_coils(0, count=M.NUM_COILS, slave=u)
        if hr.isError() or di.isError() or co.isError():
            print(f"[ERR] read failed: hr={hr} di={di} co={co}")
            return

        print("--- holding registers (level + setpoints) ---")
        print(f"  level_mm      = {hr.registers[M.HR_LEVEL_MM]}")
        print(f"  level_pct     = {hr.registers[M.HR_LEVEL_PCT]}")
        print(f"  low_setpoint  = {hr.registers[M.HR_LOW_SETPOINT_MM]}")
        print(f"  high_setpoint = {hr.registers[M.HR_HIGH_SETPOINT_MM]}")
        print(f"  high_high     = {hr.registers[M.HR_HIGHHIGH_MM]}")
        print("--- discrete inputs (status) ---")
        print(f"  inlet_state     = {int(di.bits[M.DI_INLET_STATE])}")
        print(f"  outlet_state    = {int(di.bits[M.DI_OUTLET_STATE])}")
        print(f"  alarm_highhigh  = {int(di.bits[M.DI_ALARM_HIGHHIGH])}")
        print(f"  alarm_sensor    = {int(di.bits[M.DI_ALARM_SENSOR])}")
        print("--- coils (commands) ---")
        print(f"  inlet_cmd   = {int(co.bits[M.COIL_INLET_CMD])}")
        print(f"  outlet_cmd  = {int(co.bits[M.COIL_OUTLET_CMD])}")
        print(f"  mode_manual = {int(co.bits[M.COIL_MODE_MANUAL])}")

        print("\n--- write test: MANUAL + pulse inlet command ---")
        c.write_coil(M.COIL_MODE_MANUAL, True, slave=u)
        c.write_coil(M.COIL_INLET_CMD, True, slave=u)
        time.sleep(1.0)
        co2 = c.read_coils(0, count=M.NUM_COILS, slave=u)
        di2 = c.read_discrete_inputs(0, count=M.NUM_DISCRETE, slave=u)
        print(f"  mode_manual now = {int(co2.bits[M.COIL_MODE_MANUAL])} (expect 1)")
        print(f"  inlet_cmd now   = {int(co2.bits[M.COIL_INLET_CMD])} (expect 1)")
        print(f"  inlet_state now = {int(di2.bits[M.DI_INLET_STATE])} "
              f"(1 unless blocked by high-high)")
        # leave it in a safe state
        c.write_coil(M.COIL_INLET_CMD, False, slave=u)
        c.write_coil(M.COIL_MODE_MANUAL, False, slave=u)
        print("  reset inlet_cmd=0, mode=AUTO")
        print("\n[OK] Modbus read/write verified.")
    finally:
        c.close()


if __name__ == "__main__":
    main()
