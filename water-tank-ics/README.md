# LogicLeak — Water Tank ICS Controller

A small-scale networked Industrial Control System on a Raspberry Pi 4: it
measures a tank's water level with an ultrasonic sensor and controls inlet /
outlet pumps via relays, exposing the plant over Modbus TCP to a Mango
Automation HMI. Built both as a working process-control demo and as an isolated
target for studying ICS cybersecurity.

## Layout

```
water-tank-ics/
├── config.yaml            # single source of truth: pins, calibration, setpoints
├── requirements.txt       # pymodbus 3.6.x (pinned), PyYAML, RPi.GPIO
├── src/
│   ├── config.py          # loads + validates config.yaml
│   ├── sensor.py          # HC-SR04 -> level in mm / %
│   ├── pumps.py           # relay-driven pump control (active_low aware)
│   ├── state.py           # thread-safe PlantState shared by loop + server
│   ├── modbus_map.py      # register addresses (single source of truth)
│   ├── modbus_server.py   # async Modbus TCP server over live PlantState
│   ├── controller.py      # AUTO hysteresis + MANUAL override + safety
│   └── main.py            # wires controller thread + Modbus server
├── tools/                 # bring-up helpers (sensor, pumps, modbus)
├── tests/                 # off-Pi test suite (stubbed RPi.GPIO + pymodbus)
├── docs/modbus_register_map.md
└── systemd/watertank.service
```

## Calibration (this tank)

- Sensor at the top; empty ≈ 26.4 cm, full = 0 cm → **span 264 mm**.
- `level_mm = (26.4 − distance_cm) × 10`.
- Setpoints: low **44 mm** (22 cm), high **94 mm** (17 cm), high-high **134 mm**
  (13 cm), dry-min **20 mm**.
- `active_low: false` — this relay board is active-high, pumps on the NO contact
  (so a powered-off Pi leaves the pumps OFF).

## Control behavior

- **AUTO**: inlet fills below 44 mm, stops at 94 mm. The outlet opens as
  overflow relief at 134 mm and drains back to 94 mm.
- **MANUAL**: operator drives inlet/outlet from the HMI command coils.
- **Safety (both modes)**: high-high forces the inlet off + alarm; dry-run
  forces the outlet off; a lost/implausible sensor reading forces both off + alarm.

## Run on the Pi

```bash
pip install -r requirements.txt --break-system-packages
# bring-up checks first:
python3 -m tools.check_sensor         # live level (add --raw to calibrate)
python3 -m tools.check_pumps          # cycle each relay
# start the controller (port 502 needs root):
sudo python3 -m src.main
# verify Modbus from a client:
python3 -m tools.check_modbus
```

To change a Python file on the Pi, **replace the whole file** (scp it) — do not
hand-edit it in nano, which mixes tabs and spaces and breaks indentation.

## Tests (run anywhere, no Pi, no pip installs)

```bash
PYTHONPATH=tests/_stubs:. python3 tests/test_modules.py      # 52 checks
PYTHONPATH=tests/_stubs:. python3 tests/test_integration.py  #  8 checks
```

## HMI

Mango Automation v5.6.4 (Docker), Modbus-IP data source polling the Pi, 12 data
points in a "Water Tank HMI" watch list. See `docs/modbus_register_map.md` for
the addresses.

## Phases

1. **Control / ICS** — this controller + Mango HMI (done; under test).
2. **Security** — place on an isolated network, run Modbus recon / injection /
   replay from Kali, then detect and harden with Wazuh.
