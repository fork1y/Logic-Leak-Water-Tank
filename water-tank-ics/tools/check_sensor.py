#!/usr/bin/env python3
"""Step 1 bring-up: live HC-SR04 reading.

Prints distance + level % about twice a second so you can:
  - confirm Trig/Echo wiring (you get real numbers, not timeouts),
  - calibrate tank geometry: fill/empty the tank and read the cm values,
    then put them in config.yaml as tank_full_cm / tank_empty_cm.

No pumps are touched by this script. Safe to run first.

    cd water-tank-ics
    python3 -m tools.check_sensor        # uses config.yaml geometry
    python3 -m tools.check_sensor --raw  # distance only, ignore geometry

Ctrl-C to stop.
"""
from __future__ import annotations

import argparse
import time

import RPi.GPIO as GPIO

from src import config as cfgmod
from src.sensor import UltrasonicSensor


def main() -> None:
    ap = argparse.ArgumentParser(description="Live HC-SR04 sensor check")
    ap.add_argument("--raw", action="store_true",
                    help="show distance only (for calibrating tank geometry)")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = cfgmod.load(args.config)
    GPIO.setmode(GPIO.BCM if cfg.gpio_mode == "BCM" else GPIO.BOARD)
    GPIO.setwarnings(False)

    print(f"Trig=GPIO{cfg.sensor.trig_pin}  Echo=GPIO{cfg.sensor.echo_pin}  "
          f"(empty={cfg.sensor.tank_empty_cm}cm full={cfg.sensor.tank_full_cm}cm)")
    print("Reading... Ctrl-C to stop.\n")

    sensor = UltrasonicSensor(cfg.sensor)
    print(f"span = {cfg.sensor.span_mm} mm\n")
    misses = 0
    try:
        while True:
            if args.raw:
                d = sensor.read_distance_cm()
                if d is None:
                    misses += 1
                    print(f"  no echo (miss #{misses}) — check wiring / divider")
                else:
                    print(f"  distance = {d:6.1f} cm")
            else:
                r = sensor.read_level()
                if not r.valid:
                    misses += 1
                    print(f"  INVALID (miss #{misses}) — lost echo / out of range "
                          f"(dist={r.distance_cm} cm)")
                else:
                    bar = "#" * int(r.level_pct / 5)
                    print(f"  level = {r.level_mm:4d} mm / {r.level_pct:3d} %  "
                          f"({r.distance_cm:5.1f} cm)  |{bar:<20}|")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
