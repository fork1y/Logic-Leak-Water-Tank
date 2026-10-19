# Overview
This project recreates the behavior of a real industrial process-control environment at a benchtop scale. A Raspberry Pi 4 reads the water level in a tank and drives two DC pumps to keep that level within a target range, moving water between a reservoir and the main tank. On top of this physical process sits a SCADA stack (Modbus TCP + Mango Automation + an HMI dashboard).
### The project has two halves:
1) Control / ICS side — a functioning water-management process: the level is sensed continuously and the inlet/outlet pumps are controlled automatically by the Pi or remotely through the SCADA system.
2) Cybersecurity side — the completed ICS is placed on an isolated network and evaluated for vulnerabilities, with real attacks (injection, relay) launched from an attacker workstation to demonstrate their physical impact on the process.
