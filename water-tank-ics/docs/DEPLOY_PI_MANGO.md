# Deploying the Pi + Mango System (guide)

This brings up the control system on your existing Wi-Fi/router 
Can also move to the isolated switch if needed.

Devices: **the Pi** (controller) and **Computer 1** (SSH + Mango).

---

## Step 1 — Get the Pi on the network and reachable

1. Connect the **Pi to your network** — ethernet into a router LAN
   port (most reliable) or the Pi's Wi-Fi. Put **Computer 1 on the same
   network**.
2. On the Pi, find its IP address:
   ```bash
   hostname -I        # e.g. 192.168.1.37  -> this is the Pi's IP
   ```
3. Enable SSH once (so you can work from Computer 1 without a monitor):
   ```bash
   sudo raspi-config   # Interface Options -> SSH -> Enable
   ```
4. From **Computer 1**, confirm you can reach and log into the Pi:
   ```bash
   ping 192.168.1.37
   ssh pi@192.168.1.37
   ```
   A login prompt means the network foundation is done.

> Tip: in the Internet router admin page, set a **DHCP reservation** for the
> Pi so its IP never changes — otherwise Mango may lose it after a reboot.

---

## Step 2 — Put the control program on the Pi and start it

1. Copy the project folder to the Pi (from Computer 1, where the unzipped
   `water-tank-ics` lives):
   ```bash
   scp -r water-tank-ics pi@192.168.1.37:~/
   ```
2. SSH into the Pi and install dependencies:
   ```bash
   ssh pi@192.168.1.37
   cd ~/water-tank-ics
   pip install -r requirements.txt     # installs pymodbus + RPi.GPIO
   ```
3. **Confirm config matches your wiring** — edit `config.yaml` if the GPIO pins
   differ (defaults: inlet 23, outlet 24, Trig 17, Echo 27), and set the tank
   geometry (`tank_empty_cm` / `tank_full_cm`).
4. Bring up the hardware one layer at a time (see `docs/BRINGUP.md`):
   ```bash
   python3 -m tools.check_sensor      # live level in mm/%  (calibrate here)
   python3 -m tools.check_pumps       # confirm inlet/outlet + polarity
   ```
5. Start the controller + Modbus server:
   ```bash
   sudo python3 -m src.main           # port 502 needs root
   ```
   Leave this running. The Pi is now live on the network as a Modbus device:
   **`<Pi-IP>:502`, unit 1.**

> To run without `sudo`, set `modbus.port: 5020` in `config.yaml` and use that
> port everywhere below.

---

## Step 3 — Verify Modbus over the network (before Mango)

From **Laptop 1** (install pymodbus there too: `pip install "pymodbus>=3.6,<4.0"`):
```bash
cd water-tank-ics
python3 -m tools.check_modbus --host 192.168.1.37
```
`RESULT: Modbus integration verified` proves the network + addressing are
correct. If a read looks shifted by one index, tell me — it's a one-line
`zero_mode` fix in `src/modbus_server.py`.

---

## Step 4 — Mango: data source, points, HMI

On **Laptop 1**, install Mango and open it (`http://localhost:8080`).

1. **Create a Modbus IP data source:** transport **TCP**, host **`192.168.1.37`**
   (the Pi's IP), port **502**, **slave/unit ID 1**, poll period ~500 ms.
2. **Add data points** per `docs/modbus_register_map.md`. Match each point's
   Modbus type + offset exactly:

   | Point | Modbus type | Offset | R/W |
   |---|---|---|---|
   | Level (mm) | Holding register | 0 | read |
   | Level (%) | Holding register | 1 | read |
   | Low setpoint | Holding register | 2 | read/write |
   | High setpoint | Holding register | 3 | read/write |
   | High-high | Holding register | 4 | read/write |
   | Inlet command | Coil | 0 | read/write |
   | Outlet command | Coil | 1 | read/write |
   | Mode (manual) | Coil | 2 | read/write |
   | Inlet running | Binary input | 0 | read |
   | Outlet running | Binary input | 1 | read |
   | Alarm high-high | Binary input | 2 | read |
   | Alarm sensor | Binary input | 3 | read |

   (If Mango uses 1-based addressing, add 1 to each offset.)
3. **Confirm live values:** the Level point should track the real water level.
4. **Build the HMI:** a level gauge (bind to Level %), lamps for inlet/outlet
   and the two alarms, a Mode toggle (coil 2), and inlet/outlet buttons
   (coils 0/1).
5. **End-to-end test:** set Mode = MANUAL on the HMI, press Inlet → the real
   pump runs and the lamp lights. Set Mode = AUTO → the Pi resumes automatic
   filling. That round trip is full integration.

---

## When you add the switch (attack phase)

Nothing in the code changes — you only switch the network to the isolated
`192.168.50.x` plan and update **one thing**: the host IP in Mango's data
source (and `--host` in `check_modbus`) to the Pi's new static IP. Then snapshot
the Mango VM before the first attack.
