"""The real engine: what a job does on the PC, with the code that already runs there (pipeline stages,
report, audit). Nothing new is analysed here: the application only calls it (docs/aplicacion_local.md,
«la aplicación no vuelve a hacer el análisis»)."""
import json
from pathlib import Path

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
        r = self._row(match_id)
        extra = {"opponent_id": r["opponent_id"]} if r.get("opponent_id") else {}
        return Match(id=r["id"], video=Path(r["vpath"] or ""), player=index.player(self.db, r["player"]),
                     opponent=r.get("opponent") or "", tournament=r.get("tournament") or "", date=r.get("date") or "",
                     surface=r.get("surface") or "", round=r.get("round") or "", extra=extra)

    def dir(self, match_id: str) -> Path:
        return self.paths.output / match_id

    def video_size(self, match_id: str) -> int:
        return int(self._row(match_id).get("vsize") or 0)

    def manifest(self, match_id: str) -> dict:
        return pipeline.load_manifest(self.dir(match_id))

    def _ctx(self, match_id: str, cfg: dict) -> pipeline.Context:
        from ..cli import _logger
        m = self.match(match_id)
        d = self.dir(match_id)
        save_test_info(m, d)                       # the folder says what it is (the index can be rebuilt from it)
        info = json.loads((d / "partido.json").read_text(encoding="utf-8"))
        info.update(player=m.player.id, opponent_id=m.extra.get("opponent_id", ""))
        (d / "partido.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
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
        for m, d in self.matches_of(player):
            f = d / ("strokes.json" if m.player.id == player else "strokes_opponent.json")
            try:
                n += sum(s.get("stroke") == stroke for s in json.loads(f.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                continue
        return n

    def build_report(self, player: str, stroke: str, dest: Path, cfg: dict) -> int:
        from ..report import build
        build([m for m, _ in self.matches_of(player)], self.paths.output, dest, stroke, player_id=player)
        return self.count_strokes(player, stroke)

    def audit(self, player: str, stroke: str, report: Path, dest: Path, cfg: dict):
        from ..cli import run_audit
        run_audit(self.paths.output, report, dest, stroke, dirs=[d for _, d in self.matches_of(player)])

    def stale(self, match_id: str, cfg: dict) -> list[str]:
        """Stages of the match whose code, settings or inputs changed since they ran (a new version)."""
        st = pipeline.status(pipeline.Context(self.match(match_id), cfg, self.dir(match_id)))
        return [n for n, s in st.items() if s == "stale" and n in MAIN_STAGES]

    def stale_seconds(self, match_id: str, names: list[str]) -> float:
        man = self.manifest(match_id)
        return sum((man.get(n) or {}).get("seconds", 0) for n in names)
