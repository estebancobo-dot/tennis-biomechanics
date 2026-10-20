"""The definitive storage (docs/almacenamiento.md): the library tree, its naming rules, the index that maps
each video's content to its match, and the migration of the current output folders into it.

Self-contained on purpose: the pipeline and the application still write to <output>/<id>/; switching them
over to the library is a later, separate step (docs/almacenamiento.md, «Implementado»).

    <root>/                          e.g. C:\\tenis\\biblioteca
      datos/tennisbio.db             index (derived: rebuilt from the folders when lost or damaged)
      jugadoras/<jugadora>/ficha.yaml
      partidos/<año>/<partido>/      partido.json, etapas/, golpes/<jugadora>/, repeticiones/, tomas/
      analisis/<jugadora>/<golpe>/   actual/, v1..vN/, pendiente/
      exportar/<jugadora>/<golpe>/   movil/, copias/, diagnostico/
      pruebas/                       test runs, never beside the real matches

Every name is lowercase ASCII `[a-z0-9_-]`; a video is known by its content (size + sampled pieces,
`pipeline.video_sample`), never by its name or path. Every file is written atomically (temporary file +
os.replace): an interruption, a full disk or a permission error never leaves a half-written file.
"""
from __future__ import annotations

import datetime as _dt
import errno
import filecmp
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .catalog import ascii_id
from .pipeline import video_sample

STROKES = ("forehand", "backhand", "serve", "volley", "overhead")
STROKE_ALIASES = {"derecha": "forehand", "reves": "backhand", "saque": "serve", "volea": "volley",
                  "remate": "overhead", "smash": "overhead"}
MAX_MATCH_SLUG = 80
MAX_PLAYER_SLUG = 40
MAX_PATH = 240                      # total path length kept below this (Windows MAX_PATH is 260)
DEEPEST_RELATIVE = 200              # partidos/<año>/<partido ≤80>/golpes/<jugadora ≤40>/series/<fichero>
UNKNOWN_DATE = "sin-fecha"
INDEX_NAME = "tennisbio.db"
MATCH_FILE = "partido.json"
JOURNAL_NAME = "migracion.jsonl"
VIDEO_MISSING = "vídeo no disponible"
VIDEO_OK = "disponible"
SLUG_RX = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# letters ascii_id (catalog) does not transliterate: German, Nordic, Serbian/Macedonian Cyrillic, Belarusian
_EXTRA = {"ß": "ss", "æ": "ae", "ø": "o", "đ": "d", "þ": "th", "œ": "oe", "ђ": "dj", "ћ": "c", "џ": "dz",
          "љ": "lj", "њ": "nj", "ј": "j", "ќ": "k", "ѓ": "g", "ў": "u", "ı": "i"}


class LibraryError(RuntimeError):
    """A storage problem; the message is for the user (Spanish) and says what to do."""


# ---------------------------------------------------------------- names

def _ascii(text: str, n: int = 200) -> str:
    """Lowercase ASCII words joined by '-' (Cyrillic transliterated, accents dropped); '' when nothing is left."""
    t = "".join(_EXTRA.get(c, c) for c in str(text or "").lower())
    return ascii_id(t, n, default="")


def _short_hash(text: str, n: int = 6) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def _cut(slug: str, limit: int, tag: str) -> str:
    """Bounded name: a long one is cut and ends with a piece of its fingerprint (two long names that
    share their beginning stay different)."""
    if len(slug) <= limit:
        return slug
    return slug[: limit - len(tag) - 1].rstrip("-_") + "-" + tag


def split_name(name: str) -> tuple[str, str]:
    """(surname, given names). «Apellido, Nombre» when there is a comma; otherwise the last word is the
    surname («Elena Rybakina» → Rybakina, Elena)."""
    name = " ".join(str(name or "").split())
    if "," in name:
        sur, given = name.split(",", 1)
        return sur.strip(), given.strip()
    parts = name.split(" ")
    return (parts[-1], " ".join(parts[:-1])) if parts and parts[0] else ("", "")


def surname_slug(name: str) -> str:
    return _ascii(split_name(name)[0]) or _ascii(name)


def player_slug(name: str) -> str:
    """`apellido-nombre`, lowercase ASCII, transliterated: «Elena Rybakina» → rybakina-elena,
    «Елена Рыбакина» → rybakina-elena, «Iga Świątek» → swiatek-iga. At most 40 characters."""
    sur, given = split_name(name)
    slug = "-".join(p for p in (_ascii(sur), _ascii(given)) if p)
    if not slug:
        raise LibraryError(f"El nombre de la jugadora «{name}» no tiene letras utilizables para su carpeta.")
    return _cut(slug, MAX_PLAYER_SLUG, _short_hash(str(name), 4))


def stroke_slug(stroke: str) -> str:
    s = _ascii(stroke)
    s = STROKE_ALIASES.get(s, s)
    if s not in STROKES:
        raise LibraryError(f"Golpe desconocido «{stroke}»: tiene que ser uno de {', '.join(STROKES)}.")
    return s


def parse_date(date) -> _dt.date | None:
    """A date from the catalogue (date, datetime or text «2023-01-28», «2023/01/28»); None when unknown
    or not a real date (an unknown date is said, never guessed)."""
    if isinstance(date, _dt.datetime):
        return date.date()
    if isinstance(date, _dt.date):
        return date
    t = str(date or "").strip().replace("/", "-").replace(".", "-")
    if not t:
        return None
    try:
        return _dt.date.fromisoformat(t[:10])
    except ValueError:
        return None


