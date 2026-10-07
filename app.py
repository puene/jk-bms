#!/usr/bin/env python3
"""
app.py — JK BMS Phase 3 Web Dashboard
Flask (plain, no Socket.IO) | Python 3.9

Socket.IO was removed entirely: its long-polling transport was creating
enough concurrent HTTP connections/threads on the Pi to starve the BMS
poller thread of scheduling time — /api/status stayed 503 forever, with
the poller's first cycle only running once the process was interrupted.
REST polling (the browser hits /api/status every 2s) already covers all
the same functionality without that overhead, so this is a straight
simplification rather than a workaround.
"""
from __future__ import annotations
import os, re, sys, json, signal, threading, time, logging
from typing import Optional

from flask import Flask, jsonify, request
from pymodbus.client import ModbusSerialClient

from jk_reader import read_bms
from jk_config import read_config, write_setting
from jk_db     import init_db, maybe_log, query_history
from jk_ble    import JkBle

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("app")

PORT     = "/dev/ttyUSB0"
BAUDRATE = 115200
SLAVE    = 1
POLL_SEC = 1.0

# ── Communication interface (BLE default, or RS485) ─────────────────────────
# Persisted per Pi in comm_config.json (not part of the repo / update.sh).
COMM_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comm_config.json")
COMM_DEFAULT = {"interface": "ble", "ble_mac": None, "ble_name": None}
RELEASE_SEC  = 600     # "release BLE" button: let the JK phone app connect
MAC_RE       = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")

def _load_comm() -> dict:
    c = dict(COMM_DEFAULT)
    try:
        with open(COMM_FILE) as f:
            c.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as e:
        logging.getLogger("app").warning("comm_config.json: %s — using defaults", e)
    if c.get("interface") not in ("ble", "rs485"):
        c["interface"] = "ble"
    return c

def _save_comm(c: dict):
    tmp = COMM_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(c, f, indent=2)
    os.replace(tmp, COMM_FILE)

_comm_lock = threading.Lock()
_comm      = _load_comm()

def _on_ble_auto_pick(mac, name):
    with _comm_lock:
        _comm.update(ble_mac=mac, ble_name=name)
        _save_comm(_comm)

_ble = JkBle(on_auto_pick=_on_ble_auto_pick)

def _apply_comm():
    with _comm_lock:
        _ble.configure(enabled=_comm["interface"] == "ble", mac=_comm.get("ble_mac"))

def _install_shutdown_handler():
    """systemctl stop/restart sends SIGTERM: close BLE before exiting."""
    def _shutdown(*_):
        logging.getLogger("app").info("SIGTERM — closing BLE")
        _ble.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)

def _active_interface() -> Optional[str]:
    """Interface the poller reads from now: 'ble', 'rs485', or None
    (BLE released for the phone app and no RS485 adapter present)."""
    with _comm_lock:
        iface = _comm["interface"]
    if iface == "ble" and _ble.released_for() > 0:
        return "rs485" if os.path.exists(PORT) else None
    return iface

try:
    import board, adafruit_dht
    _dht = adafruit_dht.DHT22(board.D4); DHT_OK = True
except Exception:
    _dht = None; DHT_OK = False

app = Flask(__name__)
app.config["SECRET_KEY"] = "jkbms-p3"

_lock      = threading.Lock()   # protects _latest / _cfg_cache (data)
_port_lock = threading.Lock()   # protects _client / serial port access
_latest    = {}
_cfg_cache = {}
_cfg_dirty      = True
_cfg_dirty_after = 0.0   # epoch time: don't read config before this
_ambient   = {"temp": None, "hum": None, "ts": 0}
_client: Optional[ModbusSerialClient] = None

def _get_client():
    """Must be called while holding _port_lock."""
    global _client
    if _client is None:
        _client = ModbusSerialClient(port=PORT, baudrate=BAUDRATE,
            bytesize=8, parity="N", stopbits=1, timeout=1.0)
        if not _client.connect():
            _client = None
            raise ConnectionError(f"Cannot open {PORT}")
    return _client

