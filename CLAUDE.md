# JK BMS Monitoring — Claude Code context

## How to reach the hardware
- Code runs on a Raspberry Pi 4, reached via SSH alias `jkpi` (see ~/.ssh/config). Key auth only — never type or store passwords.
- Run every hardware/runtime command as: `ssh jkpi "<command>"`
- Project dir on Pi: `~/jk_bms/`, venv: `~/jk_bms/.venv` → use `~/jk_bms/.venv/bin/python`
- Copy files to Pi: `scp <file> jkpi:~/jk_bms/`
- Long-running tests: always wrap with `timeout <sec>` or run with `nohup ... > /tmp/<name>.log 2>&1 &` and tail the log. Never leave a BLE connection open after a test.

## Platform
- Pi 4, Linux 6.1.21-v8+, Python 3.9 — Python 3.9-compatible syntax only (use `Optional[dict]`, never `dict | None`)
- Stack: pymodbus, flask 2.3.3, markupsafe 2.1.5, adafruit-circuitpython-dht, pyserial; BLE work uses `bleak`
- DHT22 on GPIO4 (`board.D4`)

## BMS
- JK-B1A8S10P, HW V21H, SW V21.00, Li-ion NMC 7S 120Ah
- BLE device info (0x03) of the same unit reports `JK_BD6A20S10P`, HW 19H, SW 19.13 (verified same unit via matching uptime + cell resistances, 2026-10-07)
- BLE: MAC `28:D4:1E:09:D3:3A`, name `NMC24120_012`; no pairing/PIN needed. Test venv on Pi: `~/jk_bms/.venv-ble` (bleak 1.1.1)
- Primary comms: RS485 Modbus RTU FC03, 115200 8N1, slave ID 1, `/dev/ttyUSB0` (CH341)
- Modbus reads must be chunk-aligned: start = 0x1200 + n×20, qty = 20; max qty 125
- SOC at 0x1299: mask low byte only (`& 0xFF`)
- Wire-resistance registers vary by firmware; fall back to chunk 0x1243–0x1249

## Current task: BLE reader (branch `ble`)
- Protocol: JK02_32S, ref https://github.com/syssi/esphome-jk-bms/blob/main/docs/protocol-design-ble.md
- Service 0xFFE0, characteristic 0xFFE1 (write + notify)
- Command = 20 bytes: `AA 55 90 EB` + cmd + len + 10 data + counter + `00 00` + sum8 CRC
- Sequence: subscribe notify → send 0x96 → send 0x97 → BMS streams frame type 0x02 (cell info)
- Responses start `55 AA EB 90`, fragmented, assemble to 300–320 bytes, validate sum8 CRC
- Build as a standalone script (`test_ble_jk.py`, style like `test_dht22.py`) — read-only.

## Hard rules
- NEVER write BMS settings (no FC16, no `jk_proto_writer.py`, no POST to `/api/write`, no BLE write commands other than 0x96/0x97) unless the user explicitly asks in this session.
- Do not modify `app.py`, `mqtt_publisher.py`, `jk-mqtt.service`, or restart running services without asking.
- Do not touch `/dev/ttyUSB0` while the Flask app or poller is running (port conflict) — check with `ssh jkpi "fuser /dev/ttyUSB0"` first.
- Test on one Pi first; multi-Pi rollout via `update.sh` only after the user approves.
