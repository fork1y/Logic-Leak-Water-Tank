"""Per-module test suite — exercises each component individually against the
agreed integration spec (mm units, AUTO/MANUAL, high-high + sensor alarms),
using stubbed RPi.GPIO + pymodbus.

Run from the project root (no pip installs needed):

    PYTHONPATH=tests/_stubs:. python3 tests/test_modules.py

The real pymodbus TCP socket is tested separately on the Pi via
tools/check_modbus.py (PyPI is blocked in the build sandbox).
"""
from __future__ import annotations

import copy
import sys

import RPi.GPIO as GPIO  # stubbed

import src.config as cfgmod
import src.modbus_map as M
from src.config import SensorCfg
from src.pumps import Pump  # noqa: F401
from src.state import PlantState, MODE_AUTO, MODE_MANUAL
from src.controller import Controller
from src.modbus_server import build_context

RESULTS: list[tuple[str, bool]] = []
_section = ""


def section(name: str) -> None:
    global _section
    _section = name
    print(f"\n{name}")


def check(name: str, cond: bool) -> None:
    RESULTS.append((f"{_section} :: {name}", bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")


GPIO.setmode(GPIO.BCM)


# ---------------------------------------------------------------- config ----
def test_config():
    section("config.py — load + validation (mm)")
    cfg = cfgmod.load("config.yaml")
    check("loads config.yaml", cfg is not None)
    check("span_mm = (empty-full)*10 = 264", cfg.sensor.span_mm == 264)
    check("low<high<=highhigh<=span",
          cfg.control.low_setpoint_mm < cfg.control.high_setpoint_mm
          <= cfg.control.highhigh_mm <= cfg.sensor.span_mm)

    bad = copy.deepcopy(cfg); bad.control.low_setpoint_mm = 210  # low>high
    try:
        cfgmod._validate(bad); check("rejects low>=high", False)
    except ValueError:
        check("rejects low>=high", True)

    bad2 = copy.deepcopy(cfg); bad2.control.highhigh_mm = 999   # > span
    try:
        cfgmod._validate(bad2); check("rejects highhigh>span", False)
    except ValueError:
        check("rejects highhigh>span", True)

    bad3 = copy.deepcopy(cfg); bad3.control.mode_on_boot = "SIDEWAYS"
    try:
        cfgmod._validate(bad3); check("rejects bad mode_on_boot", False)
    except ValueError:
        check("rejects bad mode_on_boot", True)

    bad4 = copy.deepcopy(cfg); bad4.pumps.pump2.relay_pin = bad4.pumps.pump1.relay_pin
    try:
        cfgmod._validate(bad4); check("rejects duplicate pins", False)
    except ValueError:
        check("rejects duplicate pins", True)


# ---------------------------------------------------------------- sensor ----
def test_sensor():
    section("sensor.py — distance(cm) -> level(mm,%)")
    from src.sensor import UltrasonicSensor
    sc = SensorCfg(trig_pin=17, echo_pin=27, tank_empty_cm=30.0,
                   tank_full_cm=5.0, samples=5, timeout_s=0.04)  # span 250mm
    s = UltrasonicSensor(sc)

    s.read_distance_cm = lambda: 30.0          # empty
    r = s.read_level(); check("30cm -> 0mm/0%", r.valid and r.level_mm == 0 and r.level_pct == 0)
    s.read_distance_cm = lambda: 5.0           # full
    r = s.read_level(); check("5cm -> 250mm/100%", r.valid and r.level_mm == 250 and r.level_pct == 100)
    s.read_distance_cm = lambda: 17.5          # mid
    r = s.read_level(); check("17.5cm -> 125mm/50%", r.level_mm == 125 and r.level_pct == 50)
    s.read_distance_cm = lambda: None          # lost echo
    r = s.read_level(); check("lost echo -> invalid", r.valid is False)
    s.read_distance_cm = lambda: 80.0          # way out of range
    r = s.read_level(); check("out-of-range -> invalid (sensor alarm)", r.valid is False)

    section("sensor.py — median filter rejects outlier")
    vals = iter([10.0, 10.2, 99.0, 10.1, 9.9])
    s2 = UltrasonicSensor(sc); s2._read_distance_once = lambda: next(vals)
    check("median ~10.1 not 99", abs(s2.read_distance_cm() - 10.1) < 0.001)


# ----------------------------------------------------------------- pumps ----
def test_pumps():
    section("pumps.py — active-low polarity + bank")
    p = Pump("inlet", pin=23, active_low=True)
    check("init OFF -> HIGH", GPIO.input(23) == GPIO.HIGH)
    p.set(True); check("ON -> LOW", GPIO.input(23) == GPIO.LOW)
    p.set(False); check("OFF -> HIGH", GPIO.input(23) == GPIO.HIGH)
    p2 = Pump("x", pin=25, active_low=False)
    p2.set(True); check("active-high ON -> HIGH", GPIO.input(25) == GPIO.HIGH)
    p2.set(False)


# ----------------------------------------------------------------- state ----
def test_state():
    section("state.py — defaults + lock")
    st = PlantState()
    check("boot AUTO", st.mode_manual == MODE_AUTO)
    with st as s:
        s.level_mm = 123
    check("write persisted under lock", st.level_mm == 123)
    check("lock released", st._lock.acquire(blocking=False)); st._lock.release()


# ------------------------------------------------------------ controller ----
class FakeSensor:
    def __init__(self, valid, level_mm):
        self.valid, self.level_mm = valid, level_mm
    def read_level(self):
        from src.sensor import Reading
        pct = int(round(self.level_mm / 250 * 100))
        return Reading(self.valid, self.level_mm, pct, 10.0)


def _ctrl(level_mm, valid=True):
    cfg = cfgmod.load("config.yaml")
    st = PlantState()
    c = Controller(cfg, st)
    c.sensor = FakeSensor(valid, level_mm)
    # disable noise hardening for the pure-logic tests (they jump levels fast)
    c.cfg.control.min_switch_interval_s = 0.0
    c.cfg.control.max_jump_mm = 1_000_000
    return cfg, st, c


def test_controller():
    section("controller.py — AUTO hysteresis (low=44 high=94)")
    cfg, st, c = _ctrl(30)          # below low
    c._tick(); check("30mm (<44) -> inlet ON", c.pumps.pump1.is_on is True)
    check("AUTO -> outlet OFF", c.pumps.pump2.is_on is False)
    check("publishes level_mm", st.level_mm == 30)
    c.sensor = FakeSensor(True, 100); c._tick()
    check("100mm (>=94) -> inlet OFF", c.pumps.pump1.is_on is False)
    c.sensor = FakeSensor(True, 70); c._tick()
    check("70mm (between, was OFF) -> holds OFF", c.pumps.pump1.is_on is False)

    section("controller.py — MANUAL honors command coils")
    cfg, st, c = _ctrl(70)
    with st as s:
        s.mode_manual = MODE_MANUAL; s.inlet_cmd = True; s.outlet_cmd = True
    c._tick()
    check("MANUAL inlet_cmd -> inlet ON", c.pumps.pump1.is_on is True)
    check("MANUAL outlet_cmd -> outlet ON", c.pumps.pump2.is_on is True)

    section("controller.py — HIGH-HIGH forces inlet OFF even in MANUAL")
    cfg, st, c = _ctrl(140)         # >= highhigh(134)
    with st as s:
        s.mode_manual = MODE_MANUAL; s.inlet_cmd = True
    c._tick()
    check("inlet forced OFF at high-high", c.pumps.pump1.is_on is False)
    check("ALARM_HIGHHIGH set", st.alarm_highhigh is True)

    section("controller.py — DRY-RUN guard forces outlet OFF")
    cfg, st, c = _ctrl(10)          # <= dry_min(20)
    with st as s:
        s.mode_manual = MODE_MANUAL; s.outlet_cmd = True
    c._tick()
    check("outlet forced OFF when near-empty", c.pumps.pump2.is_on is False)

    section("controller.py — SENSOR invalid -> fail-safe + alarm")
    cfg, st, c = _ctrl(30); c._tick()           # prime inlet ON
    c.sensor = FakeSensor(False, 0); c._tick()
    check("both pumps OFF on invalid", not c.pumps.pump1.is_on and not c.pumps.pump2.is_on)
    check("ALARM_SENSOR set", st.alarm_sensor is True)


# -------------------------------------------------------------- modbus ------
def test_modbus_wiring():
    section("modbus_server.py — register read/write wiring (new map)")
    st = PlantState()
    slave = build_context(st).slaves
    co, di, hr = slave.co, slave.di, slave.hr

    def R(b, a, n=1): return b.getValues(a, n)
    def W(b, a, v): b.setValues(a, v)

    W(co, M.COIL_MODE_MANUAL, [1]); check("coil MODE_MANUAL -> state MANUAL", st.mode_manual == MODE_MANUAL)
    W(co, M.COIL_INLET_CMD, [1]); check("coil INLET_CMD write+read", st.inlet_cmd is True and R(co, M.COIL_INLET_CMD)[0] == 1)
    W(co, M.COIL_OUTLET_CMD, [1]); check("coil OUTLET_CMD write", st.outlet_cmd is True)

    W(hr, M.HR_LOW_SETPOINT_MM, [80]); check("HR low setpoint write", st.low_setpoint_mm == 80)
    W(hr, M.HR_HIGHHIGH_MM, [240]); check("HR highhigh write", st.highhigh_mm == 240)

    st.level_mm = 152; check("HR LEVEL_MM reflects state", R(hr, M.HR_LEVEL_MM)[0] == 152)
    st.level_pct = 61; check("HR LEVEL_PCT reflects state", R(hr, M.HR_LEVEL_PCT)[0] == 61)
    st.inlet_on = True; check("DI INLET_STATE reflects state", R(di, M.DI_INLET_STATE)[0] == 1)
    st.alarm_highhigh = True; check("DI ALARM_HIGHHIGH reflects state", R(di, M.DI_ALARM_HIGHHIGH)[0] == 1)
    st.alarm_sensor = True; check("DI ALARM_SENSOR reflects state", R(di, M.DI_ALARM_SENSOR)[0] == 1)


def test_noise_hardening():
    from src.sensor import Reading
    import time as _t
    section("controller.py — spike filter (rejects relay noise)")
    c = Controller(cfgmod.load("config.yaml"), PlantState())  # defaults 5.0s / 40mm
    def f(mm): return c._filter_level(Reading(True, mm, 0, 10.0))
    check("first reading accepted", f(100) == 100)
    check("small change accepted", f(110) == 110)
    check("big jump held as noise", f(200) == 110)
    check("jump accepted once confirmed", f(202) == 202)
    check("lost echo -> None", c._filter_level(Reading(False, 0, 0, 0.0)) is None)

    section("controller.py — dwell (anti-chatter)")
    c._inlet_last_change = _t.monotonic()          # just switched
    check("change within interval is blocked", c._dwell_inlet(True) is False)
    c._inlet_last_change = _t.monotonic() - 10      # long ago
    check("change allowed after interval", c._dwell_inlet(True) is True)


def main():
    test_config(); test_sensor(); test_pumps(); test_state()
    test_controller(); test_modbus_wiring(); test_noise_hardening()
    passed = sum(1 for _, ok in RESULTS if ok); total = len(RESULTS)
    print("\n" + "=" * 60)
    fails = [n for n, ok in RESULTS if not ok]
    if fails:
        print(f"RESULT: {passed}/{total} passed, {len(fails)} FAILED:")
        for n in fails:
            print("   -", n)
        return 1
    print(f"RESULT: ALL {total} CHECKS PASSED (6 modules, new integration spec)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