def _poller():
    global _latest, _cfg_cache, _cfg_dirty, _client
    errs = 0
    cycle = 0
    while True:
        t0 = time.time()
        cycle += 1

        # read DHT22 first so ambient_temp is fresh when we log this cycle
        if DHT_OK and time.time() - _ambient["ts"] >= 10:
            try:
                t = _dht.temperature; h = _dht.humidity
                if t is not None:
                    _ambient.update({"temp": round(t,1), "hum": round(h,1), "ts": time.time()})
            except Exception: pass

        iface = _active_interface()
        if iface != "rs485":
            # BLE (or nothing): keep /dev/ttyUSB0 closed so a dead or missing
            # USB/RS485 adapter can't affect anything.
            with _port_lock:
                if _client is not None:
                    try: _client.close()
                    except Exception: pass
                    _client = None
            if iface == "ble":
                d = _ble.latest() or {"read_ok": False, "comm": "ble",
                    "error_msg": _ble.status()["error"] or "waiting for BLE data"}
            else:
                d = {"read_ok": False, "comm": None,
                     "error_msg": "BLE released for phone app, no RS485 adapter"}
            with _lock:
                _latest = d
            maybe_log(d, ambient_temp=_ambient.get("temp"))
            errs = 0
            time.sleep(max(0, POLL_SEC - (time.time() - t0)))
            continue

        try:
            with _port_lock:
                c = _get_client()
                d = read_bms(c, SLAVE)
                d["comm"] = "rs485"
                cfg_snapshot = None
                if _cfg_dirty and time.time() >= _cfg_dirty_after:
                    try:
                        _client.close()
                    except Exception:
                        pass
                    _client = None
                    time.sleep(0.5)
                    c = _get_client()
                    time.sleep(0.3)
                    cfg_snapshot = read_config(c, SLAVE)
            log.debug("poller cycle %d: read_ok=%s", cycle, d.get("read_ok"))
            with _lock:
                _latest = d
                if cfg_snapshot is not None:
                    _cfg_cache = cfg_snapshot
                    _cfg_dirty = False
                    log.info("config refreshed OK")
            maybe_log(d, ambient_temp=_ambient.get("temp"))   # log to DB every 60s
            errs = 0
        except Exception as e:
            errs += 1
            log.error("poller #%d: %s", errs, e, exc_info=True)
            if errs >= 5:
                with _port_lock:
                    try:
                        if _client: _client.close()
                    except Exception: pass
                    _client = None
                errs = 0

        time.sleep(max(0, POLL_SEC - (time.time() - t0)))

@app.route("/api/status")
def api_status():
    with _lock:
        if _latest.get("read_ok"):
            return jsonify(_latest)
        info = {"read_ok": False, "comm": _latest.get("comm"),
                "error_msg": _latest.get("error_msg", "")}
    return jsonify(info), 503

@app.route("/api/config")
def api_config():
    if _active_interface() == "ble":
        return jsonify(_ble.config())      # from BLE settings frame (read-only)
    with _lock: return jsonify(dict(_cfg_cache))

@app.route("/api/config/refresh")
def api_config_refresh():
    global _cfg_dirty
    if _active_interface() == "ble":
        _ble.refresh_config()
        return jsonify(_ble.config())
    _cfg_dirty = True
    with _lock:
        return jsonify(dict(_cfg_cache))

