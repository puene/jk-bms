"""
jk_registers.py — JK-B1A8S10P HW:V21H SW:V21.00
ALL addresses VERIFIED from raw register dump on hardware.

Chunk rule: start = RT_BASE + n*20, qty=20
"""
RT_BASE = 0x1200

# ── Real-time registers (all VERIFIED) ───────────────────────────────────────

# n=0  0x1200: cell voltages UINT16 mV
R_CELL_MV  = [RT_BASE + i for i in range(8)]   # 0x1200..0x1207

# n=1  0x1214: wire resistance UINT16 mΩ
R_WIRE_RES = [RT_BASE + 0x25 + i for i in range(8)]  # 0x1225..0x122C

# n=4  0x1250: RunTime UINT32 seconds at 0x125E/5F
R_RUNTIME_H = RT_BASE + 0x5E   # 0x125E
R_RUNTIME_L = RT_BASE + 0x5F   # 0x125F

# n=5  0x1264: TempMos INT16 ×0.1°C at 0x1277
R_TEMP_MOS  = RT_BASE + 0x77   # 0x1277

# n=6  0x1278: BatVol, BatWatt, BatCurrent, TempBat1/2
# VERIFIED from raw dump (chunk 0x1278 offsets):
#   [13] 0x1285 = 28264 → BatVol  UINT16 mV
#   [14] 0x1286 = 0x0000 \
#   [15] 0x1287 = 0xE687  → BatWatt UINT32 mW  ÷1000 = W
#   [16] 0x1288 = 0xFFFF \
#   [17] 0x1289 = 0xF7D8  → BatCurrent INT32 mA
#   [18] 0x128A = 0x0132  → TempBat1 INT16 ×0.1°C
#   [19] 0x128B = 0x0131  → TempBat2 INT16 ×0.1°C
R_BAT_VOL    = RT_BASE + 0x85   # 0x1285  UINT16 mV
R_BAT_WATT_H = RT_BASE + 0x86   # 0x1286  UINT32 mW Hi
R_BAT_WATT_L = RT_BASE + 0x87   # 0x1287  UINT32 mW Lo
R_BAT_CURR_H = RT_BASE + 0x88   # 0x1288  INT32 Hi
R_BAT_CURR_L = RT_BASE + 0x89   # 0x1289  INT32 Lo
R_TEMP_BAT1  = RT_BASE + 0x8A   # 0x128A  INT16 ×0.1°C
R_TEMP_BAT2  = RT_BASE + 0x8B   # 0x128B  INT16 ×0.1°C

# n=8  0x12A0: AlarmSta UINT32 at 0x12A0/A1 (JK RS485 Modbus V1.0), then
# BalanCurrent, SOC, capacities ... Previously read from 0x12B2/B3 (wrong).
# Cross-checked 2026-10-07: BLE cell-info offset 166 = same alarm word.
R_ALARM_H      = 0x12A0
R_ALARM_L      = 0x12A1

# n=9  0x12B4: SOC, Cap, Cycle, State — VERIFIED from chunk dump 2026-06-12
#   0x12A3 LoByte = SOC%  (offset 15 from 0x12B4? — check: 0x12A3 in chunk n=8!)
#
# CORRECTED: data confirmed in chunk n=9 (0x12B4):
#   0x12B8 = 5       → CycleCount ✓
#   0x12B9 = 43111   → SysRunTicks ×0.1s (session)
#   0x12BA = 0x0101  → HiByte=Charge(1), LoByte=Discharge(1) ✓
#
# SOC/Cap stay in chunk n=8 at 0x12A3/A4/A5/A6/A7 (verified earlier)
R_SOC          = 0x12A3   # chunk n=8, LoByte=SOC%  (HiByte=0, NOT SOH)
R_CAP_REMAIN_H = 0x12A4   # chunk n=8, UINT32 mAh Hi
R_CAP_REMAIN_L = 0x12A5
R_CAP_FULL_H   = 0x12A6   # chunk n=8, UINT32 mAh Hi  (SOCFullChargeCap)
R_CAP_FULL_L   = 0x12A7
# CycleCount / CycleCap: UINT32 pairs in chunk n=8.
# Reading CycleCap as UINT16 at 0x12AB only gave the low word (wrapped every
# 65.5 Ah). Cross-checked vs BLE frame 2026-10-07: CycleCount=25, CycleCap=3043300 mAh.
R_CYCLE_CNT_H  = 0x12A8   # UINT32 cycles Hi
R_CYCLE_CNT_L  = 0x12A9
R_CYCLE_CAP_H  = 0x12AA   # UINT32 mAh Hi (total Ah cycled)
R_CYCLE_CAP_L  = 0x12AB
# SOH: HiByte of 0x12AC = 100%
# VERIFIED: 0x12AC = 0x6400 → HiByte=100=SOH%, LoByte=0 ✓
R_SOH_REG      = 0x12AC   # HiByte = SOH%
R_CYCLE_CNT    = 0x12B8   # chunk n=9 — NOT CycleCount (RunTime Hi word); unused
R_SYS_TICKS    = 0x12B9   # chunk n=9 — NOT ticks (RunTime Lo word); unused
R_CHG_DCH      = 0x12BA   # chunk n=9, HiByte=Charge LoByte=Discharge

# RunTime: MUST be read directly (BMS returns 0 when read as part of chunk)
# VERIFIED from Modbus capture: Tx 0x12BC count=2 → Rx 0x0005A823 = 370723s = 4D ✓
R_RUNTIME_H    = 0x12BC   # direct read only
R_RUNTIME_L    = 0x12BD
# Same RunTime is also readable inside chunk n=8 as UINT32 at 0x12AE/AF.
# VERIFIED 2026-10-07: 0x12AE=119, 0x12AF=46378 → 7845162 s ≈ run_secs.
# (0x12AE was previously mistaken for CycleCount, 0x12AF for SysTicks.)
R_RUNTIME_C8_H = 0x12AE
R_RUNTIME_C8_L = 0x12AF

