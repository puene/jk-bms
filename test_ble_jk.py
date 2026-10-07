#!/usr/bin/env python3
"""
JK BMS BLE Quick Test (JK02_32S) — READ-ONLY
อ่าน cell info ผ่าน BLE แล้วเทียบกับค่า RS485 จาก /api/status ของ Flask app

Protocol ref: https://github.com/syssi/esphome-jk-bms/blob/main/docs/protocol-design-ble.md
ส่งเฉพาะคำสั่ง 0x96 (cell info) และ 0x97 (device info) เท่านั้น — ไม่มีการเขียน setting

Run (บน Pi):
    timeout 90 ~/jk_bms/.venv-ble/bin/python ~/jk_bms/test_ble_jk.py
"""

import argparse
import asyncio
import json
import struct
import sys
import time
import urllib.request
from typing import Optional

from bleak import BleakClient, BleakScanner

BMS_MAC   = "28:D4:1E:09:D3:3A"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
API_URL   = "http://127.0.0.1:5000/api/status"
CELLS     = 7

CMD_HDR   = b"\xAA\x55\x90\xEB"
RESP_HDR  = b"\x55\xAA\xEB\x90"
FRAME_LEN = 300          # CRC = sum8(frame[0:299]) at frame[299]

CMD_CELL_INFO   = 0x96
CMD_DEVICE_INFO = 0x97
READ_ONLY_CMDS  = (CMD_CELL_INFO, CMD_DEVICE_INFO)


def build_cmd(cmd: int) -> bytes:
    """20-byte command: AA 55 90 EB + cmd + len + 4 value + pad + sum8 CRC."""
    if cmd not in READ_ONLY_CMDS:
        raise ValueError(f"cmd 0x{cmd:02X} not allowed (read-only script)")
    f = bytearray(20)
    f[0:4] = CMD_HDR
    f[4] = cmd
    f[19] = sum(f[:19]) & 0xFF
    return bytes(f)


class FrameAssembler:
    """Joins notify fragments into full frames and validates sum8 CRC."""

    def __init__(self):
        self.buf = bytearray()
        self.frames: "asyncio.Queue[bytes]" = asyncio.Queue()
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
            self.frames.put_nowait(frame)


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
        "uptime_s":     _u32(f, 38),
        "power_on_cnt": _u32(f, 42),
        "device_name":  _str(f, 46, 16),
    }


def decode_cell_info(f: bytes) -> dict:
    """JK02_32S frame type 0x02 — offsets from esphome-jk-bms (offset=16/32)."""
    cell_mv  = [_u16(f, 6 + 2 * i) for i in range(CELLS)]
    cell_res = [_u16(f, 80 + 2 * i) for i in range(CELLS)]
    valid = [v for v in cell_mv if v > 0]
    cmax = max(valid) if valid else 0
    cmin = min(valid) if valid else 0
    return {
        "cell_mv":      cell_mv,
        "cell_res":     cell_res,
        "cell_mask":    _u32(f, 70),               # enabled cells bitmask (7S → 0x7F)
        "cell_avg":     _u16(f, 74),
        "cell_diff":    _u16(f, 76),
        "cell_max":     cmax,
        "cell_min":     cmin,
        "temp_mos":     round(_i16(f, 144) * 0.1, 1),
        "pack_volt":    round(_u32(f, 150) / 1000.0, 3),
        "pack_power":   round(abs(_i32(f, 154)) / 1000.0, 1),
        "pack_curr":    round(_i32(f, 158) / 1000.0, 2),
        "temp_bat1":    round(_i16(f, 162) * 0.1, 1),
        "temp_bat2":    round(_i16(f, 164) * 0.1, 1),
        "alarm_raw":    _u32(f, 166),
        "balance_curr": round(_i16(f, 170) / 1000.0, 3),
        "balancing":    bool(f[172]),
        "soc":          f[173],
        "rem_cap":      round(_u32(f, 174) / 1000.0, 2),
        "full_cap":     round(_u32(f, 178) / 1000.0, 2),
        "cycle_count":  _u32(f, 182),
        "cycle_cap":    round(_u32(f, 186) / 1000.0, 1),
        "soh":          f[190],
        "run_secs":     _u32(f, 194),
        "charging":     bool(f[198]),
        "discharging":  bool(f[199]),
    }


