# Modbus Register Map

The contract between the Pi controller and everything that talks to it (Mango
Automation, HMI tags, your attack scripts). Addresses are **zero-based**
(pymodbus with `zero_mode=True`). If your HMI uses 1-based `4xxxx`/`0xxxx`
notation, add 1 and the appropriate prefix. Unit / slave ID: **1**.

Levels are in **millimeters** because Modbus registers are 16-bit integers with
no decimals. `level_mm = (tank_empty_cm − distance_cm) × 10`.

## Coils — read FC01 / write FC05,FC15 (commands)

| Addr | Name         | Meaning                                              |
|------|--------------|------------------------------------------------------|
| 0    | INLET_CMD    | Request INLET pump ON (fill). Honored only in MANUAL |
| 1    | OUTLET_CMD   | Request OUTLET pump ON (drain). Honored only in MANUAL|
| 2    | MODE_MANUAL  | 0 = AUTO, 1 = MANUAL                                  |

## Discrete Inputs — read FC02 (status, read-only)

| Addr | Name           | Meaning                                  |
|------|----------------|------------------------------------------|
| 0    | INLET_STATE    | INLET pump currently energized           |
| 1    | OUTLET_STATE   | OUTLET pump currently energized          |
| 2    | ALARM_HIGHHIGH | Overflow guard tripped (level ≥ high-high)|
| 3    | ALARM_SENSOR   | Sensor reading lost / out of range       |

## Holding Registers — read FC03 / write FC06,FC16 (16-bit)

| Addr | Name          | Units / notes                                 |
|------|---------------|-----------------------------------------------|
| 0    | LEVEL_MM      | measured level, mm (read-only)                |
| 1    | LEVEL_PCT     | measured level, 0–100 % (read-only)           |
| 2    | LOW_SETPOINT  | mm — AUTO starts filling below this (writable)|
| 3    | HIGH_SETPOINT | mm — AUTO stops filling at/above (writable)   |
| 4    | HIGH_HIGH     | mm — overflow cutoff, any mode (writable)     |

## Control behavior

- **AUTO**: inlet fills when level ≤ LOW_SETPOINT, stops at ≥ HIGH_SETPOINT
  (hysteresis). The outlet opens as overflow relief at ≥ HIGH_HIGH and drains
  back to HIGH_SETPOINT.
- **MANUAL**: inlet/outlet follow INLET_CMD / OUTLET_CMD directly.

## Safety (enforced on the Pi, both modes)

- **HIGH-HIGH overflow**: level ≥ HIGH_HIGH → inlet forced OFF + ALARM_HIGHHIGH.
- **DRY-RUN guard**: level ≤ dry_min (config.yaml) → outlet forced OFF.
- **SENSOR invalid**: lost / out-of-range reading → both pumps OFF + ALARM_SENSOR.

## Attack-surface notes (for later phases)

Writable from the network with **no authentication**:
- Coils 0–2: flip to MANUAL, then drive the pumps directly.
- Holding 2–4: move the setpoints, e.g. raise HIGH_HIGH to defeat the overflow guard.

The Pi-side safety limits (overflow, dry-run, sensor-lost fail-safe) still apply
even to malicious writes — the attacker can command, but the controller is the
last line of defense. That gap between "what Modbus allows" and "what the
controller permits" is the story the hardening phase (Wazuh) tells.
