"""Relay-driven pump control.

Each pump is one relay channel on a GPIO pin. Keyes/SRD relay boards are
usually ACTIVE-LOW (GPIO LOW energizes the relay), set by pumps.active_low.
Pumps always initialize OFF, and OFF is re-asserted on shutdown.
"""
from __future__ import annotations

import logging
import time

import RPi.GPIO as GPIO

from .config import PumpsCfg

log = logging.getLogger("pumps")


class Pump:
    def __init__(self, name: str, pin: int, active_low: bool):
        self.name = name
        self.pin = pin
        self.active_low = active_low
        self._on = False
        self._started_at: float | None = None
        # Drive the OFF level before enabling output to avoid a power-on glitch.
        off_level = GPIO.HIGH if active_low else GPIO.LOW
        GPIO.setup(pin, GPIO.OUT, initial=off_level)
        log.info("pump '%s' on GPIO%d initialized OFF", name, pin)

    def _write(self, on: bool) -> None:
        level = (GPIO.LOW if on else GPIO.HIGH) if self.active_low \
            else (GPIO.HIGH if on else GPIO.LOW)
        GPIO.output(self.pin, level)

    def set(self, on: bool) -> None:
        if on == self._on:
            return
        self._write(on)
        self._on = on
        self._started_at = time.monotonic() if on else None
        log.info("pump '%s' -> %s", self.name, "ON" if on else "OFF")

    @property
    def is_on(self) -> bool:
        return self._on

    @property
    def runtime_s(self) -> float:
        if self._on and self._started_at is not None:
            return time.monotonic() - self._started_at
        return 0.0


class PumpBank:
    """Owns both pumps and guarantees a safe all-off state."""

    def __init__(self, cfg: PumpsCfg):
        self.pump1 = Pump("pump1_fill", cfg.pump1.relay_pin, cfg.active_low)
        self.pump2 = Pump("pump2_recirc", cfg.pump2.relay_pin, cfg.active_low)

    def all_off(self) -> None:
        self.pump1.set(False)
        self.pump2.set(False)
