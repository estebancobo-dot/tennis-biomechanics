"""The real engine: what a job does on the PC, with the code that already runs there (pipeline stages,
report, audit). Nothing new is analysed here: the application only calls it (docs/aplicacion_local.md,
«la aplicación no vuelve a hacer el análisis»)."""
import json
from pathlib import Path

from .. import match_files as _mf
from .. import pipeline, stages
from ..catalog import Match, save_test_info
from . import index
from .db import DB, Paths

assert stages  # importing the module registers the stages

MAIN_STAGES = tuple(n for n in pipeline.STAGES if n != "fine_opponent")
USABLE = ("analizado", "identidad dudosa", "con aviso")     # matches whose strokes feed an analysis


class Engine:
    def __init__(self, db: DB, paths: Paths):
        self.db, self.paths = db, paths

    def _row(self, match_id: str) -> dict:
        r = self.db.one("SELECT m.*, v.path AS vpath, v.size AS vsize FROM matches m LEFT JOIN videos v ON v.sample = m.video "
                        "WHERE m.id=?", match_id)
        if not r:
            raise KeyError(f"partido desconocido: {match_id}")
        return r

    def match(self, match_id: str) -> Match:
        """The stages' Match, built exactly as the runs build it (catalog.trial_match: what the folder's
        partido.json says, then the index; the rival read by the scoreboard when nobody gave it). A field
        built differently would change the stages' fingerprints and ask for hours of recomputation that
        nothing really needs (seen on the PC, 18-10)."""
        from ..catalog import trial_match
        r = self._row(match_id)
        d = self.dir(match_id)
        opp = r.get("opponent") or ""
        if not opp and (_mf.at(d, "score.json")).exists():
            try:
                opp = json.loads((_mf.at(d, "score.json")).read_text(encoding="utf-8")).get("opponent") or ""
            except (OSError, ValueError):
                opp = ""
        # the id the stages always knew (a library folder is named by its slug; partido.json keeps the old id):
        # a different id could change what the stages infer from it (the surface) and their fingerprints
        name = d.name
        if _mf.is_library(d):
            try:
                name = json.loads((d / "partido.json").read_text(encoding="utf-8")).get("origen") or match_id
            except (OSError, ValueError):
                name = match_id
        m = trial_match(name, Path(r["vpath"] or ""), index.player(self.db, r["player"]), {}, match_dir=d,
                        opponent=opp, tournament=r.get("tournament") or "", date=r.get("date") or "",
                        surface=r.get("surface") or "", round=r.get("round") or "")
        if r.get("opponent_id"):
            m.extra["opponent_id"] = r["opponent_id"]
        return m

    def dir(self, match_id: str) -> Path:
        """The match folder: where the index says (test runs live one level down; a library folder is an
        absolute path), else, a new match: its library folder once the library is switched on
        (tennisbio.layout), or <output>/<id>."""
        r = self.db.one("SELECT dir FROM matches WHERE id=?", match_id)
        if r and r.get("dir"):
            return self.paths.output / r["dir"]
        lib = self._library_dir(match_id)
        if lib is not None:
            self.db.x("UPDATE matches SET dir=? WHERE id=?", lib.as_posix(), match_id)
            return lib
        return self.paths.output / match_id

    def _library_dir(self, match_id: str) -> Path | None:
        from ..layout import library_active
        from ..library import Library, LibraryError, player_slug
        root = library_active()
        if root is None:
            return None
        r = self._row(match_id)
        if not r.get("vpath"):
            return None
        who = index.player(self.db, r["player"])
        try:
            with Library(root) as lib:
                added = lib.add_video(Path(r["vpath"]), date=r.get("date") or None, tournament=r.get("tournament") or "",
                                      round=r.get("round") or "", surface=r.get("surface") or "",
                                      players=[getattr(who, "name", r["player"]), r.get("opponent") or ""])
                d = added.dir
        except LibraryError:
            return None
        (d / "etapas").mkdir(parents=True, exist_ok=True)
        p = d / "partido.json"
        info = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if not info.get("jugadora"):
            info["jugadora"] = player_slug(getattr(who, "name", "") or r["player"])
            info.setdefault("origen", match_id)
            p.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        return d

    def video_size(self, match_id: str) -> int:
        return int(self._row(match_id).get("vsize") or 0)

    def manifest(self, match_id: str) -> dict:
        return pipeline.load_manifest(self.dir(match_id))

    def _ctx(self, match_id: str, cfg: dict) -> pipeline.Context:
        from ..cli import _logger
        m = self.match(match_id)
        d = self.dir(match_id)
        save_test_info(m, d)                       # the folder says what it is (the index can be rebuilt from it)
        f = _mf.test_info(d)
        info = json.loads(f.read_text(encoding="utf-8"))
        info.update(player=m.player.id, opponent_id=m.extra.get("opponent_id", ""))
        f.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        return pipeline.Context(m, cfg, d, log=_logger(d))

    def run_match(self, match_id: str, player: str, cfg: dict):
        pipeline.run(self._ctx(match_id, cfg), list(MAIN_STAGES))

    def run_opponent(self, match_id: str, player: str, cfg: dict):
        c = {**cfg, "analyze_opponent": True}
        pipeline.run(self._ctx(match_id, c), ["fine_opponent"])

    def matches_of(self, player: str) -> list[tuple[Match, Path]]:
        out = []
        for r in self.db.q("SELECT id FROM matches WHERE (player=? OR opponent_id=?) AND state IN (%s) ORDER BY date, id"
                           % ",".join("?" * len(USABLE)), player, player, *USABLE):
            try:
                out.append((self.match(r["id"]), self.dir(r["id"])))
            except KeyError:
                continue
        return out

    def count_strokes(self, player: str, stroke: str) -> int:
        n = 0
        for m, d in self._group(player)[1]:
            f = _mf.at(d, "strokes.json" if m.player.id == player else "strokes_opponent.json")
            try:
                n += sum(s.get("stroke") == stroke for s in json.loads(f.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                continue
        return n

    def _group(self, player: str) -> tuple[Path, list[tuple[Match, Path]]]:
        """The report reads <root>/<match id>: its matches must share one root. Matches added by the
        application all live in <output>; test runs live one level down, each run its own root: the
        root with most of her matches is used."""
        by: dict[Path, list] = {}
        for m, d in self.matches_of(player):
            by.setdefault(d.parent, []).append((m, d))
        if not by:
            return self.paths.output, []
        root = max(by, key=lambda r: (len(by[r]), r == self.paths.output))
        return root, by[root]

    def build_report(self, player: str, stroke: str, dest: Path, cfg: dict) -> int:
        from ..report import build
        root, mine = self._group(player)
        build([m for m, _ in mine], root, dest, stroke, player_id=player)
        return self.count_strokes(player, stroke)

    def audit(self, player: str, stroke: str, report: Path, dest: Path, cfg: dict):
        from ..cli import run_audit
        root, mine = self._group(player)
        run_audit(root, report, dest, stroke, dirs=[d for _, d in mine])

    def stale(self, match_id: str, cfg: dict) -> list[str]:
        """Stages of the match whose code, settings or inputs changed since they ran (a new version)."""
        st = pipeline.status(pipeline.Context(self.match(match_id), cfg, self.dir(match_id)))
        return [n for n, s in st.items() if s == "stale" and n in MAIN_STAGES]

    def stale_seconds(self, match_id: str, names: list[str]) -> float:
        man = self.manifest(match_id)
        return sum((man.get(n) or {}).get("seconds", 0) for n in names)
