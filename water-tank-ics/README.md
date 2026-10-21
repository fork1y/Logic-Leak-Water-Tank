# Water Tank ICS / SCADA Testbed — Controller Software


| Path                         | Purpose                                      |
|------------------------------|----------------------------------------------|
| `config.yaml`                | All pins, thresholds, timings — edit here    |
| `src/config.py`              | Typed loader + validation + logging setup    |
| `src/sensor.py`              | HC-SR04 driver, median-filtered level %      |
| `src/pumps.py`               | Relay/pump control (active-low aware)         |
| `src/state.py`               | Thread-safe shared plant state               |
| `src/controller.py`          | Control state machine + safety interlocks    |
| `src/modbus_map.py`          | Register addresses (single source of truth)  |
| `src/modbus_server.py`       | Async Modbus TCP server over live state      |
| `src/main.py`                | Entry point (controller thread + server)     |
| `systemd/watertank.service`  | Run on boot                                  |
| `docs/modbus_register_map.md`| Full register map + attack-surface notes     |
| `tests/test_modules.py`      | Per-module tests (stubs), new spec           |
| `tests/test_integration.py`  | End-to-end Mango↔Pi loop test (stubs)        |
| `tools/check_sensor.py`      | Bring-up: live sensor read + calibrate       |
| `tools/check_pumps.py`       | Bring-up: gated pump/relay test              |
| `tools/check_modbus.py`      | Bring-up: verify Modbus from a client        |
| `docs/BRINGUP.md`            | Staged hardware integration runbook          |
| `docs/DEPLOY_PI_MANGO.md`    | Beginner deploy guide (Frontier-network path)|

## Setup (on the Raspberry Pi)

```bash
pip install -r requirements.txt
# ⚠️ EDIT config.yaml AND CONFIRM GPIO PINS before connecting pumps
python -m src.main
```

Verify the logic without hardware (runs on any laptop; uses stub RPi.GPIO +
pymodbus in `tests/_stubs`, so it needs no pip installs):

```bash
PYTHONPATH=tests/_stubs:. python3 tests/testing_test.py
```

Install as a service:

```bash
sudo cp systemd/watertank.service /etc/systemd/system/
sudo systemctl enable --now watertank
journalctl -u watertank -f
```


- **Relay polarity:** Keyes/SRD boards are usually active-low (`active_low: true`).
  If pumps run when they should be off, flip it.
- **Echo voltage divider:** HC-SR04 Echo is 5V; the Pi is 3.3V. Use the
  resistor divider (the resistors on your breadboard) or you can damage the Pi.
- **Tank geometry:** set `tank_empty_cm` / `tank_full_cm` to your real tank.

## Operating modes

- **AUTO** — Pi fills on hysteresis (start below `low_threshold_pct`, stop at
  `high_threshold_pct`).
- **REMOTE** — Pi obeys Modbus pump commands from SCADA/HMI.
- Switch modes by writing coil `MODE_REMOTE`. Safety limits apply in both.

```