def match_year(date) -> str:
    d = parse_date(date)
    return f"{d.year:04d}" if d else UNKNOWN_DATE


def _players_part(players: Iterable[str]) -> str:
    """Players sorted by surname; only their surnames unless two share it (then the full slug)."""
    names = [p for p in players if str(p or "").strip()]
    keyed = sorted(((surname_slug(p), player_slug(p)) for p in names))
    surnames = [s for s, _ in keyed]
    if len(set(surnames)) < len(surnames):
        return "-".join(full for _, full in keyed)
    return "-".join(surnames)


def match_slug(date, tournament: str, round: str, players: Iterable[str], fingerprint: str = "") -> str:
    """`AAAA-MM-DD_torneo_ronda_jugadoraA-jugadoraB`, players in alphabetical order of surname, at most
    80 characters (a long one is cut and ends with 6 characters of the video's fingerprint). Without a
    date: `sin-fecha_<6 of the fingerprint>`."""
    d = parse_date(date)
    fp = _ascii(fingerprint).replace("-", "")
    head = d.isoformat() if d else (f"{UNKNOWN_DATE}_{fp[:6]}" if fp else UNKNOWN_DATE)
    parts = [head, _ascii(tournament), _ascii(round), _players_part(players)]
    slug = "_".join(p for p in parts if p)
    tag = fp[:6] or _short_hash(slug)
    return _cut(slug, MAX_MATCH_SLUG, tag)


def _as_player(player: str) -> str:
    """A player's folder name from her slug or her name."""
    p = str(player or "")
    return p if SLUG_RX.match(p) and len(p) <= MAX_PLAYER_SLUG else player_slug(p)


# ---------------------------------------------------------------- paths

def library_root(cfg: dict) -> Path:
    """`paths.library` of the configuration, or `biblioteca` next to the output folder
    (C:\\tenis\\output → C:\\tenis\\biblioteca)."""
    p = (cfg or {}).get("paths", {}) or {}
    if p.get("library"):
        return Path(p["library"])
    out = p.get("output")
    return (Path(out).parent if out else Path(".")) / "biblioteca"


def root_warning(root: Path) -> str:
    """'' or a notice when the root is so deep that the deepest file of the library would pass 240 characters."""
    n = len(str(Path(root)))
    if n + 1 + DEEPEST_RELATIVE >= MAX_PATH:
        return (f"La carpeta de la biblioteca ({root}) está demasiado anidada: {n} caracteres, y Windows no "
                f"abre rutas de más de {MAX_PATH}. Elige una carpeta más corta, como C:\\tenis\\biblioteca "
                f"(máximo {MAX_PATH - DEEPEST_RELATIVE - 2} caracteres).")
    return ""


def check_length(path: Path) -> Path:
    if len(str(path)) >= MAX_PATH:
        raise LibraryError(f"La ruta {path} tiene {len(str(path))} caracteres y Windows no la abre (máximo "
                           f"{MAX_PATH - 1}). Mueve la biblioteca a una carpeta más corta, como C:\\tenis\\biblioteca.")
    return path


def match_dir(root: Path, slug: str, year: str | None = None) -> Path:
    if not SLUG_RX.match(slug or ""):
        raise LibraryError(f"Nombre de partido no válido: «{slug}».")
    year = year or (slug[:4] if re.match(r"^\d{4}-", slug) else UNKNOWN_DATE)
    return check_length(Path(root) / "partidos" / year / slug)


def analysis_dir(root: Path, player: str, stroke: str) -> Path:
    return check_length(Path(root) / "analisis" / _as_player(player) / stroke_slug(stroke))


def export_dir(root: Path, player: str, stroke: str) -> Path:
    return check_length(Path(root) / "exportar" / _as_player(player) / stroke_slug(stroke))


def player_dir(root: Path, player: str) -> Path:
    return check_length(Path(root) / "jugadoras" / _as_player(player))


def tests_dir(root: Path, name: str = "") -> Path:
    base = Path(root) / "pruebas"
    return check_length(base / run_name(name)) if name else base


def run_name(name: str) -> str:
    """A test run's folder name in pruebas/: `_poc9_largo` → poc9_largo."""
    t = re.sub(r"[^a-z0-9_-]+", "-", _EXTRA.get(name, name).lower()).strip("_-")
    return t or "prueba"


# ---------------------------------------------------------------- atomic writes

def _user_error(e: OSError, path: Path) -> LibraryError:
    if isinstance(e, PermissionError) or e.errno in (errno.EACCES, errno.EPERM, errno.EROFS):
        return LibraryError(f"Sin permiso para escribir en {path}. Cierra los programas que estén usando esa "
                            f"carpeta (o elige otra con permiso de escritura) y vuelve a intentarlo; no se ha "
                            f"guardado nada a medias.")
    if e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", -1)):
        return LibraryError(f"Disco lleno al escribir {path}. Libera espacio y vuelve a lanzarlo: se continúa "
                            f"donde se quedó, sin nada a medias.")
    return LibraryError(f"No se pudo escribir {path}: {e}. No se ha guardado nada a medias.")


