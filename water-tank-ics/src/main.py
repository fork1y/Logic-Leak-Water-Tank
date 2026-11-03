"""Entry point: wire the control loop and the Modbus server together.

The controller runs in its own thread; the async Modbus server runs in the
main thread's event loop. Both share one PlantState. Ctrl-C (or systemd stop)
tears down cleanly with pumps forced OFF.

Run on the Pi:   python -m src.main
(Port 502 needs root; use a >1024 port in config.yaml to run unprivileged.)
"""
from __future__ import annotations

import asyncio
import logging

import RPi.GPIO as GPIO

from . import config as cfgmod
from .controller import Controller
from .modbus_server import run_server
from .state import PlantState

log = logging.getLogger("main")


async def _amain() -> None:
    cfg = cfgmod.load()
    cfgmod.setup_logging(cfg)
    log.info("=== Water Tank ICS Controller starting ===")

    GPIO.setmode(GPIO.BCM if cfg.gpio_mode == "BCM" else GPIO.BOARD)
    GPIO.setwarnings(False)

    state = PlantState()
    controller = Controller(cfg, state)
    controller.start()

    try:
        await run_server(cfg, state)
    finally:
        controller.stop()
        controller.join(timeout=3)
        GPIO.cleanup()
        log.info("shutdown complete")


def main() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        log.info("interrupted by user")


if __name__ == "__main__":
    main()
