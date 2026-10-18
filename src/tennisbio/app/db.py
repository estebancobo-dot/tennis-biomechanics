"""The application's index: one SQLite file (<data>/tennisbio.db) with videos, matches, players, analyses,
the job queue, the history of runs and the notices for the user.

It is only an index. Everything it says can be read again from the folders (each match folder has its
manifest, video.json and partido.json; each analysis its versions and audits), so a lost or damaged file
is set aside (never deleted) and rebuilt (docs/aplicacion_local.md §5.4, «Base de datos dañada»)."""
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  sample TEXT PRIMARY KEY, size INTEGER, path TEXT, duration REAL, fps REAL, interlaced INTEGER,
  added TEXT);
CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY, video TEXT, tournament TEXT, date TEXT, round TEXT, surface TEXT,
  player TEXT, opponent TEXT, opponent_id TEXT, state TEXT DEFAULT 'nuevo', note TEXT DEFAULT '',
  created TEXT, dir TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY, name TEXT, hand TEXT DEFAULT 'right', backhand TEXT DEFAULT 'two_handed',
  height_m REAL, height_known INTEGER DEFAULT 1, aliases TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS analyses (
  id TEXT PRIMARY KEY, player TEXT, stroke TEXT, version INTEGER DEFAULT 0, state TEXT DEFAULT 'nuevo',
  verdict TEXT DEFAULT '', counts TEXT DEFAULT '{}', n_strokes INTEGER DEFAULT 0, updated TEXT);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, match TEXT, player TEXT, stroke TEXT, reason TEXT,
  priority INTEGER DEFAULT 5, state TEXT DEFAULT 'pendiente', attempts INTEGER DEFAULT 0,
  device TEXT DEFAULT '', light INTEGER DEFAULT 0, created TEXT, started TEXT, finished TEXT,
  pid INTEGER, message TEXT DEFAULT '', diag TEXT DEFAULT '', estimate_s REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job INTEGER, kind TEXT, target TEXT, seconds REAL,
  result TEXT, detail TEXT, finished TEXT);
CREATE TABLE IF NOT EXISTS notices (
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, level TEXT, text TEXT, created TEXT,
  seen INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

STROKES = ("forehand", "backhand", "overhead")
STROKE_ES = {"forehand": "derecha", "backhand": "revés", "overhead": "saque"}


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Paths:
    """Where everything lives. The analysis folders stay where the pipeline writes them (<output>/<match>);
    the application adds its own index, the analyses' versions and the diagnostics next to them."""
    output: Path
    videos: Path
    data: Path

    @classmethod
    def from_config(cls, cfg: dict) -> "Paths":
        p = cfg.get("paths", {})
        out = Path(p.get("output", "output"))
        return cls(out, Path(p.get("videos", ".")), Path(p.get("data") or out.parent / "datos"))

    @property
    def db(self) -> Path:
        return self.data / "tennisbio.db"

    @property
    def analyses(self) -> Path:
        return self.output / "analisis"

    @property
    def diag(self) -> Path:
        return self.data / "diagnostico"


class DB:
    """Thin wrapper: rows as dicts, one connection, every write committed at once (an interruption
    never leaves half a change)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # the window answers each click in its own thread: one connection, used under a lock
        self.con = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
        self.lock = threading.RLock()
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        cols = {r[1] for r in self.con.execute("PRAGMA table_info(matches)")}
        if "dir" not in cols:                       # an index from before the match folder was kept
            self.con.execute("ALTER TABLE matches ADD COLUMN dir TEXT DEFAULT ''")
        self.con.commit()

    def close(self):
        self.con.close()

    def q(self, sql: str, *args) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def one(self, sql: str, *args) -> dict | None:
        with self.lock:
            r = self.con.execute(sql, args).fetchone()
            return dict(r) if r else None

    def x(self, sql: str, *args) -> int:
        with self.lock:
            cur = self.con.execute(sql, args)
            self.con.commit()
            return cur.lastrowid

    def upsert(self, table: str, row: dict, key: str = "id"):
        cols = list(row)
        upd = ", ".join(f"{c}=excluded.{c}" for c in cols if c != key)
        self.x(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
               f"ON CONFLICT({key}) DO {'UPDATE SET ' + upd if upd else 'NOTHING'}", *row.values())

    def setting(self, key: str, default=None):
        r = self.one("SELECT value FROM settings WHERE key=?", key)
        return json.loads(r["value"]) if r else default

    def set_setting(self, key: str, value):
        self.upsert("settings", {"key": key, "value": json.dumps(value)}, "key")

    def notice(self, key: str, level: str, text: str):
        """One notice per key (a repeated problem updates its text instead of piling up)."""
        self.x("INSERT INTO notices (key, level, text, created, seen) VALUES (?, ?, ?, ?, 0) "
               "ON CONFLICT(key) DO UPDATE SET level=excluded.level, text=excluded.text, created=excluded.created, seen=0",
               key, level, text, now())

    def clear_notice(self, key: str):
        self.x("DELETE FROM notices WHERE key=?", key)


def healthy(path: Path) -> bool:
    """The file opens, passes SQLite's own check and has the tables."""
    try:
        con = sqlite3.connect(str(path))
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            con.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return ok
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return False


def open_db(paths: Paths, rebuild) -> tuple[DB, bool]:
    """The index, ready. A damaged file is renamed (kept for diagnosis) and the index is rebuilt from the
    folders with `rebuild(db)`; a missing one too. Returns (db, rebuilt)."""
    p = paths.db
    rebuilt = False
    if p.exists() and not healthy(p):
        p.rename(p.with_name(f"tennisbio.danada-{time.strftime('%Y%m%d-%H%M%S')}.db"))
        rebuilt = True
    fresh = not p.exists()
    db = DB(p)
    if fresh:
        rebuild(db)
        if rebuilt:
            db.notice("db_rebuilt", "info", "El índice de la aplicación estaba dañado y se ha reconstruido desde las "
                      "carpetas de cada partido. No se ha perdido nada.")
    return db, rebuilt
