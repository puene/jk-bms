"""
jk_config.py — Settings read/write for JK BMS
BUG FIX: config values are UINT32 (not just Lo-word)
  Hi-word can be non-zero for large values e.g. CapBatCell=120000 mAh
  Hi=1, Lo=54464 → (1<<16)|54464 = 120000 ✓
"""
import logging
from jk_registers import CONFIG_FIELDS, CFG_GROUP_NAMES

log = logging.getLogger("jk_config")

def _int16(lo):
    return lo if lo < 0x8000 else lo - 0x10000

def _u32(hi, lo):
    return (hi << 16) | lo

def decode_field(dtype, hi, lo):
    """Decode UINT32 (hi,lo) to (raw, display_value)."""
    raw_u32 = _u32(hi, lo)
    if dtype == "mv":
        return raw_u32, round(raw_u32 * 0.001, 3)      # mV → V
    elif dtype == "ma":
        return raw_u32, round(raw_u32 * 0.001, 1)      # mA → A
    elif dtype == "tc":
        # Temperature OT stored as INT32, but positive only
        # Use full INT32 in case Hi is 0xFFFF for some BMS
        raw_i32 = raw_u32 if raw_u32 < 0x80000000 else raw_u32 - 0x100000000
        return raw_i32, round(raw_i32 * 0.1, 1)
    elif dtype == "tcs":
        # Temperature UT stored as INT32 (signed, can be negative)
        raw_i32 = raw_u32 if raw_u32 < 0x80000000 else raw_u32 - 0x100000000
        return raw_i32, round(raw_i32 * 0.1, 1)
    else:
        return raw_u32, raw_u32   # s, raw

def read_config(client, slave=1):
    """Read all settings. Returns dict keyed by field key."""
    regs = {}
    for addr, qty, label in [
        (0x1000, 100, "chunk1"),   # covers 0x1000..0x1063
        (0x1064,  40, "chunk2"),   # covers 0x1064..0x108B (DevAddr at 0x1084)
    ]:
        try:
            r = client.read_holding_registers(address=addr, count=qty, slave=slave)
            if hasattr(r, "registers"):
                for i, v in enumerate(r.registers):
                    regs[addr + i] = v
            else:
                log.error("config %s: no registers", label)
        except Exception as e:
            log.error("config %s: %s", label, e)

    log.info("config: read %d registers", len(regs))

    result = {}
    for byte_off, key, label, dtype, unit, group in CONFIG_FIELDS:
        hi_reg = 0x1000 + byte_off // 2   # Hi-word (even address)
        lo_reg = hi_reg + 1               # Lo-word (odd address)
        hi = regs.get(hi_reg, 0)
        lo = regs.get(lo_reg, 0)
        raw, val = decode_field(dtype, hi, lo)
        result[key] = {
            "label":     label,
            "unit":      unit,
            "group":     group,
            "dtype":     dtype,
            "raw":       raw,          # full UINT32/INT32 raw value
            "value":     val,          # human-readable
            "write_off": byte_off,
        }
    return result

def write_setting(client, byte_off, value, slave=1):
    """Write one setting via FC16.
    value = raw integer in native unit (mV, mA, ×0.1°C etc.)
    For values > 65535, writes as proper UINT32 [Hi, Lo].
    """
    write_addr = 0x1000 + byte_off
    hi = (int(value) >> 16) & 0xFFFF
    lo = int(value) & 0xFFFF
    try:
        resp = client.write_registers(
            address=write_addr, values=[hi, lo], slave=slave)
        if resp and not hasattr(resp, "exception_code"):
            log.info("write 0x%04X = %d (Hi=%d Lo=%d) OK", write_addr, value, hi, lo)
            return True, f"0x{write_addr:04X}"
        return False, "Modbus write error"
    except Exception as e:
        return False, str(e)