def write_bytes_atomic(path: Path, data: bytes):
    """Write through a temporary file in the same folder and os.replace: either the old file or the whole
    new one, never half of it. On error the temporary file is removed and a LibraryError explains it."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise _user_error(e, path) from e


def write_json_atomic(path: Path, obj):
    write_bytes_atomic(path, json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8"))


def read_json(path: Path):
    """The JSON of a file, or None when it is missing or damaged."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _set_aside(path: Path, tag: str = "danado") -> Path:
    """A damaged file is renamed, never deleted (the user may want to look at it)."""
    dst = path.with_name(f"{path.stem}.{tag}-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}")
    i = 2
    while dst.exists():
        dst = path.with_name(f"{path.stem}.{tag}-{time.strftime('%Y%m%d-%H%M%S')}-{i}{path.suffix}")
        i += 1
    os.replace(path, dst)
    return dst


# ---------------------------------------------------------------- the library

@dataclass
class Added:
    slug: str
    dir: Path
    created: bool = False          # a new match
    moved: bool = False            # a known video at a new path (renamed or moved): nothing to recompute
    emission: int = 1
    segment: int = 1
    notes: list[str] = field(default_factory=list)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS lib_matches (slug TEXT PRIMARY KEY, year TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lib_videos (fp TEXT PRIMARY KEY, slug TEXT NOT NULL, emission INTEGER NOT NULL,
    segment INTEGER NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS lib_matches_key ON lib_matches(key);
"""


class Library:
    """The library at `root`: its index maps each video's content fingerprint to its match. The match
    folders (partido.json) are the source of truth; the index is rebuilt from them whenever it is lost
    or damaged."""

    def __init__(self, root: Path, log: Callable[[str], None] | None = None):
        self.root = Path(root)
        self.log = log or (lambda m: None)
        self.warning = root_warning(self.root)
        if self.warning:
            self.log(self.warning)
        self.db_path = self.root / "datos" / INDEX_NAME
        self.notes: list[str] = []
        self._db = self._open()

    # -- index
    def _connect(self) -> sqlite3.Connection:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise _user_error(e, self.db_path.parent) from e
        db = sqlite3.connect(self.db_path, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    def _open(self) -> sqlite3.Connection:
        fresh = not self.db_path.exists()
        db = None
        try:
            db = self._connect()
            db.executescript(_SCHEMA)
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("quick_check")
        except sqlite3.OperationalError as e:          # cannot open or write (permissions, locked), not damaged
            if db is not None:
                db.close()
            if "not a database" not in str(e) and "malformed" not in str(e):
                raise LibraryError(f"No se puede abrir el índice {self.db_path} ({e}). Comprueba que la carpeta "
                                   f"tiene permiso de escritura y que no está abierta en otro programa.") from e
            db = self._reset_index()
            fresh = True
        except sqlite3.DatabaseError:
            if db is not None:
                db.close()
            db = self._reset_index()
            fresh = True
        self._db = db
        if fresh:
            self.rebuild()
        return db

    def _reset_index(self) -> sqlite3.Connection:
        """A damaged index is set aside (never deleted) and a new one is rebuilt from the folders."""
        moved = _set_aside(self.db_path)
        self.notes.append(f"El índice estaba dañado (guardado aparte como {moved.name}); se ha reconstruido "
                          f"desde las carpetas.")
        self.log(self.notes[-1])
        db = self._connect()
        db.executescript(_SCHEMA)
        return db

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def rebuild(self) -> list[str]:
        """Rebuild the index from partidos/<año>/<partido>/partido.json. A damaged partido.json is reported and
        left as it is (its stage files are kept)."""
        warnings = []
        rows_m, rows_v = [], []
        base = self.root / "partidos"
        for f in sorted(base.glob(f"*/*/{MATCH_FILE}")) if base.exists() else []:
            data = read_json(f)
            if not isinstance(data, dict):
                warnings.append(f"{f}: dañado; el partido queda fuera del índice hasta repararlo (repair).")
                continue
            slug = f.parent.name                     # the folder is the truth, not what the file says
            data["partido"] = slug
            rows_m.append((slug, f.parent.parent.name, self._key(data, slug), json.dumps(data, ensure_ascii=False)))
            for e, s, seg in _segments(data):
                if seg.get("huella"):
                    rows_v.append((seg["huella"], slug, e, s, seg.get("ruta", ""), int(seg.get("tamano") or 0)))
        with self._tx() as db:
            db.execute("DELETE FROM lib_videos")
            db.execute("DELETE FROM lib_matches")
            db.executemany("INSERT OR REPLACE INTO lib_matches VALUES (?,?,?,?)", rows_m)
            db.executemany("INSERT OR REPLACE INTO lib_videos VALUES (?,?,?,?,?,?)", rows_v)
        for w in warnings:
            self.log(w)
        return warnings

    class _Tx:
        def __init__(self, db):
            self.db = db

        def __enter__(self):
            self.db.execute("BEGIN IMMEDIATE")
            return self.db

        def __exit__(self, et, ev, tb):
            self.db.execute("ROLLBACK" if et else "COMMIT")

    def _tx(self):
        return Library._Tx(self._db)

    @staticmethod
    def _key(data: dict, slug: str) -> str:
        """What makes two videos the same match: date, tournament, round and players. Without a date the
        key is the match itself (two undated videos are never merged on a guess)."""
        d = parse_date(data.get("fecha"))
        if not d:
            return f"slug:{slug}"
        players = sorted(_as_player(p.get("carpeta") or p.get("nombre", "")) for p in data.get("jugadoras", []))
        return json.dumps([d.isoformat(), _ascii(data.get("torneo", "")), _ascii(data.get("ronda", "")), players])

    # -- queries
    def matches(self) -> list[str]:
        return [r["slug"] for r in self._db.execute("SELECT slug FROM lib_matches ORDER BY slug")]

    def match(self, slug: str) -> dict:
        r = self._db.execute("SELECT data FROM lib_matches WHERE slug=?", (slug,)).fetchone()
        if r is None:
            raise LibraryError(f"No hay ningún partido «{slug}» en la biblioteca.")
        return json.loads(r["data"])

    def dir_of(self, slug: str) -> Path:
        r = self._db.execute("SELECT year FROM lib_matches WHERE slug=?", (slug,)).fetchone()
        return match_dir(self.root, slug, r["year"] if r else None)

    def match_of(self, fingerprint: str) -> str | None:
        r = self._db.execute("SELECT slug FROM lib_videos WHERE fp=?", (fingerprint,)).fetchone()
        return r["slug"] if r else None

    def find_by_video(self, path: Path) -> str | None:
        return self.match_of(video_sample(Path(path)))

    def stages_dir(self, slug: str, emission: int = 1) -> Path:
        """The cheap pass of one broadcast: etapas/ for the first, etapas/emision-2/ for a second one."""
        d = self.dir_of(slug) / "etapas"
        return check_length(d if emission == 1 else d / f"emision-{emission}")

    def strokes_dir(self, slug: str, player: str) -> Path:
        """The fine pass of a player in a match: golpes/<jugadora>/ (the rival's beside it, same cheap pass)."""
        return check_length(self.dir_of(slug) / "golpes" / _as_player(player))

    def analysis_dir(self, player: str, stroke: str) -> Path:
        return analysis_dir(self.root, player, stroke)

    def export_dir(self, player: str, stroke: str) -> Path:
        return export_dir(self.root, player, stroke)

    def tests_dir(self, name: str = "") -> Path:
        return tests_dir(self.root, name)

    def video_status(self, slug: str) -> str:
        """`disponible` when every segment of the first broadcast is where the index says (any complete
        broadcast is enough); `vídeo no disponible` otherwise. The results are kept either way."""
        data = self.match(slug)
        for em in data.get("emisiones", []):
            segs = em.get("segmentos", [])
            if segs and all(s.get("ruta") and Path(s["ruta"]).is_file() for s in segs):
                return VIDEO_OK
        return VIDEO_MISSING

    def video_paths(self, slug: str, emission: int = 1) -> list[Path | None]:
        """The segments of a broadcast in order; None for one that is not available now."""
        data = self.match(slug)
        em = next((e for e in data.get("emisiones", []) if e.get("emision") == emission), None)
        if em is None:
            return []
        return [Path(s["ruta"]) if s.get("ruta") and Path(s["ruta"]).is_file() else None for s in em["segmentos"]]

    # -- writing
    def _save(self, slug: str, year: str, data: dict, created: bool):
        """partido.json first (atomic), the index after it: the folder is always the truth."""
        d = match_dir(self.root, slug, year)
        made = not d.exists()
        try:
            write_json_atomic(d / MATCH_FILE, data)
        except LibraryError:
            if made and created:
                _remove_empty_dirs(d, self.root)
            raise
        with self._tx() as db:
            db.execute("INSERT OR REPLACE INTO lib_matches VALUES (?,?,?,?)",
                       (slug, year, self._key(data, slug), json.dumps(data, ensure_ascii=False)))
            db.execute("DELETE FROM lib_videos WHERE slug=?", (slug,))
            db.executemany("INSERT OR REPLACE INTO lib_videos VALUES (?,?,?,?,?,?)",
                           [(s["huella"], slug, e, i, s.get("ruta", ""), int(s.get("tamano") or 0))
                            for e, i, s in _segments(data) if s.get("huella")])

    def _free_slug(self, base: str) -> str:
        """`base`, or `base-2`, `base-3`… when a match (in the index or on disk) already has it."""
        taken = set(self.matches())
        year = match_year(base[:10]) if re.match(r"^\d{4}-\d\d-\d\d", base) else UNKNOWN_DATE
        cand, i = base, 2
        while cand in taken or (self.root / "partidos" / year / cand).exists():
            suffix = f"-{i}"
            cand = base[: MAX_MATCH_SLUG - len(suffix)].rstrip("-_") + suffix
            i += 1
        return cand

    def add_video(self, path: Path, *, date=None, tournament: str = "", round: str = "",
                  players: Iterable[str] = (), surface: str = "", channel: str = "", segment: int | None = None,
                  match: str | None = None, incomplete: bool = False, note: str = "") -> Added:
        """Register a video. The same content at a new path (renamed, moved, another USB letter) is the same
        match: only its path is updated. `segment` (1, 2…) joins a match split in several files; another
        `channel` with the same date, tournament, round and players is a second broadcast of the same match.
        `match` attaches it explicitly to a known match. Otherwise the same identity is a different match
        (suffix -2). `incomplete`: a summary or an incomplete match, accepted and marked."""
        path = Path(path)
        try:
            size = path.stat().st_size
        except OSError as e:
            raise LibraryError(f"No se encuentra el vídeo {path} (o no se puede leer): {e.strerror or e}.") from e
        if size == 0:
            raise LibraryError(f"El vídeo {path} está vacío (0 bytes); no se añade.")
        fp = video_sample(path)
        known = self.match_of(fp)
        if known:                                          # renamed or moved: same match, new path
            data = self.match(known)
            res = Added(known, self.dir_of(known))
            for e, i, s in _segments(data):
                if s.get("huella") == fp:
                    res.emission, res.segment = e, i
                    if s.get("ruta") != str(path):
                        s["ruta"], res.moved = str(path), True
                        res.notes.append(f"Vídeo movido o renombrado: {path}. Se reutiliza todo lo calculado.")
            if res.moved:
                self._save(known, self.dir_of(known).parent.name, data, created=False)
            return res

        seg = {"huella": fp, "ruta": str(path), "tamano": size}
        names = [str(p) for p in players if str(p or "").strip()]
        new = {"version": 1, "fecha": (parse_date(date).isoformat() if parse_date(date) else ""),
               "torneo": tournament or "", "ronda": round or "", "superficie": surface or "",
               "jugadoras": [{"nombre": n, "carpeta": player_slug(n)} for n in names],
               "incompleto": bool(incomplete), "nota": note or ("Resumen o partido incompleto" if incomplete else ""),
               "emisiones": []}
        if date and not new["fecha"]:
            new["nota"] = (new["nota"] + "; " if new["nota"] else "") + f"fecha no reconocida: «{date}»"

        target = match
        if target is None and parse_date(date):
            key = self._key(new, "")
            r = self._db.execute("SELECT slug FROM lib_matches WHERE key=? ORDER BY slug", (key,)).fetchall()
            for row in r:
                data = self.match(row["slug"])
                chans = {e.get("cadena", "") for e in data.get("emisiones", [])}
                if segment is not None or channel not in chans:
                    target = row["slug"]
                    break
        if target is not None:
            data = self.match(target)
            ems = data.setdefault("emisiones", [])
            em = next((e for e in ems if e.get("cadena", "") == channel), None)
            res = Added(target, self.dir_of(target))
            if em is None:
                em = {"emision": len(ems) + 1, "cadena": channel, "segmentos": []}
                ems.append(em)
                res.notes.append(f"Otra emisión del mismo partido ({channel or 'sin cadena'}): sus repeticiones se suman.")
            idx = segment or len(em["segmentos"]) + 1
            if any(s.get("segmento") == idx for s in em["segmentos"]):
                raise LibraryError(f"El partido {target} ya tiene un segmento {idx} en esa emisión; indica otro número.")
            seg["segmento"] = idx
            em["segmentos"] = sorted(em["segmentos"] + [seg], key=lambda s: s.get("segmento", 0))
            if incomplete:
                data["incompleto"], data["nota"] = True, data.get("nota") or "Resumen o partido incompleto"
            res.emission, res.segment = em["emision"], idx
            self._save(target, self.dir_of(target).parent.name, data, created=False)
            return res

        slug = self._free_slug(match_slug(date, tournament, round, names, fp))
        year = match_year(date)
        seg["segmento"] = segment or 1
        new["partido"] = slug
        new["emisiones"] = [{"emision": 1, "cadena": channel, "segmentos": [seg]}]
        self._save(slug, year, new, created=True)
        res = Added(slug, match_dir(self.root, slug, year), created=True, segment=seg["segmento"])
        if slug != match_slug(date, tournament, round, names, fp):
            res.notes.append(f"Ya había un partido con el mismo nombre: este se guarda como {slug}.")
        return res

    def relocate(self, folders: Iterable[Path]) -> dict[str, str]:
        """Find again the videos that are not where the index says (renamed, moved, a USB with another letter):
        files of the same size whose sampled content matches. Returns {fingerprint: new path}."""
        missing = {r["fp"]: dict(r) for r in self._db.execute("SELECT * FROM lib_videos")
                   if not (r["path"] and Path(r["path"]).is_file())}
        sizes = {v["size"] for v in missing.values()}
        found: dict[str, str] = {}
        for folder in folders:
            folder = Path(folder)
            if not folder.exists() or not missing:
                continue
            for f in folder.rglob("*"):
                try:
                    if not f.is_file() or f.stat().st_size not in sizes:
                        continue
                    fp = video_sample(f)
                except OSError:
                    continue
                if fp in missing and fp not in found:
                    found[fp] = str(f)
        for fp, p in found.items():
            self.add_video(Path(p))                    # known fingerprint → only the path is updated
        return found

    def repair(self, slug: str) -> list[str]:
        """Check a match folder. A damaged partido.json is set aside and rewritten from the index; damaged
        JSON files of its stages are listed (the pipeline recomputes that stage). Returns what it found."""
        out = []
        d = self.dir_of(slug)
        f = d / MATCH_FILE
        if not isinstance(read_json(f), dict):
            data = self.match(slug)
            if f.exists():
                aside = _set_aside(f)
                out.append(f"partido.json dañado (guardado como {aside.name}); rehecho desde el índice.")
            else:
                out.append("Faltaba partido.json; rehecho desde el índice.")
            write_json_atomic(f, data)
        for j in sorted(d.rglob("*.json")):
            if j.name.startswith(".") or ".danado-" in j.name or j == f:
                continue
            if read_json(j) is None:
                out.append(f"Fichero dañado: {j.relative_to(d).as_posix()} (se recalcula esa etapa).")
        return out

    def damaged_files(self, slug: str) -> list[Path]:
        d = self.dir_of(slug)
        return [j for j in sorted(d.rglob("*.json")) if not j.name.startswith(".") and ".danado-" not in j.name
                and read_json(j) is None]

    def save_player(self, name: str, hand: str = "right", backhand: str = "two_handed",
                    height_m: float | None = None, aliases: Iterable[str] = ()) -> str:
        """jugadoras/<jugadora>/ficha.yaml (aliases: as the scoreboard writes her, other alphabets)."""
        import yaml

        slug = player_slug(name)
        card = {"name": name, "hand": hand, "backhand": backhand, "height_m": height_m,
                "aliases": sorted(set(a for a in aliases if a) - {name})}
        write_bytes_atomic(player_dir(self.root, slug) / "ficha.yaml",
                           yaml.safe_dump(card, allow_unicode=True, sort_keys=False).encode("utf-8"))
        return slug


def _segments(data: dict):
    for em in data.get("emisiones", []) or []:
        for i, s in enumerate(em.get("segmentos", []) or [], 1):
            yield int(em.get("emision") or 1), int(s.get("segmento") or i), s


def _remove_empty_dirs(d: Path, stop: Path):
    """Remove the empty folders this call created (never one with anything inside)."""
    d, stop = Path(d), Path(stop)
    while d != stop and stop in d.parents:
        try:
            d.rmdir()
        except OSError:
            return
        d = d.parent


# ---------------------------------------------------------------- migration

# outputs of the cheap pass (one per video): they go to etapas/; the rest of a match folder (fine pass,
# windows, series, caches) goes to golpes/<jugadora>/
CHEAP_FILES = {"probe.json", "scenes.json", "audio_onsets.json", "audio_track.json", "players.npz", "court.json",
               "score.json", "identity.json", "candidates.json", "manifest.json", "video.json", "source.mkv",
               "source.json", "manifest.damaged.json"}
SKIP_TOP = {"datos", "biblioteca"}


@dataclass
class Op:
    kind: str                  # copy_tree | copy_file | write_json
    src: str                   # absolute source ('' for write_json)
    dst: str                   # relative to the library root, with '/'
    data: dict | None = None
    note: str = ""

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.dst}"


def _load_players(config_dir: Path | None = None) -> dict[str, str]:
    import yaml

    from .config import CONFIG_DIR

    out = {}
    for f in sorted((Path(config_dir or CONFIG_DIR) / "players").glob("*.yaml")):
        try:
            out[f.stem] = (yaml.safe_load(f.read_text(encoding="utf-8-sig")) or {}).get("name") or f.stem
        except (OSError, ValueError):
            out[f.stem] = f.stem
    return out


def _load_catalog(config_dir: Path | None = None) -> dict[str, dict]:
    import yaml

    from .config import CONFIG_DIR

    f = Path(config_dir or CONFIG_DIR) / "matches.yaml"
    try:
        return {str(m["id"]): dict(m) for m in (yaml.safe_load(f.read_text(encoding="utf-8-sig")) or {}).get("matches", [])}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _split_analysis(name: str) -> tuple[str, str] | None:
    """`rybakina_forehand` → (rybakina, forehand); None when it does not end in a stroke."""
    if "_" not in name:
        return None
    pid, s = name.rsplit("_", 1)
    try:
        return pid, stroke_slug(s)
    except LibraryError:
        return None


def _split_report(name: str) -> tuple[str | None, str] | None:
    """`informe_derecha` → (None, forehand); `exportar_sabalenka_reves` → (sabalenka, backhand)."""
    parts = name.split("_")[1:]
    if not parts:
        return None
    try:
        s = stroke_slug(parts[-1])
    except LibraryError:
        return None
    return ("_".join(parts[:-1]) or None), s


def plan_migration(output_root: Path, library_root: Path, players: dict[str, str] | None = None,
                   catalog: dict[str, dict] | None = None, main_player: str | None = None) -> list[Op]:
    """What moving the current output folders into the library means, without doing it. Copies only:
    the old folders stay until the copy is verified. Matches go to partidos/<año>/<partido>/ (cheap pass
    to etapas/, the rest to golpes/<jugadora>/, a new partido.json); analyses to analisis/<jugadora>/<golpe>/;
    informe_*/exportar_* beside them; test runs (`_smoke`, `_poc*`, any folder starting with `_`) to pruebas/.
    `players`: player id → name (default: config/players); `catalog`: match id → entry (default:
    config/matches.yaml); `main_player`: whose `informe_derecha` is (default: the most frequent player)."""
    out, lib = Path(output_root), Path(library_root)
    players = _load_players() if players is None else players
    catalog = _load_catalog() if catalog is None else catalog
    ops: list[Op] = []
    if not out.exists():
        return ops
    existing = Library(lib) if (lib / "datos" / INDEX_NAME).exists() or (lib / "partidos").exists() else None
    taken = set(existing.matches()) if existing else set()
    seen_fp: dict[str, str] = {}                      # videos met in this plan
    known: dict[str, tuple[str, str]] = {}             # already in the library: fingerprint / old folder → (slug, year)
    if existing:
        years = {r["slug"]: r["year"] for r in existing._db.execute("SELECT slug, year FROM lib_matches")}
        for r in existing._db.execute("SELECT fp, slug FROM lib_videos"):
            known["fp:" + r["fp"]] = (r["slug"], years.get(r["slug"], UNKNOWN_DATE))
        for slug in years:
            origin = existing.match(slug).get("origen")
            if origin:
                known["dir:" + origin] = (slug, years[slug])
        existing.close()

    def pname(pid: str) -> str:
        return players.get(pid) or pid

    counts: dict[str, int] = {}
    entries = sorted(p for p in out.iterdir() if p.is_dir())
    for d in entries:
        if (d / "manifest.json").exists() and not d.name.startswith("_"):
            info = read_json(d / "partido.json") or {}
            pid = str(info.get("player") or (catalog.get(d.name) or {}).get("player") or "")
            if pid:
                counts[pid] = counts.get(pid, 0) + 1
    main = main_player or (max(sorted(counts), key=counts.get) if counts else None)

    for d in entries:
        name = d.name
        if name in SKIP_TOP:
            continue
        if name.startswith("_"):
            ops.append(Op("copy_tree", str(d), f"pruebas/{run_name(name)}", note="ejecución de prueba"))
            continue
        if name == "analisis":
            for a in sorted(p for p in d.iterdir() if p.is_dir()):
                sp = _split_analysis(a.name)
                if sp is None:
                    ops.append(Op("copy_tree", str(a), f"pruebas/analisis-sin-clasificar/{run_name(a.name)}",
                                  note="análisis sin jugadora/golpe reconocibles"))
                    continue
                pid, stroke = sp
                base = f"analisis/{_as_player(pname(pid))}/{stroke}"
                for e in sorted(a.iterdir()):           # entry by entry: an old report can sit beside them
                    ops.append(Op("copy_tree" if e.is_dir() else "copy_file", str(e), f"{base}/{e.name}"))
            continue
        if name.startswith(("informe_", "exportar_")):
            sp = _split_report(name)
            who = (sp[0] if sp else None) or main
            if sp is None or who is None:
                ops.append(Op("copy_tree", str(d), f"pruebas/{run_name(name)}", note="informe sin jugadora conocida"))
                continue
            kind = "analisis" if name.startswith("informe_") else "exportar"
            sub = "/informe-antiguo" if kind == "analisis" else "/antiguo"
            ops.append(Op("copy_tree", str(d), f"{kind}/{_as_player(pname(who))}/{sp[1]}{sub}"))
            continue
        if not (d / "manifest.json").exists():
            continue                                    # not ours: left where it is
        ops.extend(_plan_match(d, lib, players, catalog, taken, seen_fp, known))
    return ops


def _plan_match(d: Path, lib: Path, players: dict, catalog: dict, taken: set, seen_fp: dict,
                known: dict | None = None) -> list[Op]:
    info = read_json(d / "partido.json") or {}
    cat = catalog.get(d.name) or {}
    vid = read_json(d / "video.json") or {}
    fp = str(vid.get("sample") or "")
    pid = str(info.get("player") or cat.get("player") or "")
    me = players.get(pid) or pid or ""
    rival = str(info.get("opponent") or cat.get("opponent") or "")
    if not rival and cat.get("opponent_id"):
        rival = players.get(cat["opponent_id"], cat["opponent_id"])
    date = info.get("date") or cat.get("date") or ""
    tour = info.get("tournament") or cat.get("tournament") or ""
    rnd = info.get("round") or cat.get("round") or ""
    names = [n for n in (me, rival) if n]

    if fp and fp in seen_fp:                            # the same video analysed twice: kept as a test
        return [Op("copy_tree", str(d), f"pruebas/duplicados/{run_name(d.name)}",
                   note=f"el mismo vídeo que {seen_fp[fp]}")]
    prev = (known or {}).get("fp:" + fp) if fp else None
    prev = prev or (known or {}).get("dir:" + d.name)
    if prev:                                            # migrated before (or the same video): same match, same folder
        slug, year = prev
    else:
        base = match_slug(date, tour, rnd, names, fp or _short_hash(d.name))
        slug, i = base, 2
        while slug in taken:
            slug = base[: MAX_MATCH_SLUG - len(f"-{i}")].rstrip("-_") + f"-{i}"
            i += 1
        year = match_year(date)
    taken.add(slug)
    if fp:
        seen_fp[fp] = slug
    rel = f"partidos/{year}/{slug}"
    check_length(lib / rel)
    who = _as_player(me) if me else "jugadora"
    ops = []
    for e in sorted(d.iterdir()):
        if e.name == "partido.json":
            ops.append(Op("copy_file", str(e), f"{rel}/etapas/partido_origen.json"))
            continue
        dst = f"{rel}/etapas/{e.name}" if e.name in CHEAP_FILES else f"{rel}/golpes/{who}/{e.name}"
        ops.append(Op("copy_tree" if e.is_dir() else "copy_file", str(e), dst))
    seg = {"huella": fp, "ruta": str(vid.get("path") or ""), "tamano": int(vid.get("size") or 0), "segmento": 1}
    data = {"version": 1, "partido": slug, "fecha": parse_date(date).isoformat() if parse_date(date) else "",
            "torneo": tour, "ronda": rnd, "superficie": info.get("surface") or cat.get("surface") or "",
            "jugadoras": [{"nombre": n, "carpeta": player_slug(n)} for n in names],
            "incompleto": False, "nota": "", "origen": d.name,
            "emisiones": [{"emision": 1, "cadena": "", "segmentos": [seg] if fp else []}]}
    ops.append(Op("write_json", "", f"{rel}/{MATCH_FILE}", data=data))
    return ops


def _free_bytes(path: Path) -> float:
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    return float(shutil.disk_usage(p).free)


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def _same_tree(a: Path, b: Path) -> bool:
    if a.is_file() or b.is_file():
        return a.is_file() and b.is_file() and filecmp.cmp(a, b, shallow=False)
    fa = {f.relative_to(a).as_posix(): f.stat().st_size for f in a.rglob("*") if f.is_file()}
    fb = {f.relative_to(b).as_posix(): f.stat().st_size for f in b.rglob("*") if f.is_file()}
    return fa == fb


def read_journal(journal: Path) -> set[str]:
    done = set()
    try:
        lines = Path(journal).read_text(encoding="utf-8").splitlines()
    except OSError:
        return done
    for line in lines:                                  # a line cut by a crash is ignored (that op is redone)
        try:
            done.add(json.loads(line)["op"])
        except (ValueError, KeyError, TypeError):
            continue
    return done


def apply(ops: list[Op], journal: Path, library_root: Path | None = None,
          log: Callable[[str], None] = print) -> dict:
    """Run the plan. Resumable: each finished operation is appended to the journal (JSON lines) and skipped
    when run again; a destination already identical to its source counts as done (no duplicates). Each
    copy goes through a `.partial` folder or a temporary file and is renamed at the end: an interruption
    leaves nothing half-copied under its final name. The old folders are never deleted."""
    journal = Path(journal)
    root = Path(library_root) if library_root else journal.parent.parent
    done = read_journal(journal)
    todo = [o for o in ops if o.id not in done]
    need = sum(_size(Path(o.src)) for o in todo if o.src)
    free = _free_bytes(root)
    if need * 1.05 > free:
        raise LibraryError(f"No hay espacio para copiar a la biblioteca: hacen falta {need / 1e9:.1f} GB y quedan "
                           f"{free / 1e9:.1f} GB libres en el disco. Libera espacio y vuelve a lanzarlo.".replace(".", ",", 2))
    stats = {"hechas": 0, "saltadas": len(ops) - len(todo), "total": len(ops)}
    try:
        journal.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise _user_error(e, journal.parent) from e
    try:                                                # a line cut by a crash must not swallow the next one
        if journal.exists() and journal.stat().st_size and not journal.read_bytes().endswith(b"\n"):
            with open(journal, "a", encoding="utf-8") as f:
                f.write("\n")
    except OSError as e:
        raise _user_error(e, journal) from e
    for o in todo:
        dst = check_length(root / o.dst)
        try:
            _run_op(o, dst)
            with open(journal, "a", encoding="utf-8") as f:
                f.write(json.dumps({"op": o.id, "hora": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            raise _user_error(e, dst) from e
        stats["hechas"] += 1
    log(f"Migración: {stats['hechas']} operaciones hechas, {stats['saltadas']} ya estaban hechas.")
    return stats


def _run_op(o: Op, dst: Path):
    if o.kind == "write_json":
        if not dst.exists():                            # a partido.json already there is kept (never overwritten)
            write_json_atomic(dst, o.data)
        return
    src = Path(o.src)
    if not src.exists():
        raise LibraryError(f"Falta el origen {src}: no se copia (la carpeta antigua debe seguir donde estaba).")
    if dst.exists():
        if _same_tree(src, dst):
            return                                      # copied before the journal line was written
        raise LibraryError(f"{dst} ya existe con otro contenido; no se sobrescribe. Revisa esa carpeta.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if o.kind == "copy_tree":
        tmp = dst.with_name(dst.name + ".partial")
        if tmp.exists():
            shutil.rmtree(tmp)                          # our own copy cut half-way: redone
        try:
            shutil.copytree(src, tmp)
            os.replace(tmp, dst)
        except shutil.Error as e:                       # copytree gathers the errors of each file
            shutil.rmtree(tmp, ignore_errors=True)
            text = str(e)
            code = (errno.ENOSPC if "No space" in text or "Errno 28" in text or "WinError 112" in text else
                    errno.EACCES if "denied" in text or "Errno 13" in text or "WinError 5" in text else errno.EIO)
            raise OSError(code, text[:300]) from e
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)      # nothing half-copied left behind
            raise
    elif o.kind == "copy_file":
        tmp = dst.with_name(f".{dst.name}.tmp")
        try:
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise
    else:
        raise LibraryError(f"Operación desconocida: {o.kind}")


def verify(ops: list[Op], library_root: Path) -> list[str]:
    """What is not yet faithfully copied ([] = the old folders can be removed by the user)."""
    root, bad = Path(library_root), []
    for o in ops:
        dst = root / o.dst
        if not dst.exists():
            bad.append(f"Falta {o.dst}")
        elif o.src and not _same_tree(Path(o.src), dst):
            bad.append(f"Distinto del origen: {o.dst}")
    return bad


def migrate(output_root: Path, library_root: Path, log: Callable[[str], None] = print, **kw) -> dict:
    """Plan, copy (resumable, journal in datos/migracion.jsonl), verify and rebuild the index."""
    lib = Path(library_root)
    ops = plan_migration(output_root, lib, **kw)
    stats = apply(ops, lib / "datos" / JOURNAL_NAME, lib, log)
    stats["problemas"] = verify(ops, lib)
    with Library(lib, log) as L:
        stats["avisos"] = L.rebuild()
    return stats
