"""Load and expose config.yaml as nested dataclasses.

One place reads the YAML; everything else imports typed objects from here,
so a typo in a key fails loudly at startup instead of deep in a control loop.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass
class SensorCfg:
    trig_pin: int
    echo_pin: int
    tank_empty_cm: float
    tank_full_cm: float
    samples: int
    timeout_s: float

    @property
    def span_mm(self) -> int:
        """Usable level span in millimeters (full - empty distance, *10)."""
        return int(round((self.tank_empty_cm - self.tank_full_cm) * 10))


@dataclass
class PumpCfg:
    relay_pin: int


@dataclass
class PumpsCfg:
    active_low: bool
    pump1: PumpCfg
    pump2: PumpCfg


@dataclass
class ControlCfg:
    mode_on_boot: str
    low_setpoint_mm: int
    high_setpoint_mm: int
    highhigh_mm: int
    dry_min_mm: int
    loop_interval_s: float
    # --- noise hardening (have defaults so older config.yaml still loads) ---
    min_switch_interval_s: float = 5.0   # inlet can't change state faster than this
    max_jump_mm: int = 40                # reject level jumps bigger than this (noise)


@dataclass
class ModbusCfg:
    host: str
    port: int
    unit_id: int


@dataclass
class LoggingCfg:
    level: str
    file: str


@dataclass
class Config:
    gpio_mode: str
    sensor: SensorCfg
    pumps: PumpsCfg
    control: ControlCfg
    modbus: ModbusCfg
    logging: LoggingCfg
    raw: dict = field(repr=False, default_factory=dict)


def load(path: str | os.PathLike | None = None) -> Config:
    """Read the YAML file and build a validated Config object."""
    p = Path(path) if path else _DEFAULT_PATH
    with open(p, "r") as fh:
        d = yaml.safe_load(fh)

    cfg = Config(
        gpio_mode=d["gpio"]["mode"],
        sensor=SensorCfg(**d["sensor"]),
        pumps=PumpsCfg(
            active_low=d["pumps"]["active_low"],
            pump1=PumpCfg(**d["pumps"]["pump1"]),
            pump2=PumpCfg(**d["pumps"]["pump2"]),
        ),
        control=ControlCfg(**d["control"]),
        modbus=ModbusCfg(**d["modbus"]),
        logging=LoggingCfg(**d["logging"]),
        raw=d,
    )
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    if cfg.sensor.tank_empty_cm <= cfg.sensor.tank_full_cm:
        raise ValueError("sensor.tank_empty_cm must be > tank_full_cm")
    span = cfg.sensor.span_mm
    c = cfg.control
    if not (0 <= c.low_setpoint_mm < c.high_setpoint_mm <= c.highhigh_mm <= span):
        raise ValueError(
            "control setpoints must satisfy "
            "0 <= low < high <= highhigh <= span_mm "
            f"(low={c.low_setpoint_mm}, high={c.high_setpoint_mm}, "
            f"highhigh={c.highhigh_mm}, span={span})"
        )
    if not (0 <= c.dry_min_mm < c.high_setpoint_mm):
        raise ValueError("control.dry_min_mm must be in [0, high_setpoint_mm)")
    if cfg.control.mode_on_boot not in ("AUTO", "MANUAL"):
        raise ValueError("control.mode_on_boot must be AUTO or MANUAL")
    pins = [
        cfg.sensor.trig_pin, cfg.sensor.echo_pin,
        cfg.pumps.pump1.relay_pin, cfg.pumps.pump2.relay_pin,
    ]
    if len(set(pins)) != len(pins):
        raise ValueError(f"GPIO pins must be unique, got {pins}")


def setup_logging(cfg: Config) -> None:
    """Configure root logging to console + file per config."""
    Path(cfg.logging.file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, cfg.logging.level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)-14s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(cfg.logging.file),
        ],
    )
