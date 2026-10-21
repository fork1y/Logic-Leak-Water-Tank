#!/usr/bin/env python3
"""Step 2 bring-up: confirmation-gated pump/relay test.

Verifies, safely, that:
  - the right GPIO drives the right pump,
  - active_low polarity in config.yaml is correct (relay clicks ON when you
    say ON, not the opposite),
  - the controller's Pump class drives the relay the way the control loop will.

Safety design:
  - nothing energizes until you type the pump name to confirm,
  - every energize is time-limited (--secs, default 3s) and auto-off,
  - OFF is re-asserted on exit / Ctrl-C.

    cd water-tank-ics
    python3 -m tools.check_pumps              # interactive menu
    python3 -m tools.check_pumps --secs 2     # shorter pulses

Make sure the tank can accept whatever these short pulses move, or run the
pumps dry-safe (tubes in the reservoir) for the very first click test.
"""
from __future__ import annotations

import argparse
import time

import RPi.GPIO as GPIO

from src import config as cfgmod
from src.pumps import PumpBank


def _pulse(pump, name: str, secs: float) -> None:
    print(f"  -> {name} ON for {secs}s ...")
    pump.set(True)
    try:
        time.sleep(secs)
    finally:
        pump.set(False)
        print(f"  -> {name} OFF")


def main() -> None:
    ap = argparse.ArgumentParser(description="Interactive pump/relay check")
    ap.add_argument("--secs", type=float, default=3.0,
                    help="max seconds to energize per test (default 3)")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = cfgmod.load(args.config)
    GPIO.setmode(GPIO.BCM if cfg.gpio_mode == "BCM" else GPIO.BOARD)
    GPIO.setwarnings(False)

    print(f"Pump1 (fill)    -> GPIO{cfg.pumps.pump1.relay_pin}")
    print(f"Pump2 (recirc)  -> GPIO{cfg.pumps.pump2.relay_pin}")
    print(f"active_low = {cfg.pumps.active_low}  (flip in config.yaml if a "
          f"relay energizes when it should be off)\n")

    bank = PumpBank(cfg.pumps)  # both initialize OFF
    options = {"1": (bank.pump1, "Pump1 (fill)"),
               "2": (bank.pump2, "Pump2 (recirc)")}
    try:
        while True:
            print("Select: [1] Pump1  [2] Pump2  [q] quit")
            choice = input("> ").strip().lower()
            if choice in ("q", "quit", "exit"):
                break
            if choice not in options:
                print("  (enter 1, 2, or q)")
                continue
            pump, name = options[choice]
            confirm = input(f"  type '{choice}' again to ENERGIZE {name}: ").strip()
            if confirm == choice:
                _pulse(pump, name, args.secs)
            else:
                print("  cancelled.")
            print()
    except (KeyboardInterrupt, EOFError):
        print("\ninterrupted.")
    finally:
        bank.all_off()
        GPIO.cleanup()
        print("all pumps OFF, GPIO cleaned up.")


if __name__ == "__main__":
    main()
