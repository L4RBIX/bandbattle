"""Tiny SQLite storage layer (sync, guarded by a lock; fine for prototype load)."""
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Almaty")
DB_PATH = os.getenv("DB_PATH", "bandbattle.db")

_lock = threading.Lock()
_dir = os.path.dirname(DB_PATH)
if _dir:
    os.makedirs(_dir, exist_ok=True)
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    city TEXT,
    school TEXT,
    target TEXT,
    xp INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    last_day TEXT,
    best_band REAL DEFAULT 0,
    answers INTEGER DEFAULT 0,
    source TEXT,
    ref_by INTEGER,
    referrals INTEGER DEFAULT 0,
    created INTEGER,
    demo INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ts INTEGER,
    day TEXT,
    qid INTEGER,
    band REAL,
    fc REAL,
    lr REAL,
    gra REAL,
    words INTEGER,
    wpm INTEGER,
    mode TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ts INTEGER,
    kind TEXT,
    payload TEXT
);
"""

with _lock:
    _conn.executescript(SCHEMA)
    _conn.commit()


def today() -> str:
    return datetime.now(TZ).date().isoformat()


def yesterday() -> str:
    return (datetime.now(TZ).date() - timedelta(days=1)).isoformat()


def _q(sql, args=(), one=False, commit=False):
    with _lock:
        cur = _conn.execute(sql, args)
        if commit:
            _conn.commit()
            return cur.lastrowid
        rows = cur.fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def get_user(uid):
    return _q("SELECT * FROM users WHERE id=?", (uid,), one=True)


def create_user(uid, first_name, username, source=None, ref_by=None):
    _q(
        "INSERT OR IGNORE INTO users (id, first_name, username, source, ref_by, created) VALUES (?,?,?,?,?,?)",
        (uid, first_name, username, source, ref_by, int(time.time())),
        commit=True,
    )


def update_user(uid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    _q(f"UPDATE users SET {cols} WHERE id=?", (*fields.values(), uid), commit=True)


def delete_user(uid):
    _q("DELETE FROM users WHERE id=?", (uid,), commit=True)
    _q("DELETE FROM answers WHERE user_id=?", (uid,), commit=True)


def add_referral(inviter_id) -> int:
    _q("UPDATE users SET referrals = referrals + 1, xp = xp + 15 WHERE id=?", (inviter_id,), commit=True)
    row = get_user(inviter_id)
    return row["referrals"] if row else 0


def log_event(uid, kind, payload=""):
    _q("INSERT INTO events (user_id, ts, kind, payload) VALUES (?,?,?,?)",
       (uid, int(time.time()), kind, payload or ""), commit=True)


def ever_started(uid) -> bool:
    return _q("SELECT 1 FROM events WHERE user_id=? AND kind='start' LIMIT 1", (uid,), one=True) is not None


def has_event(uid, kind, payload) -> bool:
    return _q("SELECT 1 FROM events WHERE user_id=? AND kind=? AND payload=? LIMIT 1",
              (uid, kind, payload), one=True) is not None


def answers_today(uid) -> int:
    row = _q("SELECT COUNT(*) c FROM answers WHERE user_id=? AND day=?", (uid, today()), one=True)
    return row["c"]


def record_answer(uid, qid, band, fc, lr, gra, words, wpm, mode):
    """Save an answer, update streak / XP / best band. Returns dict with xp_gain, streak."""
    u = get_user(uid)
    d = today()
    if u["last_day"] == d:
        streak = u["streak"] or 1
    elif u["last_day"] == yesterday():
        streak = (u["streak"] or 0) + 1
    else:
        streak = 1
    first_today = u["last_day"] != d
    xp_gain = 10 + int(round(band * 2)) + (min(streak, 7) * 2 if first_today else 0)
    _q(
        "INSERT INTO answers (user_id, ts, day, qid, band, fc, lr, gra, words, wpm, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (uid, int(time.time()), d, qid, band, fc, lr, gra, words, wpm, mode),
        commit=True,
    )
    update_user(
        uid,
        streak=streak,
        last_day=d,
        xp=(u["xp"] or 0) + xp_gain,
        best_band=max(u["best_band"] or 0, band),
        answers=(u["answers"] or 0) + 1,
    )
    return {"xp_gain": xp_gain, "streak": streak}


def last_answer(uid):
    return _q("SELECT * FROM answers WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,), one=True)


def recent_bands(uid, n=7):
    rows = _q("SELECT band FROM answers WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, n))
    return [r["band"] for r in rows][::-1]


def top_schools(n=5):
    return _q(
        "SELECT school, SUM(xp) xp, COUNT(*) players, MAX(demo) demo FROM users "
        "WHERE school IS NOT NULL GROUP BY school ORDER BY xp DESC LIMIT ?", (n,))


def top_cities(n=5):
    return _q(
        "SELECT city, SUM(xp) xp, COUNT(*) players FROM users "
        "WHERE city IS NOT NULL GROUP BY city ORDER BY xp DESC LIMIT ?", (n,))


def top_players(n=10):
    return _q(
        "SELECT first_name, school, xp, best_band, streak, demo FROM users "
        "WHERE school IS NOT NULL ORDER BY xp DESC LIMIT ?", (n,))


def school_rank(school):
    rows = _q("SELECT school, SUM(xp) xp FROM users WHERE school IS NOT NULL GROUP BY school ORDER BY xp DESC")
    for i, r in enumerate(rows, 1):
        if r["school"] == school:
            return i, len(rows)
    return None, len(rows)


def stats():
    s = {}
    s["users"] = _q("SELECT COUNT(*) c FROM users WHERE demo=0", one=True)["c"]
    s["onboarded"] = _q("SELECT COUNT(*) c FROM users WHERE demo=0 AND school IS NOT NULL", one=True)["c"]
    s["answers"] = _q("SELECT COUNT(*) c FROM answers", one=True)["c"]
    s["active_today"] = _q("SELECT COUNT(DISTINCT user_id) c FROM answers WHERE day=?", (today(),), one=True)["c"]
    s["avg_band"] = _q("SELECT AVG(band) a FROM answers", one=True)["a"]
    s["referrals"] = _q("SELECT COUNT(*) c FROM users WHERE ref_by IS NOT NULL AND demo=0", one=True)["c"]
    s["sources"] = _q(
        "SELECT COALESCE(source,'direct') src, COUNT(*) c FROM users WHERE demo=0 GROUP BY src ORDER BY c DESC LIMIT 10")
    s["book_clicks"] = _q("SELECT COUNT(*) c FROM events WHERE kind='book'", one=True)["c"]
    s["cards"] = _q("SELECT COUNT(*) c FROM events WHERE kind='card'", one=True)["c"]
    s["guess"] = _q("SELECT COUNT(*) c FROM events WHERE kind='guess'", one=True)["c"]
    s["ugc"] = _q("SELECT COUNT(DISTINCT user_id) c FROM events WHERE kind='feature_optin'", one=True)["c"]
    return s


DEMO_PLAYERS = [
    # (id, name, city, school, xp, best, streak) -- clearly flagged demo rows
    (-1, "Aruzhan", "Almaty", "NIS · Almaty", 214, 7.0, 6),
    (-2, "Dias", "Astana", "BIL · Astana", 188, 6.5, 5),
    (-3, "Madina", "Almaty", "RFMSH · Almaty", 171, 6.5, 4),
    (-4, "Alikhan", "Shymkent", "NIS · Shymkent", 149, 6.0, 3),
    (-5, "Tomiris", "Oral", "BIL · Oral", 133, 6.5, 3),
    (-6, "Nursultan", "Almaty", "Lyceum No.165 · Almaty", 120, 6.0, 2),
    (-7, "Aigerim", "Astana", "NIS · Astana", 97, 5.5, 2),
    (-8, "Yerlan", "Atyrau", "KTL · Atyrau", 64, 5.5, 1),
]


def seed_demo():
    if _q("SELECT COUNT(*) c FROM users WHERE demo=1", one=True)["c"]:
        return
    for uid, name, city, school, xp, best, streak in DEMO_PLAYERS:
        _q(
            "INSERT OR IGNORE INTO users (id, first_name, city, school, target, xp, streak, best_band, answers, created, demo, source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,1,'demo')",
            (uid, name, city, school, "7.0", xp, streak, best, streak * 2, int(time.time())),
            commit=True,
        )
