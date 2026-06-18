"""
jk_db.py — SQLite logger for JK BMS history data
Keeps 30 days of readings, sampled every 60 seconds.
"""
import sqlite3, time, os, logging

log = logging.getLogger("jk_db")

DB_PATH    = os.environ.get("BMS_DB", os.path.expanduser("~/jk_bms/bms_history.db"))
KEEP_DAYS  = 30
SAMPLE_SEC = 60   # log every 60 seconds

_last_log  = 0.0

def _connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    """Create table and index if not exists."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                ts          INTEGER PRIMARY KEY,
                pack_volt   REAL,
                pack_curr   REAL,
                pack_watt   REAL,
                soc         INTEGER,
                soh         INTEGER,
                rem_cap     REAL,
                full_cap    REAL,
                cycle_cap   REAL,
                cycle_cnt   INTEGER,
                temp_mos    REAL,
                temp_bat1   REAL,
                temp_bat2   REAL,
                cell_max    INTEGER,
                cell_min    INTEGER,
                cell_diff   INTEGER,
                alarm_flags INTEGER,
                ambient_temp REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON readings(ts)")
        # migrate older DBs that lack ambient_temp
        cols = [r[1] for r in conn.execute("PRAGMA table_info(readings)").fetchall()]
        if "ambient_temp" not in cols:
            conn.execute("ALTER TABLE readings ADD COLUMN ambient_temp REAL")
    log.info("DB ready: %s", DB_PATH)

def maybe_log(d: dict, ambient_temp: float = None):
    """Call from poller — logs at most once per SAMPLE_SEC."""
    global _last_log
    now = time.time()
    if not d.get("read_ok") or now - _last_log < SAMPLE_SEC:
        return
    _last_log = now
    try:
        with _connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO readings VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                int(now),
                d.get("pack_volt"),
                d.get("pack_curr"),
                d.get("pack_power"),   # BatWatt from BMS
                d.get("soc"),
                d.get("soh"),
                d.get("rem_cap"),
                d.get("full_cap"),
                d.get("cycle_cap"),
                d.get("cycle_count"),
                d.get("temp_mos"),
                d.get("temp_bat1"),
                d.get("temp_bat2"),
                d.get("cell_max"),
                d.get("cell_min"),
                d.get("cell_diff"),
                d.get("alarm_flags", 0),
                ambient_temp,
            ))
            # purge old data
            cutoff = int(now) - KEEP_DAYS * 86400
            conn.execute("DELETE FROM readings WHERE ts < ?", (cutoff,))
    except Exception as e:
        log.error("DB write: %s", e)

def query_history(hours: int) -> list:
    """Return list of dicts for the last N hours, ordered by ts asc."""
    cutoff = int(time.time()) - hours * 3600
    try:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT ts, pack_volt, pack_curr, pack_watt,
                       temp_mos, temp_bat1, temp_bat2, ambient_temp,
                       soc, cell_diff
                FROM readings
                WHERE ts >= ?
                ORDER BY ts ASC
            """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error("DB query: %s", e)
        return []
