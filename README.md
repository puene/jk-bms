# JK BMS Monitor

Web dashboard + MQTT publisher for JK-B1A8S10P BMS via RS485 Modbus RTU.

**Hardware:** Raspberry Pi 4 · JK-B1A8S10P (7S 120Ah NMC) · CH341 USB-RS485 · DHT22 (GPIO4)

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/puene/jk-bms/main/install.sh | sudo bash
```

ทำให้ครบทุกอย่างใน 1 คำสั่ง:
- ติดตั้ง system packages
- ดาวน์โหลดไฟล์ทั้งหมด
- สร้าง Python venv + ติดตั้ง pip packages
- ตั้ง systemd services (boot อัตโนมัติ)
- Start ทันที

เมื่อเสร็จแล้วเปิด browser: `http://<pi-ip>:5000`

## Update (ทุกเครื่องพร้อมกัน)

```bash
sudo bash /home/pi/jk_bms/update.sh
```

## Files

| File | Description |
|---|---|
| `app.py` | Flask web dashboard + BMS poller |
| `jk_registers.py` | Verified Modbus register map |
| `jk_reader.py` | Real-time BMS data reader |
| `jk_config.py` | Settings read/write |
| `jk_db.py` | SQLite history logger (30 days) |
| `jk_html.py` | Dashboard HTML (3 tabs: Status/Settings/History) |
| `mqtt_publisher.py` | MQTT cloud publisher |
| `mqtt_config.yml` | MQTT broker config (edit with your credentials) |
| `requirements.txt` | Python dependencies |
| `install.sh` | One-line installer |
| `update.sh` | Update all files + restart services |

## MQTT Config

แก้ไข `/home/pi/jk_bms/mqtt_config.yml` ใส่ broker credentials แล้ว:
```bash
sudo systemctl restart jk_mqtt
```

## Logs

```bash
sudo journalctl -u jk_bms  -f   # dashboard
sudo journalctl -u jk_mqtt -f   # mqtt publisher
```

## Service Control

```bash
sudo systemctl status  jk_bms jk_mqtt
sudo systemctl restart jk_bms jk_mqtt
sudo systemctl stop    jk_bms jk_mqtt
```
