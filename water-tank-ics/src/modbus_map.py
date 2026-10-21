"""Modbus register map — the single source of truth for addresses.

Built to the agreed integration spec. Both the server (src/modbus_server.py)
and everything that talks to it (Mango Automation, attack scripts) must agree
on these addresses.

ADDRESSING: client address 0 = the first register of each block (INLET_CMD is
coil 0, LEVEL_MM is holding register 0, ...). pymodbus/Mango-style. Some HMIs
show 1-based 0xxxx/4xxxx notation; add 1 there.

UNITS: Modbus registers are 16-bit integers with no decimals, so level and all
setpoints are stored in MILLIMETERS (e.g. 152 = 15.2 cm). LEVEL_PCT (0-100) is
also published for a convenient gauge binding. Mango divides mm by 10 for cm.

  COILS            (FC01 read / FC05,15 write) : HMI commands + mode
  DISCRETE INPUTS  (FC02 read)                 : live status + alarms (RO)
  HOLDING REGISTERS(FC03 read / FC06,16 write) : level readback + setpoints
"""

# --- Coils (read/write, 1-bit): HMI commands ---
COIL_INLET_CMD = 0      # HMI: run inlet pump (Pump 1 / GPIO23) — manual mode
COIL_OUTLET_CMD = 1     # HMI: run outlet pump (Pump 2 / GPIO24) — manual mode
COIL_MODE_MANUAL = 2    # 0 = Pi auto level control, 1 = HMI manual override
NUM_COILS = 3

# --- Discrete inputs (read-only, 1-bit): live status + alarms ---
DI_INLET_STATE = 0      # inlet pump actually energized
DI_OUTLET_STATE = 1     # outlet pump actually energized
DI_ALARM_HIGHHIGH = 2   # level >= high-high (overflow risk)
DI_ALARM_SENSOR = 3     # sensor reading invalid / out of range
NUM_DISCRETE = 4

# --- Holding registers (read/write, 16-bit): level readback + setpoints ---
HR_LEVEL_MM = 0         # current level, mm (published by Pi each loop) [RO-ish]
HR_LEVEL_PCT = 1        # current level, % 0-100 (published by Pi)      [RO-ish]
HR_LOW_SETPOINT_MM = 2  # writable: auto turns inlet ON below this
HR_HIGH_SETPOINT_MM = 3 # writable: auto turns inlet OFF at/above this
HR_HIGHHIGH_MM = 4      # writable: overflow threshold (forces inlet OFF, any mode)
NUM_HOLDING_REGS = 5

# NOTE: LEVEL_MM / LEVEL_PCT live in holding registers per the agreed map, but
# the Pi overwrites them every loop, so a client write to them is transient
# (next loop restores the measured value). Setpoints 2-4 are the real writables.
