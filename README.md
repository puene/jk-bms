# JK BMS Monitor

Web dashboard + MQTT publisher for JK BMS, reading over **BLE (default)** or **RS485 Modbus RTU**.

**Hardware:** Raspberry Pi 3 / 4 / 5 / Zero W (built-in Bluetooth) · JK BMS (tested: JK-B1A8S10P, JK_BD6A20S10P, JK_BD6A24S10P; firmware 11.x, 15.x, 19.x, 21.x) · optional CH341 USB-RS485 · optional DHT22 (GPIO4)

## Quick Install

Requirements: Raspberry Pi OS with a user named **`pi`** (the installer uses `/home/pi`), SSH enabled, Bluetooth on (`bluetoothctl show` → `Powered: yes`).

```bash
curl -fsSL https://raw.githubusercontent.com/puene/jk-bms/main/install.sh | sudo bash
```

One command does everything:
- Installs system packages (incl. `bluez`) and sets the timezone to Asia/Bangkok
- Downloads all project files
- Creates the Python venv and installs pip packages (incl. `bleak`)
- Sets up systemd services (start automatically on boot)
- Starts the services immediately

When it finishes, open a browser at `http://<pi-ip>:5000`.

### After installing
1. Edit the MQTT settings for the site (broker, username, password, topic) — see [MQTT Config](#mqtt-config).
2. Select the BMS:
   - If exactly one JK BMS is in BLE range, it is selected automatically within about a minute.
   - Otherwise open **Settings → Communication → Scan** and press **Use** next to the right BMS. RSSI should be better than −75 dBm.
3. Check:
   ```bash
   systemctl is-active jk_bms jk_mqtt; curl -s localhost:5000/api/status | head -c 200; echo
   ```
   Expect `active` twice and `"read_ok":true`.

## Update

Run on each Pi (keeps `mqtt_config.yml` and `comm_config.json`):

```bash
curl -fsSL https://raw.githubusercontent.com/puene/jk-bms/main/update.sh | sudo bash
```

`update.sh` also updates itself, so `sudo bash /home/pi/jk_bms/update.sh` works too once a recent version is installed.

## Communication: BLE or RS485

Choose in **Settings → Communication** (stored per Pi in `comm_config.json`; default BLE).

- **BLE** — read-only (only commands 0x96/0x97 are sent). `/dev/ttyUSB0` is never opened. BMS settings are shown read-only.
- **RS485** — Modbus RTU, 115200 8N1, slave 1, `/dev/ttyUSB0`. BMS settings can be edited from the Settings tab.
- **Release BLE 10 min** — disconnects the Pi so the JK phone app can connect (the BMS accepts one BLE connection at a time). If an RS485 adapter is present, the Pi reads over RS485 meanwhile.
- Writing BMS settings over BLE is not supported yet.

### BLE troubleshooting
- `http://<pi-ip>:5000/api/comm` shows the BLE state: `error`, `last_frame_age` and `frames` (frames received per type; `0x02` = cell data).
- `device ... not found`: weak signal or another device (e.g. a phone with the JK app) is connected to the BMS. Move the Pi closer / out of metal cabinets.
- Pi 3/4 share one chip for Wi-Fi and Bluetooth. If the Pi is on LAN, turning Wi-Fi off can help (connect over the LAN IP first): `sudo rfkill block wifi` (undo: `sudo rfkill unblock wifi`).

## Files

| File | Description |
|---|---|
| `app.py` | Flask web dashboard + BMS poller + interface selection |
| `jk_ble.py` | BLE reader (JK02_32S protocol, read-only) |
| `jk_registers.py` | Verified Modbus register map + alarm bits |
| `jk_reader.py` | Real-time BMS data reader (RS485) |
| `jk_config.py` | Settings read/write (RS485) |
| `jk_db.py` | SQLite history logger (30 days) |
| `jk_html.py` | Dashboard HTML (3 tabs: Status/Settings/History) |
| `mqtt_publisher.py` | MQTT cloud publisher |
| `mqtt_config.yml` | MQTT broker config template (edit with your credentials) |
| `requirements.txt` | Python dependencies |
| `install.sh` | One-line installer |
| `update.sh` | Update all files + restart services |
| `test_ble_jk.py` | Standalone BLE test: compares BLE readings with RS485 |

## MQTT Config

Edit `/home/pi/jk_bms/mqtt_config.yml` with the broker credentials and the site topic, then:
```bash
sudo systemctl restart jk_mqtt
```

## Logs

```bash
sudo journalctl -u jk_bms  -f   # dashboard + BMS reader
sudo journalctl -u jk_mqtt -f   # mqtt publisher
```

## Service Control

```bash
sudo systemctl status  jk_bms jk_mqtt
sudo systemctl restart jk_bms jk_mqtt
sudo systemctl stop    jk_bms jk_mqtt
```
