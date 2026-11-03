"""Modbus register map — the single source of truth for addresses.

Both the server (src/modbus_server.py) and anything that talks to it (Mango
Automation, your attack scripts) must agree on these. All addresses are
ZERO-BASED, which is what pymodbus uses internally with zero_mode=True. Some
HMIs display 1-based "4xxxx"/"0xxxx" addresses; add 1 and the prefix there.

  COILS            (FC 01 read / 05,15 write) : on/off commands
  DISCRETE INPUTS  (FC 02 read)               : on/off status (read-only)
  HOLDING REGISTERS(FC 03 read / 06,16 write) : level readback + setpoints
"""

# --- Coils (writable commands) ---
COIL_INLET_CMD = 0      # request INLET  pump ON (fill)  — honored in MANUAL
COIL_OUTLET_CMD = 1     # request OUTLET pump ON (drain) — honored in MANUAL
COIL_MODE_MANUAL = 2    # 0 = AUTO, 1 = MANUAL
NUM_COILS = 3

# --- Discrete inputs (read-only status bits) ---
DI_INLET_STATE = 0      # INLET  pump actually energized
DI_OUTLET_STATE = 1     # OUTLET pump actually energized
DI_ALARM_HIGHHIGH = 2   # overflow guard tripped (level >= high-high)
DI_ALARM_SENSOR = 3     # sensor reading lost / out of range
NUM_DISCRETE = 4

# --- Holding registers (read level, write setpoints; 16-bit) ---
HR_LEVEL_MM = 0         # measured level in mm         (read-only)
HR_LEVEL_PCT = 1        # measured level 0-100 %       (read-only)
HR_LOW_SETPOINT_MM = 2  # AUTO: inlet ON below this    (writable)
HR_HIGH_SETPOINT_MM = 3 # AUTO: inlet OFF at/above     (writable)
HR_HIGHHIGH_MM = 4      # overflow cutoff, any mode    (writable)
NUM_HOLDING_REGS = 5
