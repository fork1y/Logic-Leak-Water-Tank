# Modbus Register Map

The contract between the Pi controller and everything that talks to it
(Mango Automation, HMI tags, attack scripts). **Client address 0 = the first
register of each block.** Some HMIs show 1-based `0xxxx`/`4xxxx` notation; add
1 there. Unit / slave ID: **1** (see `config.yaml`).

**Units:** level and all setpoints are in **millimeters** (16-bit integers, no
decimals). `LEVEL_PCT` is also published 0–100. Mango divides mm by 10 for cm.

## Coils — read FC01 / write FC05,15 (HMI commands + mode)

| Addr | Name         | Meaning                                              |
|------|--------------|------------------------------------------------------|
| 0    | INLET_CMD    | HMI: run inlet pump (Pump 1 / GPIO23) — MANUAL mode  |
| 1    | OUTLET_CMD   | HMI: run outlet pump (Pump 2 / GPIO24) — MANUAL mode |
| 2    | MODE_MANUAL  | 0 = Pi AUTO level control, 1 = HMI MANUAL override   |

## Discrete inputs — read FC02 (status + alarms, read-only)

| Addr | Name           | Meaning                               |
|------|----------------|---------------------------------------|
| 0    | INLET_STATE    | inlet pump actually energized         |
| 1    | OUTLET_STATE   | outlet pump actually energized        |
| 2    | ALARM_HIGHHIGH | level ≥ high-high (overflow risk)     |
| 3    | ALARM_SENSOR   | sensor reading invalid / out of range |

## Holding registers — read FC03 / write FC06,16 (level + setpoints, 16-bit)

| Addr | Name            | Units / notes                               |
|------|-----------------|---------------------------------------------|
| 0    | LEVEL_MM        | current level, mm (Pi overwrites each loop) |
| 1    | LEVEL_PCT       | current level, % 0–100 (Pi overwrites)      |
| 2    | LOW_SETPOINT_MM | writable: AUTO inlet ON below this          |
| 3    | HIGH_SETPOINT_MM| writable: AUTO inlet OFF at/above this      |
| 4    | HIGHHIGH_MM     | writable: overflow — inlet OFF in ANY mode  |

## Control logic

- **AUTO** (`MODE_MANUAL=0`): hysteresis on `LEVEL_MM` — inlet ON below
  `LOW_SETPOINT_MM`, OFF at/above `HIGH_SETPOINT_MM`, holds between. Outlet off.
- **MANUAL** (`MODE_MANUAL=1`): inlet/outlet follow `INLET_CMD` / `OUTLET_CMD`.
- **Safety, both modes:** `LEVEL_MM ≥ HIGHHIGH_MM` forces the inlet OFF and
  raises `ALARM_HIGHHIGH` (so the HMI can't overflow the tank); near-empty
  forces the outlet OFF (dry-run guard); an invalid sensor reading forces both
  pumps OFF and raises `ALARM_SENSOR`.

## Attack-surface notes (for later phases)

Writable from the network with **no authentication**:
- Coils: flip `MODE_MANUAL` to 1, then drive the pumps via `INLET_CMD` /
  `OUTLET_CMD`.
- Holding regs: move the setpoints, or widen `HIGHHIGH_MM` to defeat the
  overflow guard. `LEVEL_MM`/`LEVEL_PCT` are writable but the Pi overwrites
  them each loop — a spoofed reading snaps back on the next tick, which is
  itself a nice thing to demonstrate.

The Pi's own interlocks (high-high, dry-run, sensor fail-safe) still apply to
malicious writes — the attacker can command, but the controller is the last
line of defense. That gap is the story the hardening phase tells.
