#!/usr/bin/env python3
"""Step 2 bring-up: cycle each pump relay to confirm wiring + polarity.

Drives the relays directly — no control loop, no sensor, no Modbus — so you can
hear each relay click and watch each pump run on its own. Use this to verify:
  - active_low is correct (command ON actually runs the pump, not the reverse),
  - the pumps aren't swapped (pump1_fill drives the INLET, pump2 the OUTLET),
  - the pumps are on the relay's NO contact (pump OFF when the Pi is off).

Pumps are forced OFF on exit.

    cd water-tank-ics
    python3 -m tools.check_pumps
"""
from __future__ import annotations

import RPi.GPIO as GPIO

from src import config as cfgmod
from src.pumps import PumpBank


def main() -> None:
    cfg = cfgmod.load("config.yaml")
    GPIO.setmode(GPIO.BCM if cfg.gpio_mode == "BCM" else GPIO.BOARD)
    GPIO.setwarnings(False)

    pumps = PumpBank(cfg.pumps)
    print(f"pump1_fill   -> GPIO{cfg.pumps.pump1.relay_pin} (INLET)")
    print(f"pump2_recirc -> GPIO{cfg.pumps.pump2.relay_pin} (OUTLET)")
    print(f"active_low = {cfg.pumps.active_low}\n")

    try:
        for name, p in (("pump1_fill (INLET)", pumps.pump1),
                        ("pump2_recirc (OUTLET)", pumps.pump2)):
            input(f"ENTER to turn {name} ON ...")
            p.set(True)
            input(f"  {name} is ON — pump should be running. ENTER to turn OFF ...")
            p.set(False)
            print(f"  {name} OFF\n")
        print("done — both pumps verified.")
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        pumps.all_off()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
