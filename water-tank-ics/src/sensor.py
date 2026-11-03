"""HC-SR04 ultrasonic distance sensor -> tank level in mm and %.

Trigger a 10 us pulse, time the echo, convert to distance (cm), then map
distance to a level in MILLIMETERS (and %) using the geometry in config.yaml.
Each measurement is the MEDIAN of several samples so a single bad echo can't
make the pumps chatter.

WARNING: the HC-SR04 Echo pin outputs 5V. The Pi's GPIO is 3.3V-only. Put a
voltage divider on the Echo line or you can damage the Pi.
"""
from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass

import RPi.GPIO as GPIO

from .config import SensorCfg

log = logging.getLogger("sensor")

SPEED_OF_SOUND_CM_S = 34300.0  # cm/s at ~20 C


@dataclass
class Reading:
    valid: bool          # False if echo lost or distance implausible
    level_mm: int        # water level in millimeters (0 .. span_mm)
    level_pct: int       # water level 0..100 %
    distance_cm: float   # raw measured distance (0.0 if invalid)


class UltrasonicSensor:
    def __init__(self, cfg: SensorCfg):
        self.cfg = cfg
        GPIO.setup(cfg.trig_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(cfg.echo_pin, GPIO.IN)
        time.sleep(0.05)  # let the sensor settle

    def _read_distance_once(self) -> float | None:
        """Return a single distance reading in cm, or None on timeout."""
        c = self.cfg
        GPIO.output(c.trig_pin, GPIO.HIGH)
        time.sleep(0.00001)             # 10 us trigger pulse
        GPIO.output(c.trig_pin, GPIO.LOW)

        deadline = time.monotonic() + c.timeout_s
        while GPIO.input(c.echo_pin) == 0:          # wait for echo HIGH
            if time.monotonic() > deadline:
                return None
        start = time.monotonic()
        while GPIO.input(c.echo_pin) == 1:          # wait for echo LOW
            if time.monotonic() > deadline:
                return None
        end = time.monotonic()
        return (end - start) * SPEED_OF_SOUND_CM_S / 2.0

    def read_distance_cm(self) -> float | None:
        """Median-filtered distance in cm. None if every sample timed out."""
        readings = []
        for _ in range(self.cfg.samples):
            d = self._read_distance_once()
            if d is not None and 0 < d < 500:
                readings.append(d)
            time.sleep(0.01)
        if not readings:
            log.warning("no valid echo this cycle")
            return None
        return statistics.median(readings)

    def read_level(self) -> Reading:
        """Measure and convert to a Reading(level_mm, level_pct, valid).

        valid is False when the echo is lost OR the distance is well outside
        the configured tank range (drives the ALARM_SENSOR discrete input).
        """
        c = self.cfg
        dist = self.read_distance_cm()
        if dist is None:
            return Reading(False, 0, 0, 0.0)

        # plausibility window: a little past both ends of the tank range
        lo = c.tank_full_cm - 2.0
        hi = c.tank_empty_cm + 5.0
        valid = lo <= dist <= hi

        span_mm = c.span_mm
        level_mm = int(round((c.tank_empty_cm - dist) * 10))
        level_mm = max(0, min(span_mm, level_mm))          # clamp
        level_pct = int(round(level_mm / span_mm * 100)) if span_mm > 0 else 0
        level_pct = max(0, min(100, level_pct))
        return Reading(valid, level_mm, level_pct, round(dist, 1))
