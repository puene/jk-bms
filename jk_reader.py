"""
jk_reader.py — BMS real-time data reader
All registers verified from Modbus captures & raw chunk dumps.
"""
import time, logging
from jk_registers import (
    RT_BASE, R_WIRE_RES, R_TEMP_MOS,
    R_BAT_VOL, R_BAT_WATT_H, R_BAT_WATT_L,
    R_BAT_CURR_H, R_BAT_CURR_L, R_TEMP_BAT1, R_TEMP_BAT2,
    R_SOC, R_SOH_REG, R_CAP_REMAIN_H, R_CAP_REMAIN_L,
    R_CAP_FULL_H, R_CAP_FULL_L, R_CYCLE_CAP,
    R_ALARM_H, R_ALARM_L,
    R_CYCLE_CNT, R_SYS_TICKS, R_CHG_DCH,
    R_RUNTIME_H, R_RUNTIME_L, ALARM_BITS,
)

log = logging.getLogger("jk_reader")

def _int16(r):   return r if r < 0x8000 else r - 0x10000
def _i32(h, l):
    v = (h << 16) | l; return v if v < 0x80000000 else v - 0x100000000
def _u32(h, l):  return (h << 16) | l
def _alarms(f):  return [v for k, v in ALARM_BITS.items() if f & (1 << k)]

def _chunk(client, start, slave, qty=20):
    try:
        r = client.read_holding_registers(address=start, count=qty, slave=slave)
        if hasattr(r, "registers") and r.registers:
            return r.registers
    except Exception as e:
        log.warning("chunk 0x%04X: %s", start, e)
    return None

def _chunk_safe(client, start, slave, qty=20, retries=2):
    """Like _chunk but with retry + small delay for BMS firmware that needs
    recovery time between consecutive Modbus requests."""
    import time
    for attempt in range(retries + 1):
        if attempt > 0:
            time.sleep(0.05)   # 50ms recovery time between retries
        try:
            r = client.read_holding_registers(address=start, count=qty, slave=slave)
            if hasattr(r, "registers") and r.registers:
                return r.registers
        except Exception as e:
            log.warning("chunk 0x%04X attempt %d: %s", start, attempt+1, e)
    return None

def _r(regs, base, addr):
    if regs is None: return 0
    i = addr - base
    return regs[i] if 0 <= i < len(regs) else 0

C0 = RT_BASE        # 0x1200  cell voltages
C1 = RT_BASE + 20   # 0x1214  wire resistance
C5 = RT_BASE + 100  # 0x1264  TempMos
C6 = RT_BASE + 120  # 0x1278  BatVol, BatWatt, BatCurrent, TempBat
C8 = RT_BASE + 160  # 0x12A0  SOC, SOH, Cap, CycleCap, Alarms
C9 = RT_BASE + 180  # 0x12B4  CycleCount, State

