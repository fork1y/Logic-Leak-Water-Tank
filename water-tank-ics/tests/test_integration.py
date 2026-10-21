"""End-to-end integration test (software): Mango <-> Pi over one PlantState.

Wires the Modbus server blocks and the Controller to the SAME PlantState, then
simulates a Mango command cycle through the Modbus blocks and checks the
controller reacts and the status reads back — the full chain:

    Mango writes coil  ->  PlantState  ->  controller tick  ->  pump
                        ->  PlantState  ->  Mango reads discrete input

The only thing not exercised here is the TCP socket itself (needs real
pymodbus on the Pi; see tools/check_modbus.py).

    PYTHONPATH=tests/_stubs:. python3 tests/test_integration.py
"""
from __future__ import annotations

import sys

import RPi.GPIO as GPIO  # stubbed

import src.config as cfgmod
import src.modbus_map as M
from src.state import PlantState, MODE_MANUAL, MODE_AUTO
from src.controller import Controller
from src.modbus_server import build_context
from src.sensor import Reading

GPIO.setmode(GPIO.BCM)
RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")


class FakeSensor:
    def __init__(self, level_mm, valid=True):
        self.level_mm, self.valid = level_mm, valid
    def read_level(self):
        return Reading(self.valid, self.level_mm, int(self.level_mm / 250 * 100), 10.0)


def build(level_mm, valid=True):
    cfg = cfgmod.load("config.yaml")
    st = PlantState()
    ctrl = Controller(cfg, st)
    ctrl.sensor = FakeSensor(level_mm, valid)
    ctrl.cfg.control.min_switch_interval_s = 0.0   # disable hardening for tests
    ctrl.cfg.control.max_jump_mm = 1_000_000
    slave = build_context(st).slaves      # same st the controller uses
    return st, ctrl, slave


# protocol address = logical + 1 (zero_mode=False)
def W(block, logical, vals): block.setValues(logical, vals)
def R(block, logical, n=1): return block.getValues(logical, n)


print("Integration: Mango commands a pump in MANUAL mode")
st, ctrl, slave = build(level_mm=120)
# Mango flips to MANUAL and commands the inlet ON
W(slave.co, M.COIL_MODE_MANUAL, [1])
W(slave.co, M.COIL_INLET_CMD, [1])
check("Mango write landed in state (MANUAL)", st.mode_manual == MODE_MANUAL)
ctrl._tick()                              # Pi acts on the command
check("controller energized inlet", ctrl.pumps.pump1.is_on is True)
check("Mango reads INLET_STATE=1 back", R(slave.di, M.DI_INLET_STATE)[0] == 1)
# Mango commands inlet OFF
W(slave.co, M.COIL_INLET_CMD, [0])
ctrl._tick()
check("inlet OFF after command cleared", R(slave.di, M.DI_INLET_STATE)[0] == 0)

print("\nIntegration: HIGH-HIGH alarm surfaces to Mango even on a manual fill")
st, ctrl, slave = build(level_mm=245)     # >= highhigh 238
W(slave.co, M.COIL_MODE_MANUAL, [1])
W(slave.co, M.COIL_INLET_CMD, [1])        # attacker/operator forces fill
ctrl._tick()
check("inlet blocked by high-high", R(slave.di, M.DI_INLET_STATE)[0] == 0)
check("Mango reads ALARM_HIGHHIGH=1", R(slave.di, M.DI_ALARM_HIGHHIGH)[0] == 1)

print("\nIntegration: Mango tunes a setpoint live and AUTO responds")
st, ctrl, slave = build(level_mm=120)     # AUTO by default
W(slave.co, M.COIL_MODE_MANUAL, [0])      # ensure AUTO
# with low=75 high=200, level 120 holds inlet state; raise low above level -> fill
W(slave.hr, M.HR_LOW_SETPOINT_MM, [150])  # now 120 < 150 -> should fill
ctrl._tick()
check("AUTO fills after low setpoint raised above level",
      R(slave.di, M.DI_INLET_STATE)[0] == 1)
check("Mango reads back the new low setpoint", R(slave.hr, M.HR_LOW_SETPOINT_MM)[0] == 150)

print("\n" + "=" * 56)
fails = [n for n, ok in RESULTS if not ok]
if fails:
    print(f"RESULT: {len(RESULTS)-len(fails)}/{len(RESULTS)} passed, FAILED: {fails}")
    sys.exit(1)
print(f"RESULT: ALL {len(RESULTS)} INTEGRATION CHECKS PASSED (Mango<->Pi loop)")