def hexdump(f: bytes):
    for o in range(0, len(f), 16):
        print(f"  {o:3d}: " + " ".join(f"{x:02X}" for x in f[o:o + 16]))


def fetch_rs485() -> Optional[dict]:
    try:
        with urllib.request.urlopen(API_URL, timeout=3) as r:
            d = json.loads(r.read().decode())
        return d if d.get("read_ok") else None
    except Exception as e:
        print(f"WARN  อ่าน {API_URL} ไม่ได้: {e}")
        return None


async def fetch_rs485_after(t_ble: float, wait: float = 6.0) -> Optional[dict]:
    """Poll /api/status until the RS485 sample was taken after the BLE frame."""
    loop = asyncio.get_running_loop()
    end = time.time() + wait
    rs = None
    while time.time() < end:
        rs = await loop.run_in_executor(None, fetch_rs485)
        if rs and rs.get("timestamp", 0) >= t_ble:
            return rs
        await asyncio.sleep(0.3)
    return rs


def compare(ble: dict, rs: dict, verbose: bool = True) -> dict:
    """Print BLE vs RS485 table; return {field: diff} for numeric fields
    and {field: bool equal} for the rest."""
    rows = []
    for i in range(CELLS):
        rows.append((f"cell_mv[{i + 1}]", ble["cell_mv"][i], rs["cell_mv"][i]))
    for i in range(CELLS):
        rows.append((f"cell_res[{i + 1}]", ble["cell_res"][i], rs["cell_res"][i]))
    for k in ("cell_max", "cell_min", "cell_diff", "pack_volt", "pack_curr",
              "pack_power", "soc", "soh", "rem_cap", "full_cap", "cycle_count",
              "cycle_cap", "temp_mos", "temp_bat1", "temp_bat2",
              "charging", "discharging", "run_secs"):
        rows.append((k, ble.get(k), rs.get(k)))
    rows.append(("alarm_flags", f"0x{ble['alarm_raw']:08X}", f"0x{rs['alarm_flags']:08X}"))

    out = {}
    if verbose:
        print(f"\n  {'field':<14}{'BLE':>14}{'RS485':>14}{'diff':>12}")
        print("  " + "-" * 54)
    for name, b, r in rows:
        if isinstance(b, (int, float)) and isinstance(r, (int, float)) \
                and not isinstance(b, bool) and not isinstance(r, bool):
            diff = round(b - r, 3)
            out[name] = diff
            line = f"  {name:<14}{b:>14}{r:>14}{diff:>12}" + ("" if diff == 0 else "  *")
        else:
            out[name] = (b == r)
            line = f"  {name:<14}{str(b):>14}{str(r):>14}{'':>12}" + ("" if b == r else "  *")
        if verbose:
            print(line)
    return out


def print_summary(results: list):
    """Per-field mean/max |diff| over all time-matched samples."""
    print(f"\n=== Summary: {len(results)} time-matched samples ===")
    print(f"  {'field':<14}{'mean|diff|':>12}{'max|diff|':>12}")
    print("  " + "-" * 38)
    for k in results[0]:
        vals = [r[k] for r in results]
        if isinstance(vals[0], bool):
            n_eq = sum(vals)
            print(f"  {k:<14}{f'equal {n_eq}/{len(vals)}':>24}")
        else:
            a = [abs(v) for v in vals]
            print(f"  {k:<14}{round(sum(a) / len(a), 3):>12}{round(max(a), 3):>12}")