def read_bms(client, slave=1):
    d = {"read_ok": False, "error_msg": ""}
    try:
        # n=0: cell voltages
        c0 = _chunk_safe(client, C0, slave)
        if c0 is None:
            d["error_msg"] = "No response from BMS"; return d
        cell_mv = [c0[i] for i in range(7)]

        # n=1: wire resistance (UINT16 mΩ)
        c1 = _chunk_safe(client, C1, slave)
        cell_res = [_r(c1, C1, R_WIRE_RES[i]) for i in range(7)]

        # n=5: TempMos
        c5 = _chunk_safe(client, C5, slave)
        temp_mos = _int16(_r(c5, C5, R_TEMP_MOS)) * 0.1

        # n=6: BatVol, BatWatt, BatCurrent, TempBat
        c6 = _chunk_safe(client, C6, slave)
        pack_volt  = _r(c6, C6, R_BAT_VOL) / 1000.0
        # BatWatt INT32 mW — signed (negative = discharging)
        bat_watt   = _i32(_r(c6, C6, R_BAT_WATT_H), _r(c6, C6, R_BAT_WATT_L))
        pack_power = round(abs(bat_watt) / 1000.0, 1)   # always positive W
        pack_curr  = _i32(_r(c6, C6, R_BAT_CURR_H), _r(c6, C6, R_BAT_CURR_L)) / 1000.0
        temp_bat1  = _int16(_r(c6, C6, R_TEMP_BAT1)) * 0.1
        temp_bat2  = _int16(_r(c6, C6, R_TEMP_BAT2)) * 0.1

        # n=8: SOC, SOH, RemCap, FullCap, CycleCap, Alarms
        # Also contains CycleCount (0x12AE) and ChgDch (0x12B0) —
        # some firmware versions do NOT respond to chunk n=9 (0x12B4)
        # but these registers are already inside chunk n=8.
        c8 = _chunk_safe(client, C8, slave)
        soc        = _r(c8, C8, R_SOC) & 0xFF
        soh        = (_r(c8, C8, R_SOH_REG) >> 8) & 0xFF
        rem_cap    = _u32(_r(c8, C8, R_CAP_REMAIN_H), _r(c8, C8, R_CAP_REMAIN_L)) / 1000.0
        full_cap   = _u32(_r(c8, C8, R_CAP_FULL_H),   _r(c8, C8, R_CAP_FULL_L))   / 1000.0
        cycle_cap  = _r(c8, C8, R_CYCLE_CAP) / 1000.0
        alm_flg    = _u32(_r(c8, C8, R_ALARM_H), _r(c8, C8, R_ALARM_L))
        # n=9: CycleCount, ChgDch, SysTicks — may not respond on all firmware versions
        c9 = _chunk_safe(client, C9, slave)

        # CycleCount and ChgDch: try n=9 first, fall back to n=8
        # Both firmware versions store these at the same absolute addresses.
        # When c9=None the registers fall within c8's range (offsets 14 & 16).
        # NOTE: R_CYCLE_CNT=0x12B8 / R_CHG_DCH=0x12BA are offsets 24/26 from
        # C8=0x12A0 — OUT of c8's 20-register window — so use the c8-valid
        # addresses 0x12AE (offset 14) and 0x12B0 (offset 16) as fallbacks.
        R_CYCLE_CNT_C8 = 0x12AE
        R_CHG_DCH_C8   = 0x12B0
        R_SYS_TICKS_C8 = 0x12AF  # also valid in c8 (offset 15)
        if c9:
            cycle_cnt = _r(c9, C9, R_CYCLE_CNT)
            chg_dch   = _r(c9, C9, R_CHG_DCH)
        else:
            cycle_cnt = _r(c8, C8, R_CYCLE_CNT_C8)
            chg_dch   = _r(c8, C8, R_CHG_DCH_C8)

        # RunTime: direct read (returns 0 inside chunk)
        run_secs = 0
        try:
            rr = client.read_holding_registers(address=R_RUNTIME_H, count=2, slave=slave)
            if hasattr(rr, "registers") and len(rr.registers) >= 2:
                candidate = _u32(rr.registers[0], rr.registers[1])
                if 0 < candidate < 631_152_000:
                    run_secs = candidate
        except Exception as e:
            log.warning("RunTime: %s", e)
        if run_secs == 0:
            ticks = _r(c9, C9, R_SYS_TICKS) if c9 else _r(c8, C8, R_SYS_TICKS_C8)
            if ticks > 0:
                run_secs = int(ticks * 0.1)

        # Format: X Years Y Months Z Days
        years  = run_secs // (365 * 86400)
        remain = run_secs  % (365 * 86400)
        months = remain   // (30  * 86400)
        days   = (remain  %  (30  * 86400)) // 86400
        parts  = []
        if years:  parts.append(f"{years} Year{'s' if years > 1 else ''}")
        if months: parts.append(f"{months} Month{'s' if months > 1 else ''}")
        parts.append(f"{days} Day{'s' if days != 1 else ''}")
        run_str = " ".join(parts)

        valid = [v for v in cell_mv if v > 0]
        cmax = max(valid) if valid else 0
        cmin = min(valid) if valid else 0
        cavg = round(sum(valid) / len(valid), 1) if valid else 0.0

        d.update({
            "read_ok":     True,
            "timestamp":   time.time(),
            "cell_mv":     cell_mv,
            "cell_res":    cell_res,
            "pack_volt":   round(pack_volt, 3),
            "pack_curr":   round(pack_curr, 2),
            "pack_power":  pack_power,
            "soc":         soc,
            "soh":         soh,
            "rem_cap":     round(rem_cap, 2),
            "full_cap":    round(full_cap, 2),
            "cycle_cap":   round(cycle_cap, 1),
            "cycle_count": cycle_cnt,
            "temp_mos":    round(temp_mos, 1),
            "temp_bat1":   round(temp_bat1, 1),
            "temp_bat2":   round(temp_bat2, 1),
            "charging":    bool((chg_dch >> 8) & 0xFF),
            "discharging": bool(chg_dch & 0xFF),
            "balancing":   False,
            "run_str":     run_str,
            "run_secs":    run_secs,
            "alarm_flags": alm_flg,
            "alarms":      _alarms(alm_flg),
            "cell_max":    cmax,
            "cell_min":    cmin,
            "cell_diff":   cmax - cmin,
            "cell_avg":    cavg,
        })
    except Exception as e:
        d["error_msg"] = str(e)
        log.error("read_bms: %s", e, exc_info=True)
    return d
