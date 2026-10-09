"""
jk_ble.py — JK BMS BLE reader (JK02_32S protocol), READ-ONLY
Python 3.9 | bleak

Keeps one BLE connection open in a background thread (own asyncio loop) and
turns the BMS notify stream into the same dict shape as jk_reader.read_bms(),
so the web page / MQTT / DB see identical data whichever interface is used.

Only commands 0x96 (cell info + settings) and 0x97 (device info) are ever
sent — no BMS setting is written over BLE.

Ref: https://github.com/syssi/esphome-jk-bms/blob/main/docs/protocol-design-ble.md
"""
import asyncio
import logging
import struct
import threading
import time
from typing import Optional

from bleak import BleakClient, BleakScanner

from jk_registers import CONFIG_FIELDS, ALARM_BITS
from jk_config import decode_field
from jk_reader import format_runtime

log = logging.getLogger("jk_ble")

SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHAR_UUID    = "0000ffe1-0000-1000-8000-00805f9b34fb"

CMD_HDR   = b"\xAA\x55\x90\xEB"
RESP_HDR  = b"\x55\xAA\xEB\x90"
FRAME_LEN = 300          # CRC = sum8(frame[0:299]) at frame[299]

CMD_CELL_INFO   = 0x96
CMD_DEVICE_INFO = 0x97
READ_ONLY_CMDS  = (CMD_CELL_INFO, CMD_DEVICE_INFO)

FRAME_TIMEOUT  = 20.0    # reconnect if no cell-info frame for this long
CELL_RETRY_SEC = 6.0     # resend 0x96 if the cell-info stream has not started
AUTO_PICK_SEC  = 60.0    # scan interval while no MAC is configured


def build_cmd(cmd: int) -> bytes:
    """20-byte command: AA 55 90 EB + cmd + len + 4 value + pad + sum8 CRC."""
    if cmd not in READ_ONLY_CMDS:
        raise ValueError(f"cmd 0x{cmd:02X} not allowed (read-only)")
    f = bytearray(20)
    f[0:4] = CMD_HDR
    f[4] = cmd
    f[19] = sum(f[:19]) & 0xFF
    return bytes(f)


def _u16(b, o): return struct.unpack_from("<H", b, o)[0]
def _i16(b, o): return struct.unpack_from("<h", b, o)[0]
def _u32(b, o): return struct.unpack_from("<I", b, o)[0]
def _i32(b, o): return struct.unpack_from("<i", b, o)[0]
def _str(b, o, n): return b[o:o + n].split(b"\x00")[0].decode("ascii", "replace")


def decode_device_info(f: bytes) -> dict:
    return {
        "model":        _str(f, 6, 16),
        "hw_version":   _str(f, 22, 8),
        "sw_version":   _str(f, 30, 8),
        "power_on_cnt": _u32(f, 42),
        "device_name":  _str(f, 46, 16),
    }


