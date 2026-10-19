# Overview
This project recreates the behavior of a real industrial process-control environment at a benchtop scale. A Raspberry Pi 4 reads the water level in a tank and drives two DC pumps to keep that level within a target range, moving water between a reservoir and the main tank. On top of this physical process sits a SCADA stack (Modbus TCP + Mango Automation + an HMI dashboard).
### The project has two parts:
1) Control / ICS side — a functioning water-management process: the level is sensed continuously and the inlet/outlet pumps are controlled automatically by the Pi or remotely through the SCADA system.
2) Cybersecurity side — the completed ICS is placed on an isolated network and evaluated for vulnerabilities, with real attacks (injection, relay) launched from an attacker workstation to demonstrate their physical impact on the process.

# System Architecture
The system is organized into three layers
### 1) Physical Layer
• Raspberry Pi4 - primary controller; reads the level sensor and drives the relays
• HC-SR04 ultrasonic sensor - measures the water level in the tank
• relay modules (2x) - switch the two pumps on/off under GPIO control
• 5V DC pumps - pump 1 fills the water tank from the reservoir; pump 2 recirculates/drains back to the reservior
• Water tank and reservoir

### 2) Control Layer
