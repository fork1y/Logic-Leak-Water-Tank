# Overview
This project recreates the behavior of a real industrial process-control environment at a benchtop scale. A Raspberry Pi 4 reads the water level in a tank and drives two DC pumps to keep that level within a target range, moving water between a reservoir and the main tank. On top of this physical process sits a SCADA stack (Modbus TCP + Mango Automation + an HMI dashboard).