def decode_cell_info(f: bytes) -> dict:
    """Frame type 0x02 → same keys as jk_reader.read_bms().
    Offsets: esphome-jk-bms JK02_32S; verified against RS485 on 2026-10-07."""
    mask  = _u32(f, 70)                          # enabled cells bitmask (7S → 0x7F)
    cells = min(bin(mask).count("1"), 32) or 7
    cell_mv  = [_u16(f, 6 + 2 * i) for i in range(cells)]
    cell_res = [_u16(f, 80 + 2 * i) for i in range(cells)]
    valid = [v for v in cell_mv if v > 0]
    cmax = max(valid) if valid else 0
    cmin = min(valid) if valid else 0
    cavg = round(sum(valid) / len(valid), 1) if valid else 0.0
    run_secs = _u32(f, 194)
    alm_flg = _u32(f, 166)       # AlarmSta, same word as RS485 0x12A0/A1
    return {
        "read_ok":      True,
        "error_msg":    "",
        "timestamp":    time.time(),
        "cell_mv":      cell_mv,
        "cell_res":     cell_res,
        "pack_volt":    round(_u32(f, 150) / 1000.0, 3),
        "pack_curr":    round(_i32(f, 158) / 1000.0, 2),
        "pack_power":   round(abs(_i32(f, 154)) / 1000.0, 1),
        "soc":          f[173],
        "soh":          f[190],
        "rem_cap":      round(_u32(f, 174) / 1000.0, 2),
        "full_cap":     round(_u32(f, 178) / 1000.0, 2),
        "cycle_cap":    round(_u32(f, 186) / 1000.0, 1),
        "cycle_count":  _u32(f, 182),
        "temp_mos":     round(_i16(f, 144) * 0.1, 1),
        "temp_bat1":    round(_i16(f, 162) * 0.1, 1),
        "temp_bat2":    round(_i16(f, 164) * 0.1, 1),
        "charging":     bool(f[198]),
        "discharging":  bool(f[199]),
        "balancing":    bool(f[172]),
        "balance_curr": round(_i16(f, 170) / 1000.0, 3),
        "run_str":      format_runtime(run_secs),
        "run_secs":     run_secs,
        "alarm_flags":  alm_flg,
        "alarms":       [v for k, v in ALARM_BITS.items() if alm_flg & (1 << k)],
        "cell_max":     cmax,
        "cell_min":     cmin,
        "cell_diff":    cmax - cmin,
        "cell_avg":     cavg,
    }


def decode_settings(f: bytes) -> dict:
    """Frame type 0x01 → same dict as jk_config.read_config().
    The settings frame is the Modbus config area as little-endian UINT32s:
    field at Modbus byte_off sits at frame offset 6 + byte_off."""
    result = {}
    for byte_off, key, label, dtype, unit, group in CONFIG_FIELDS:
        raw_u32 = _u32(f, 6 + byte_off)
        raw, val = decode_field(dtype, raw_u32 >> 16, raw_u32 & 0xFFFF)
        result[key] = {
            "label":     label,
            "unit":      unit,
            "group":     group,
            "dtype":     dtype,
            "raw":       raw,
            "value":     val,
            "write_off": byte_off,
        }
    return result


class _FrameAssembler:
    """Joins notify fragments into 300-byte frames and validates sum8 CRC."""

    def __init__(self, on_frame):
        self.buf = bytearray()
        self.on_frame = on_frame
        self.crc_errors = 0

    def feed(self, data: bytes):
        if data[:4] == RESP_HDR:
            self.buf = bytearray()
        elif not self.buf:
            return                      # tail of a longer frame (e.g. 320 B) — skip
        self.buf.extend(data)
        if len(self.buf) >= FRAME_LEN:
            frame = bytes(self.buf)
            self.buf = bytearray()
            if sum(frame[:FRAME_LEN - 1]) & 0xFF != frame[FRAME_LEN - 1]:
                self.crc_errors += 1
                return
            self.on_frame(frame)


