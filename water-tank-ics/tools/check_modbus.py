#!/usr/bin/env python3
"""Bring-up: Modbus client against the RUNNING server.

Start the controller first (python -m src.main), then run this from the Pi
(localhost) or from Mango/attacker box (--host <pi-ip>). It:
  - reads holding registers (level mm/%, setpoints),
  - reads discrete-input status + alarm bits,
  - round-trips a coil write: flips MODE_MANUAL on and back, confirming the
    server accepted it (this settles the zero-base / off-by-one question).

Requires pymodbus on THIS machine too:  pip install "pymodbus>=3.6,<4.0"

    python3 -m tools.check_modbus                      # localhost:502
    python3 -m tools.check_modbus --host 192.168.1.37  # Pi over the network
    python3 -m tools.check_modbus --port 5020          # non-root server port
"""
from __future__ import annotations

import argparse
import sys

from pymodbus.client import ModbusTcpClient

from src import modbus_map as M


def _ok(label: str, cond: bool) -> bool:
    print(f"  [{'OK ' if cond else 'ERR'}] {label}")
    return cond


def main() -> int:
    ap = argparse.ArgumentParser(description="Modbus client verification")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--unit", type=int, default=1)
    args = ap.parse_args()

    client = ModbusTcpClient(args.host, port=args.port)
    if not client.connect():
        print(f"could not connect to {args.host}:{args.port} — is src.main running?")
        return 2
    print(f"connected to {args.host}:{args.port} (unit {args.unit})\n")

    kw = {"slave": args.unit}   # pymodbus 3.x uses `slave` for unit id
    passed = True
    try:
        print("Holding registers (level + setpoints):")
        hrr = client.read_holding_registers(M.HR_LEVEL_MM, count=M.NUM_HOLDING_REGS, **kw)
        if not _ok("read holding registers", not hrr.isError()):
            passed = False
        else:
            h = hrr.registers
            print(f"       level={h[M.HR_LEVEL_MM]} mm / {h[M.HR_LEVEL_PCT]} %  "
                  f"low={h[M.HR_LOW_SETPOINT_MM]}  high={h[M.HR_HIGH_SETPOINT_MM]}  "
                  f"highhigh={h[M.HR_HIGHHIGH_MM]} (mm)")
            passed &= _ok("level_pct in 0..100", 0 <= h[M.HR_LEVEL_PCT] <= 100)

        print("Discrete inputs (status + alarms):")
        dr = client.read_discrete_inputs(M.DI_INLET_STATE, count=M.NUM_DISCRETE, **kw)
        if not _ok("read discrete inputs", not dr.isError()):
            passed = False
        else:
            b = dr.bits
            print(f"       inlet={b[M.DI_INLET_STATE]}  outlet={b[M.DI_OUTLET_STATE]}  "
                  f"HIGHHIGH={b[M.DI_ALARM_HIGHHIGH]}  SENSOR={b[M.DI_ALARM_SENSOR]}")

        print("Coil round-trip (MODE_MANUAL on -> verify -> off):")
        passed &= _ok("write MODE_MANUAL=1", not client.write_coil(M.COIL_MODE_MANUAL, True, **kw).isError())
        rc = client.read_coils(M.COIL_MODE_MANUAL, count=1, **kw)
        passed &= _ok("MODE_MANUAL reads back 1 (addressing correct)",
                      not rc.isError() and rc.bits[0] is True)
        client.write_coil(M.COIL_MODE_MANUAL, False, **kw)   # restore AUTO
        rc2 = client.read_coils(M.COIL_MODE_MANUAL, count=1, **kw)
        passed &= _ok("restored to AUTO (reads 0)", not rc2.isError() and rc2.bits[0] is False)
    finally:
        client.close()

    print()
    if passed:
        print("RESULT: Modbus integration verified — Mango can poll + command this.")
        return 0
    print("RESULT: a check failed. If reads look shifted by one index, the "
          "zero_mode / address offset in modbus_server.py needs adjusting.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
