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
import os, threading, time, logging
from typing import Optional

from flask import Flask, jsonify, request
from pymodbus.client import ModbusSerialClient

from jk_reader import read_bms
from jk_config import read_config, write_setting
from jk_db     import init_db, maybe_log, query_history

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("app")

PORT     = "/dev/ttyUSB0"
BAUDRATE = 115200
SLAVE    = 1
POLL_SEC = 1.0

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
_cfg_dirty = True
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

        try:
            with _port_lock:
                c = _get_client()
                d = read_bms(c, SLAVE)
                cfg_snapshot = None
                if _cfg_dirty:
                    time.sleep(0.2)   # BMS needs recovery time after read_bms chunks
                    cfg_snapshot = read_config(c, SLAVE)
            log.debug("poller cycle %d: read_ok=%s", cycle, d.get("read_ok"))
            with _lock:
                _latest = d
                if cfg_snapshot is not None:
                    _cfg_cache = cfg_snapshot
                    _cfg_dirty = False
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
    return jsonify({"read_ok": False}), 503

@app.route("/api/config")
def api_config():
    with _lock: return jsonify(dict(_cfg_cache))

@app.route("/api/config/refresh")
def api_config_refresh():
    global _cfg_dirty
    # Mark dirty so poller reads config on its next cycle
    _cfg_dirty = True
    # Wait up to 15s for poller to complete a full cycle and clear the flag
    deadline = time.time() + 15.0
    while time.time() < deadline:
        time.sleep(0.2)
        with _lock:
            if not _cfg_dirty:   # poller cleared it = fresh data ready
                return jsonify(dict(_cfg_cache))
    # Timed out — return whatever we have
    with _lock:
        return jsonify(dict(_cfg_cache))

@app.route("/api/write", methods=["POST"])
def api_write():
    global _cfg_dirty
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
            ok, info = write_setting(c, off, val, SLAVE)
            if ok:
                time.sleep(0.3)   # let BMS settle before next config read
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    if ok: _cfg_dirty = True
    return jsonify({"ok": ok, "addr": info, "value": val})

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
    log.info("JK BMS Phase 3 | %s @%d slave=%s poll=%.1fs DHT=%s",
             PORT, BAUDRATE, SLAVE, POLL_SEC, DHT_OK)
    threading.Thread(target=_poller, daemon=True, name="poller").start()
    app.run(host="0.0.0.0", port=5000, debug=False,
            use_reloader=False, threaded=True)
