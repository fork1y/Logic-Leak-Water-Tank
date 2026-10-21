"""Control state machine: AUTO level logic + MANUAL (HMI) override.

Runs in its own thread. Every cycle it:
  1. reads the tank level (mm + %) from the sensor,
  2. decides pump outputs from mode + HMI command coils,
  3. applies safety overrides that hold in BOTH modes,
  4. drives the relays and publishes status + alarms to shared PlantState.

Modes:
  AUTO   (mode_manual=0): Pi runs hysteresis on the mm setpoints taken from the
                          holding registers, so the HMI can tune them live.
                          Inlet fills; outlet stays off.
  MANUAL (mode_manual=1): Pi ignores level logic and drives inlet/outlet from
                          the INLET_CMD / OUTLET_CMD coils.

Safety (applied last, override everything, both modes):
  - HIGH-HIGH overflow : level >= highhigh  -> inlet forced OFF (+ alarm)
  - DRY-RUN guard      : level <= dry_min   -> outlet forced OFF
  - SENSOR invalid     : reading lost/out of range -> both pumps OFF (+ alarm)
"""
from __future__ import annotations

import logging
import threading
import time

from .config import Config
from .pumps import PumpBank
from .sensor import UltrasonicSensor
from .state import MODE_AUTO, MODE_MANUAL, PlantState

log = logging.getLogger("controller")


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


class Controller(threading.Thread):
    def __init__(self, cfg: Config, state: PlantState):
        super().__init__(name="controller", daemon=True)
        self.cfg = cfg
        self.state = state
        self.sensor = UltrasonicSensor(cfg.sensor)
        self.pumps = PumpBank(cfg.pumps)          # pump1=inlet, pump2=outlet
        self.span_mm = cfg.sensor.span_mm
        self._stop = threading.Event()
        # noise hardening state
        self._last_level_mm: int | None = None    # last ACCEPTED level
        self._pending_mm: int | None = None        # candidate awaiting confirmation
        self._inlet_last_change = 0.0              # time.monotonic of last inlet switch
        # seed mode + setpoints from config
        with state:
            state.mode_manual = MODE_MANUAL if cfg.control.mode_on_boot == "MANUAL" else MODE_AUTO
            state.low_setpoint_mm = cfg.control.low_setpoint_mm
            state.high_setpoint_mm = cfg.control.high_setpoint_mm
            state.highhigh_mm = cfg.control.highhigh_mm

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        log.info("control loop started (%.2fs period)", self.cfg.control.loop_interval_s)
        try:
            while not self._stop.is_set():
                self._tick()
                time.sleep(self.cfg.control.loop_interval_s)
        finally:
            self.pumps.all_off()
            log.info("control loop stopped; pumps forced OFF")

    # ------------------------------------------------------------------ #
    def _filter_level(self, r):
        """Spike rejection: a single wild jump (relay/pump noise) is ignored;
        a real move is accepted only once a second reading confirms it.
        Returns the level_mm to act on, or None if we have no trusted level."""
        if not r.valid:
            return None
        raw = r.level_mm
        maxj = self.cfg.control.max_jump_mm
        if self._last_level_mm is None:
            self._last_level_mm = raw
            return raw
        if abs(raw - self._last_level_mm) <= maxj:
            self._last_level_mm = raw            # normal, small change -> accept
            self._pending_mm = None
            return raw
        # big jump from the accepted level -> suspect noise; need confirmation
        if self._pending_mm is not None and abs(raw - self._pending_mm) <= maxj:
            self._last_level_mm = raw            # two readings agree -> real move
            self._pending_mm = None
            return raw
        self._pending_mm = raw                   # candidate; hold the last trusted
        return self._last_level_mm

    def _dwell_inlet(self, desired: bool) -> bool:
        """Anti-chatter: block a normal inlet state change if the last change
        was too recent. Safety-forced OFF bypasses this (handled by caller)."""
        current = self.pumps.pump1.is_on
        if desired == current:
            return desired
        if (time.monotonic() - self._inlet_last_change) < self.cfg.control.min_switch_interval_s:
            return current                        # too soon -> hold
        return desired

    def _tick(self) -> None:
        r = self.sensor.read_level()
        level_mm = self._filter_level(r)          # spike-filtered, trusted level

        with self.state as s:
            mode = s.mode_manual
            inlet_cmd = s.inlet_cmd
            outlet_cmd = s.outlet_cmd
            low = _clamp(s.low_setpoint_mm, 0, self.span_mm)
            high = _clamp(s.high_setpoint_mm, 0, self.span_mm)
            hh = _clamp(s.highhigh_mm, 0, self.span_mm)

        inlet = outlet = False
        alarm_sensor = False
        alarm_highhigh = False

        if level_mm is None:
            # Fail safe: no trusted level -> everything off (immediate, no dwell).
            alarm_sensor = True
            inlet = outlet = False
        else:
            if mode == MODE_AUTO:
                inlet = self._auto_inlet(level_mm, low, high)
                outlet = False
            else:  # MODE_MANUAL
                inlet = inlet_cmd
                outlet = outlet_cmd

            inlet = self._dwell_inlet(inlet)         # anti-chatter on normal changes

            # --- safety overrides (both modes; bypass dwell) ---
            if level_mm <= self.cfg.control.dry_min_mm:
                outlet = False                       # dry-run guard
            if level_mm >= hh:
                alarm_highhigh = True
                inlet = False                        # overflow guard (immediate)

        # drive hardware; record inlet switch time for the dwell timer
        prev_inlet = self.pumps.pump1.is_on
        self.pumps.pump1.set(inlet)
        self.pumps.pump2.set(outlet)
        if self.pumps.pump1.is_on != prev_inlet:
            self._inlet_last_change = time.monotonic()

        # publish status + alarms (the filtered level, so the HMI reads steady)
        with self.state as s:
            if level_mm is not None:
                s.level_mm = level_mm
                s.level_pct = max(0, min(100, int(round(level_mm / self.span_mm * 100)))) if self.span_mm else 0
            s.inlet_on = self.pumps.pump1.is_on
            s.outlet_on = self.pumps.pump2.is_on
            s.alarm_sensor = alarm_sensor
            s.alarm_highhigh = alarm_highhigh

    def _auto_inlet(self, level_mm: int, low: int, high: int) -> bool:
        """Hysteresis fill: inlet ON below `low`, OFF at/above `high`, hold
        between so it can't chatter around a single setpoint."""
        on = self.pumps.pump1.is_on
        if level_mm <= low:
            on = True
        elif level_mm >= high:
            on = False
        return on
