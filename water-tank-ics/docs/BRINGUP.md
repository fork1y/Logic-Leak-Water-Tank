# Software Integration — Staged Bring-Up

Bring the software up against real hardware one layer at a time. Do **not**
start with `python -m src.main`: that starts the control loop, which can
energize pumps automatically based on the sensor. Validate each layer first.

Run everything from the project root on the Pi:

```bash
cd water-tank-ics
pip install -r requirements.txt
```

---

## Step 0 — Confirm config matches your wiring

Open `config.yaml` and check the four pins against how you wired it:

| Function          | config key                | default |
|-------------------|---------------------------|---------|
| Pump 1 (fill)     | `pumps.pump1.relay_pin`   | 23      |
| Pump 2 (recirc)   | `pumps.pump2.relay_pin`   | 24      |
| HC-SR04 Trig      | `sensor.trig_pin`         | 17      |
| HC-SR04 Echo      | `sensor.echo_pin`         | 27      |

Echo must come through a voltage divider (5V → 3.3V).

---

## Step 1 — Sensor (no pumps touched)

```bash
python3 -m tools.check_sensor          # level % + distance
python3 -m tools.check_sensor --raw    # distance only, for calibration
```

**Pass criteria:** steady distance readings, no "no echo" misses.

**Calibrate geometry:** with `--raw`, note the cm reading when the tank is
empty and when full, and put them in `config.yaml` as `tank_empty_cm` /
`tank_full_cm`. Re-run without `--raw` and confirm level tracks 0→100 %.

---

## Step 2 — Pumps / relays (confirmation-gated, auto-off)

```bash
python3 -m tools.check_pumps           # 3s pulses, menu-driven
python3 -m tools.check_pumps --secs 2
```

Nothing energizes until you re-type the pump number. Each pulse auto-stops.

**Pass criteria:** selecting Pump1 clicks the Pump1 relay (not Pump2), and the
relay is ON only while the script says ON. If a relay is ON when it should be
OFF, flip `pumps.active_low` in `config.yaml` and re-run.

---

## Step 3 — Full control loop

Now the pieces are trusted individually, start the real controller:

```bash
python3 -m src.main
```

Watch the log: it reads level, and in AUTO mode starts Pump 1 below
`low_threshold_pct`, stops at `high_threshold_pct`. Safety interlocks
(overflow, dry-run, max-runtime, e-stop, sensor-lost) are active.
Ctrl-C stops it and forces pumps OFF.

**Pass criteria:** level drops below low → Pump 1 turns on; level reaches high
→ Pump 1 turns off. No chatter around a single setpoint.

> Port 502 needs root (`sudo python3 -m src.main`). To run unprivileged, set
> `modbus.port: 5020` in `config.yaml`.

---

## Step 4 — Modbus (leave `src.main` running)

From the Pi (localhost) or the SCADA/attacker box:

```bash
python3 -m tools.check_modbus                      # localhost
python3 -m tools.check_modbus --host <pi-ip>       # from another box
python3 -m tools.check_modbus --port 5020          # if you moved the port
```

**Pass criteria:** `RESULT: Modbus integration verified`. The coil round-trip
confirms the address offset is correct — if reads look shifted by one index,
that's the `zero_mode` setting in `src/modbus_server.py`, and it's a one-line
fix. Flip MODE to REMOTE from `check_modbus` and confirm pump commands take
effect, then back to AUTO.

Once Step 4 passes, the Pi is ready for **Phase 4: Mango Automation** — point
a Modbus TCP data source at `<pi-ip>:502`, unit 1, and map tags per
`docs/modbus_register_map.md`.
```