class JkBle:
    """Background BLE reader. All public methods are thread-safe."""

    def __init__(self, on_auto_pick=None):
        self._lock = threading.Lock()
        self._mac: Optional[str] = None
        self._enabled = False
        self._released_until = 0.0
        self._cfg_request = False
        self._on_auto_pick = on_auto_pick   # callback(mac, name) when auto-selected

        self._latest: Optional[dict] = None
        self._config: dict = {}
        self._device_info: dict = {}
        self._connected = False
        self._last_frame = 0.0
        self._error = ""
        self._crc_errors = 0
        self._frame_counts: dict = {}
        self._devinfo_evt: Optional[asyncio.Event] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bt_lock: Optional[asyncio.Lock] = None
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True, name="ble").start()
        self._ready.wait(5)

    # ── public API ────────────────────────────────────────────────────────
    def configure(self, enabled: bool, mac: Optional[str]):
        with self._lock:
            mac = mac.upper() if mac else None
            if mac != self._mac:
                self._latest, self._config, self._device_info = None, {}, {}
            self._enabled, self._mac = enabled, mac

    def latest(self) -> Optional[dict]:
        """Last cell-info dict, or None if older than FRAME_TIMEOUT."""
        with self._lock:
            d = self._latest
            if d and time.time() - d["timestamp"] <= FRAME_TIMEOUT:
                return dict(d, comm="ble")
            return None

    def config(self) -> dict:
        with self._lock:
            return dict(self._config)

    def refresh_config(self):
        with self._lock:
            self._cfg_request = True

    def release(self, seconds: float):
        """Disconnect and stay off BLE (e.g. for the JK phone app). 0 = resume."""
        with self._lock:
            self._released_until = time.time() + seconds if seconds > 0 else 0.0

    def released_for(self) -> float:
        with self._lock:
            return max(0.0, self._released_until - time.time())

    def status(self) -> dict:
        with self._lock:
            age = time.time() - self._last_frame if self._last_frame else None
            return {
                "enabled":     self._enabled,
                "mac":         self._mac,
                "connected":   self._connected,
                "last_frame_age": round(age, 1) if age is not None else None,
                "device_info": dict(self._device_info),
                "error":       self._error,
                "crc_errors":  self._crc_errors,
                "frames":      dict(self._frame_counts),   # frames received by type
                "released_for": max(0, int(self._released_until - time.time())),
            }

    def shutdown(self, timeout: float = 5.0):
        """Disconnect cleanly (call before process exit) so BlueZ does not
        keep a stale link that stops the BMS advertising."""
        with self._lock:
            self._enabled = False
        end = time.time() + timeout
        while time.time() < end:
            with self._lock:
                if not self._connected:
                    return
            time.sleep(0.1)

    def scan(self, timeout: float = 8.0) -> list:
        """Blocking scan for devices advertising service 0xFFE0."""
        fut = asyncio.run_coroutine_threadsafe(self._scan(timeout), self._loop)
        return fut.result(timeout + 30)

    # ── BLE thread ────────────────────────────────────────────────────────
    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._bt_lock = asyncio.Lock()
        self._ready.set()
        self._loop.run_until_complete(self._main())

    def _want(self) -> Optional[str]:
        """MAC to be connected to right now, or None."""
        with self._lock:
            if not self._enabled or time.time() < self._released_until:
                return None
            return self._mac

    async def _main(self):
        backoff = 5.0
        last_pick = 0.0
        while True:
            with self._lock:
                need_pick = self._enabled and not self._mac
            if need_pick:
                if time.time() - last_pick >= AUTO_PICK_SEC:
                    last_pick = time.time()
                    await self._auto_pick()
                await asyncio.sleep(1)
                continue
            mac = self._want()
            if not mac:
                await asyncio.sleep(1)
                continue
            try:
                await self._session(mac)
                backoff = 5.0
            except Exception as e:
                with self._lock:
                    self._error = str(e) or e.__class__.__name__
                log.warning("BLE %s: %s", mac, self._error)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _clear_stale_link(self, mac: str) -> bool:
        """A BMS that is still connected (e.g. link left open by a killed
        process) does not advertise. Ask BlueZ to drop such a stale link."""
        async def run(*args):
            p = await asyncio.create_subprocess_exec(
                "bluetoothctl", *args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL)
            out, _ = await asyncio.wait_for(p.communicate(), 10)
            return out.decode(errors="replace")
        try:
            if "Connected: yes" not in await run("info", mac):
                return False
            log.warning("BLE %s: stale BlueZ link — disconnecting", mac)
            await run("disconnect", mac)
            return True
        except Exception as e:
            log.warning("BLE %s: bluetoothctl: %s", mac, e)
            return False

    async def _session(self, mac: str):
        async with self._bt_lock:
            dev = await BleakScanner.find_device_by_address(mac, timeout=15.0)
        if dev is None:
            if await self._clear_stale_link(mac):
                raise RuntimeError(f"cleared stale link to {mac}, retrying")
            raise RuntimeError(f"device {mac} not found")

        gone = asyncio.Event()
        client = BleakClient(dev, timeout=20.0, disconnected_callback=lambda _c: gone.set())
        asm = _FrameAssembler(self._on_frame)
        async with self._bt_lock:
            await client.connect()
        try:
            char = client.services.get_characteristic(CHAR_UUID)
            if char is None:
                raise RuntimeError("characteristic 0xFFE1 not found")
            resp = "write-without-response" not in char.properties
            await client.start_notify(char, lambda _c, d: asm.feed(bytes(d)))
            # Same order as esphome-jk-bms: device info (0x97) first, then
            # cell info (0x96). Some firmware (e.g. 15.x) stops the cell-info
            # stream if 0x97 arrives after 0x96.
            self._devinfo_evt = asyncio.Event()
            await client.write_gatt_char(char, build_cmd(CMD_DEVICE_INFO), response=resp)
            try:
                await asyncio.wait_for(self._devinfo_evt.wait(), 3.0)
            except asyncio.TimeoutError:
                log.info("BLE %s: no device info within 3s, continuing", mac)
            await client.write_gatt_char(char, build_cmd(CMD_CELL_INFO), response=resp)
            last_96 = time.time()
            with self._lock:
                self._connected, self._error = True, ""
                self._last_frame = time.time()
            log.info("BLE connected: %s (%s)", mac, dev.name)

            while self._want() == mac:
                if gone.is_set():
                    raise RuntimeError("disconnected by device")
                now = time.time()
                with self._lock:
                    quiet = now - self._last_frame
                    want_cfg, self._cfg_request = self._cfg_request, False
                    self._crc_errors = asm.crc_errors
                if quiet > FRAME_TIMEOUT:
                    raise RuntimeError(f"no data for {FRAME_TIMEOUT:.0f}s")
                if want_cfg or (quiet > CELL_RETRY_SEC and now - last_96 > CELL_RETRY_SEC):
                    # 0x96 (re)starts the cell-info stream and makes the BMS
                    # resend its settings frame (0x01)
                    await client.write_gatt_char(char, build_cmd(CMD_CELL_INFO), response=resp)
                    last_96 = now
                await asyncio.sleep(0.5)
        finally:
            with self._lock:
                self._connected = False
            try:
                await client.disconnect()
            except Exception:
                pass
            log.info("BLE disconnected: %s", mac)

    def _on_frame(self, frame: bytes):
        ftype = frame[4]
        with self._lock:
            k = f"0x{ftype:02X}"
            self._frame_counts[k] = self._frame_counts.get(k, 0) + 1
        try:
            if ftype == 0x02:
                d = decode_cell_info(frame)
                with self._lock:
                    self._latest, self._last_frame = d, d["timestamp"]
            elif ftype == 0x01:
                cfg = decode_settings(frame)
                with self._lock:
                    self._config = cfg
                log.info("BLE settings frame received")
            elif ftype == 0x03:
                info = decode_device_info(frame)
                with self._lock:
                    self._device_info = info
                if self._devinfo_evt is not None:
                    self._devinfo_evt.set()
        except Exception as e:
            log.warning("BLE frame 0x%02X decode: %s", ftype, e)

    async def _scan(self, timeout: float) -> list:
        async with self._bt_lock:
            found = await BleakScanner.discover(timeout=timeout, return_adv=True)
        out = []
        for dev, adv in found.values():
            if SERVICE_UUID in [u.lower() for u in adv.service_uuids]:
                out.append({"mac": dev.address.upper(),
                            "name": adv.local_name or dev.name or "",
                            "rssi": adv.rssi})
        out.sort(key=lambda x: x["rssi"], reverse=True)
        return out

    async def _auto_pick(self):
        """No MAC configured: if exactly one JK device is in range, use it."""
        try:
            devs = await self._scan(8.0)
        except Exception as e:
            log.warning("BLE auto-pick scan: %s", e)
            return
        if len(devs) != 1:
            with self._lock:
                self._error = (f"{len(devs)} BLE devices found — select one in Settings"
                               if devs else "no JK BMS found over BLE")
            return
        mac, name = devs[0]["mac"], devs[0]["name"]
        log.info("BLE auto-picked %s (%s)", mac, name)
        with self._lock:
            self._mac = mac
        if self._on_auto_pick:
            self._on_auto_pick(mac, name)