# AlarmSta bit meanings — JK RS485 Modbus V1.0 (same word over BLE).
# Confirmed on site 2026-10-07: bit 4 set at SOC 100 %, cells 4.18 V, 0 A,
# charge MOS off (was mislabelled "Charge Overcurrent" before).
ALARM_BITS = {
    0:"Wire Resistance High",      1:"MOS Overtemp",
    2:"Cell Count Mismatch",       3:"Current Sensor Error",
    4:"Cell Overvoltage",          5:"Pack Overvoltage",
    6:"Charge Overcurrent",        7:"Charge Short Circuit",
    8:"Charge Overtemp",           9:"Charge Undertemp",
    10:"Internal Comm Error",      11:"Cell Undervoltage",
    12:"Pack Undervoltage",        13:"Discharge Overcurrent",
    14:"Discharge Short Circuit",  15:"Discharge Overtemp",
    16:"Charge MOS Fault",         17:"Discharge MOS Fault",
    18:"GPS Disconnected",         19:"Change Password Reminder",
    20:"Discharge Start Failed",   21:"Battery Overtemp Alarm",
}

# ── Config fields ─────────────────────────────────────────────────────────────
# (byte_off, key, label, dtype, unit, group)
# read: hi_reg=0x1000+byte_off//2, lo_reg=hi_reg+1
# decode as full UINT32=(hi<<16)|lo (Hi can be >0 for large values!)
# write: FC16 to (0x1000+byte_off), data=[Hi, Lo]

CONFIG_FIELDS = [
    # ── Basic ─────────────────────────────────────────────────────────────────
    (0x006C,"CellCount",      "Cell Count",                "raw","cells","basic"),
    (0x007C,"CapBatCell",     "Battery Capacity",          "ma", "Ah",  "basic"),
    (0x0014,"VolBalanTrig",   "Balance Trigger Volt.",     "mv", "V",   "basic"),
    # ── Voltage ───────────────────────────────────────────────────────────────
    (0x0084,"VolStartBalan",  "Start Balance Volt.",       "mv", "V",   "adv_volt"),
    (0x0048,"CurBalanMax",    "Max Balance Current",       "ma", "A",   "adv_volt"),
    (0x000C,"VolCellOV",      "Cell OVP",                  "mv", "V",   "adv_volt"),
    (0x0010,"VolCellOVPR",    "Cell OVP Recovery",         "mv", "V",   "adv_volt"),
    (0x0018,"VolSOC100",      "SOC 100% Voltage",          "mv", "V",   "adv_volt"),
    (0x0004,"VolCellUV",      "Cell UVP",                  "mv", "V",   "adv_volt"),
    (0x0008,"VolCellUVPR",    "Cell UVP Recovery",         "mv", "V",   "adv_volt"),
    (0x001C,"VolSOC0",        "SOC 0% Voltage",            "mv", "V",   "adv_volt"),
    (0x0020,"VolCellRCV",     "Vol. Cell RCV",             "mv", "V",   "adv_volt"),
    (0x0024,"VolCellRFV",     "Vol. Cell RFV (Full)",      "mv", "V",   "adv_volt"),
    (0x0028,"VolSysPwrOff",   "Power Off Voltage",         "mv", "V",   "adv_volt"),
    (0x0000,"VolSmartSleep",  "Vol. Smart Sleep",          "mv", "V",   "adv_volt"),
    # ── Current ───────────────────────────────────────────────────────────────
    (0x002C,"CurBatCOC",      "Cont. Charge Current",      "ma", "A",   "adv_curr"),
    (0x0030,"TIMBatCOCPDly",  "Charge OCP Delay",          "s",  "s",   "adv_curr"),
    (0x0034,"TIMBatCOCPRDly", "Charge OCPR Time",          "s",  "s",   "adv_curr"),
    (0x0038,"CurBatDcOC",     "Cont. Discharge Current",   "ma", "A",   "adv_curr"),
    (0x003C,"TIMBatDcOCPDly", "Discharge OCP Delay",       "s",  "s",   "adv_curr"),
    (0x0040,"TIMBatDcOCPRDly","Discharge OCPR Time",       "s",  "s",   "adv_curr"),
    (0x0044,"TIMBatSCPRDly",  "Short Circuit OCPR Time",   "s",  "s",   "adv_curr"),
    (0x0080,"SCPDelay",       "Short Circuit Delay",       "raw","μs",  "adv_curr"),
    # ── Temperature ───────────────────────────────────────────────────────────
    (0x004C,"TMPBatCOT",      "Bat Charge OT",             "tc", "°C",  "adv_temp"),
    (0x0050,"TMPBatCOTPR",    "Bat Charge OT Recovery",    "tc", "°C",  "adv_temp"),
    (0x0054,"TMPBatDcOT",     "Bat Discharge OT",          "tc", "°C",  "adv_temp"),
    (0x0058,"TMPBatDcOTPR",   "Bat Discharge OT Recovery", "tc", "°C",  "adv_temp"),
    (0x0064,"TMPMosOT",       "MOS OT",                    "tc", "°C",  "adv_temp"),
    (0x0068,"TMPMosOTPR",     "MOS OT Recovery",           "tc", "°C",  "adv_temp"),
]

CFG_GROUP_NAMES = {
    "basic":    "Basic Settings",
    "adv_volt": "Advance — Voltage",
    "adv_curr": "Advance — Current / OCP",
    "adv_temp": "Advance — Temperature",
}