async def run(args) -> int:
    print("=== JK BMS BLE Test (JK02_32S, read-only) ===")
    print(f"MAC: {args.mac}")
    print("กด Ctrl+C เพื่อหยุด\n")

    dev = await BleakScanner.find_device_by_address(args.mac, timeout=args.scan_timeout)
    if dev is None:
        print(f"ERR  ไม่พบ {args.mac} ภายใน {args.scan_timeout}s")
        return 1
    print(f"Found: {dev.address}  {dev.name}")

    asm = FrameAssembler()
    got = 0
    results = []
    async with BleakClient(dev, timeout=20.0) as client:
        print("Connected")
        char = client.services.get_characteristic(CHAR_UUID)
        if char is None:
            print("ERR  ไม่พบ characteristic 0xFFE1")
            return 1
        with_resp = "write-without-response" not in char.properties
        print(f"FFE1 properties: {', '.join(char.properties)}")

        await client.start_notify(char, lambda _c, d: asm.feed(bytes(d)))
        try:
            for cmd in (CMD_CELL_INFO, CMD_DEVICE_INFO):
                await client.write_gatt_char(char, build_cmd(cmd), response=with_resp)
                await asyncio.sleep(0.3)

            deadline = time.monotonic() + args.timeout
            while got < args.frames:
                left = deadline - time.monotonic()
                if left <= 0:
                    print(f"ERR  timeout — ได้ cell info {got}/{args.frames} frame")
                    break
                try:
                    frame = await asyncio.wait_for(asm.frames.get(), timeout=left)
                except asyncio.TimeoutError:
                    continue
                ftype = frame[4]
                if ftype == 0x03:
                    print("\n[device info 0x03]")
                    for k, v in decode_device_info(frame).items():
                        print(f"  {k:<14}{v}")
                elif ftype == 0x01:
                    print("\n[settings 0x01] received (not decoded)")
                elif ftype == 0x02:
                    t_ble = time.time()
                    got += 1
                    ble = decode_cell_info(frame)
                    print(f"\n[cell info 0x02] #{got}  counter={frame[5]}  "
                          f"cell_mask=0x{ble['cell_mask']:08X}")
                    if args.hexdump:
                        hexdump(frame)
                    rs = await fetch_rs485_after(t_ble) if not args.no_compare else None
                    if rs:
                        gap = rs.get("timestamp", 0) - t_ble
                        print(f"  RS485 sample time - BLE frame time: {gap:+.1f}s")
                        diffs = compare(ble, rs, verbose=not args.summary_only)
                        if abs(gap) <= args.max_gap:
                            results.append(diffs)
                        else:
                            print(f"  (gap > {args.max_gap}s — not counted in summary)")
                    else:
                        print(json.dumps(ble, indent=2))
                    # drop frames queued while waiting for RS485 — keep pairs fresh
                    while not asm.frames.empty():
                        asm.frames.get_nowait()
                else:
                    print(f"\n[frame type 0x{ftype:02X}] ignored")
        finally:
            try:
                await client.stop_notify(char)
            except Exception:
                pass
    print(f"\nDisconnected.  CRC errors: {asm.crc_errors}")
    if results:
        print_summary(results)
    return 0 if got >= args.frames else 2


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--mac", default=BMS_MAC)
    p.add_argument("--frames", type=int, default=2, help="cell info frames to read")
    p.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for frames")
    p.add_argument("--scan-timeout", type=float, default=15.0)
    p.add_argument("--hexdump", action="store_true", help="print raw 0x02 frame")
    p.add_argument("--no-compare", action="store_true", help="skip RS485 /api/status compare")
    p.add_argument("--max-gap", type=float, default=2.0,
                   help="max |RS485 - BLE| sample time (s) to count in summary")
    p.add_argument("--summary-only", action="store_true", help="hide per-frame tables")
    args = p.parse_args()
    try:
        sys.exit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        print("\nหยุดโดยผู้ใช้")


if __name__ == "__main__":
    main()