@app.route("/api/write", methods=["POST"])
def api_write():
    global _cfg_dirty
    if _active_interface() != "rs485":
        return jsonify({"ok": False,
                        "error": "Settings can only be written over RS485"}), 409
    body = request.get_json(force=True) or {}
    off  = body.get("write_off")
    val  = body.get("value")
    if not isinstance(off, int) or not isinstance(val, int):
        return jsonify({"ok": False, "error": "write_off and value must be integers"}), 400
    if not (0 <= off <= 0xFFFF):
        return jsonify({"ok": False, "error": "write_off out of range"}), 400
    if not (-2_147_483_648 <= val <= 4_294_967_295):
        return jsonify({"ok": False, "error": "value out of range"}), 400
    try:
        with _port_lock:
            c = _get_client()
            # Wait 0.5s after acquiring lock — BMS needs recovery time after
            # read_bms chunks before it will accept a write reliably
            time.sleep(0.5)
            ok, info = write_setting(c, off, val, SLAVE)
            if ok:
                time.sleep(0.3)   # let BMS settle before next config read
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    if ok:
        # BMS takes ~5s to save written value to flash.
        # Set _cfg_dirty after 6s in background so poller reads fresh value.
        def _mark_dirty_later():
            time.sleep(3)
            global _cfg_dirty, _cfg_dirty_after
            _cfg_dirty_after = time.time() + 2
            _cfg_dirty = True
            log.info("config marked dirty — will refresh on next poller cycle")
        threading.Thread(target=_mark_dirty_later, daemon=True).start()
    return jsonify({"ok": ok, "addr": info, "value": val})

@app.route("/api/comm")
def api_comm_get():
    with _comm_lock:
        c = dict(_comm)
    return jsonify({
        "interface":   c["interface"],
        "active":      _active_interface(),
        "ble":         dict(_ble.status(), name=c.get("ble_name")),
        "rs485":       {"port": PORT, "present": os.path.exists(PORT)},
        "release_sec": RELEASE_SEC,
    })

@app.route("/api/comm", methods=["POST"])
def api_comm_set():
    global _cfg_dirty
    body  = request.get_json(force=True) or {}
    iface = body.get("interface")
    if iface not in ("ble", "rs485"):
        return jsonify({"ok": False, "error": "interface must be 'ble' or 'rs485'"}), 400
    with _comm_lock:
        _comm["interface"] = iface
        if "ble_mac" in body:
            mac = (body.get("ble_mac") or "").strip().upper()
            if mac and not MAC_RE.match(mac):
                return jsonify({"ok": False, "error": "invalid MAC address"}), 400
            _comm["ble_mac"]  = mac or None
            _comm["ble_name"] = (body.get("ble_name") or "").strip() or None
        _save_comm(_comm)
    _apply_comm()
    _cfg_dirty = True
    log.info("comm set: %s mac=%s", iface, _comm.get("ble_mac"))
    return jsonify({"ok": True})

@app.route("/api/comm/scan", methods=["POST"])
def api_comm_scan():
    try:
        return jsonify({"ok": True, "devices": _ble.scan(8.0)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/comm/release", methods=["POST"])
def api_comm_release():
    body = request.get_json(force=True) or {}
    sec  = body.get("seconds", RELEASE_SEC)
    if not isinstance(sec, int) or not (0 <= sec <= 3600):
        return jsonify({"ok": False, "error": "seconds must be 0..3600"}), 400
    _ble.release(sec)
    log.info("BLE release: %ds", sec)
    return jsonify({"ok": True, "released_for": sec})

@app.route("/api/ambient")
def api_ambient(): return jsonify(_ambient)

@app.route("/api/history")
def api_history():
    """?range=24h|7d|30d"""
    rng = request.args.get("range", "24h").lower()
    hours = {"24h": 24, "7d": 168, "30d": 720}.get(rng, 24)
    rows = query_history(hours)
    return jsonify(rows)

@app.route("/")
def index():
    from jk_html import HTML
    return HTML

if __name__ == "__main__":
    init_db()
    _apply_comm()
    _install_shutdown_handler()
    log.info("JK BMS Phase 3 | comm=%s ble_mac=%s | %s @%d slave=%s poll=%.1fs DHT=%s",
             _comm["interface"], _comm.get("ble_mac"),
             PORT, BAUDRATE, SLAVE, POLL_SEC, DHT_OK)
    threading.Thread(target=_poller, daemon=True, name="poller").start()
    app.run(host="0.0.0.0", port=5000, debug=False,
            use_reloader=False, threaded=True)
