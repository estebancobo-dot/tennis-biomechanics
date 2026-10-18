"""The application as one object: what the window (part 2) and the command line call."""
import hashlib
from pathlib import Path

from ..config import CONFIG_DIR, ROOT
from ..pipeline import MissingVideo
from . import index, jobs, videos
from .db import STROKE_ES, Paths, open_db
from .engine import USABLE, Engine

# what the web and its audit are made of: a change here rebuilds every analysis (minutes each)
REPORT_CODE = ("report.py", "report_template.html", "audit.py", "learn.py", "learn_check.py", "explain.py", "findings.py",
               "model.py", "reliability.py", "screens.py", "export.py")


def report_code() -> str:
    h = hashlib.sha1()
    for f in REPORT_CODE:
        p = ROOT / "src" / "tennisbio" / f
        h.update(p.read_bytes() if p.exists() else b"")
    return h.hexdigest()[:16]


class App:
    def __init__(self, cfg: dict, engine_factory=Engine, config_dir: Path = CONFIG_DIR):
        self.cfg, self.config_dir = cfg, config_dir
        self.paths = Paths.from_config(cfg)
        self.db, self.rebuilt = open_db(self.paths, lambda db: index.rebuild(db, self.paths, cfg, config_dir))
        if not self.rebuilt:                                         # what appeared meanwhile (catalogue, folders)
            index.rebuild(self.db, self.paths, cfg, config_dir, fresh=False)
        self.engine = engine_factory(self.db, self.paths)

    def close(self):
        self.db.close()

    # --- adding -------------------------------------------------------------------------------------
    def propose(self, path: Path) -> videos.Proposal:
        return videos.propose(self.db, Path(path))

    def add(self, path: Path, **kw) -> tuple[videos.Proposal, str | None]:
        prop = self.propose(path)
        return prop, videos.confirm(self.db, prop, **kw)

    def analyze_also(self, player: str, stroke: str = "forehand") -> str:
        """«Analizar también…»: another player (her strokes from matches already analysed for the rival:
        only her fine pass, ≈ 3 h each) or another stroke of an analysed player (only a report: minutes)."""
        name = (self.db.one("SELECT name FROM players WHERE id=?", player) or {}).get("name") or player
        main = self.db.q("SELECT id, state FROM matches WHERE player=?", player)
        rival = self.db.q("SELECT id, state FROM matches WHERE opponent_id=? AND player<>?", player, player)
        if not main and not rival:
            return f"{name} no sale en ningún partido de la aplicación: añade un partido suyo."
        need = [r["id"] for r in rival if r["state"] in USABLE
                and not (self.engine.dir(r["id"]) / "strokes_opponent.json").exists()]
        for mid in need:
            jobs.enqueue(self.db, "rival", match=mid, player=player, stroke=stroke, reason=f"analizar también a {name}")
        ready = any(r["state"] in USABLE for r in main) or any(r["state"] in USABLE for r in rival)
        if ready or need:
            jobs.enqueue(self.db, "informe", player=player, stroke=stroke,
                         reason=f"{STROKE_ES.get(stroke, stroke)} de {name}")
        what = f"{STROKE_ES.get(stroke, stroke)} de {name}"
        if need:
            return f"{what}: su pasada fina en {len(need)} partido(s), ≈ {jobs.fmt_duration(3 * 3600 * len(need))}, y su informe."
        if ready:
            return f"{what}: solo su informe, a partir de los golpes ya analizados (minutos)."
        return f"{what}: sus partidos aún se están analizando; el informe sale al terminar."

    # --- new version --------------------------------------------------------------------------------
    def plan_updates(self) -> dict:
        """After an update: which matches have stages whose code or settings changed, the cost, and the
        jobs (waiting for one click when it is long). A changed web rebuilds every analysis (minutes)."""
        plan, total, no_video = [], 0.0, 0
        for r in self.db.q("SELECT id, player FROM matches WHERE state IN (%s)" % ",".join("?" * len(USABLE)), *USABLE):
            try:
                stale = self.engine.stale(r["id"], self.cfg)
            except (MissingVideo, KeyError, OSError):
                no_video += 1                              # no video: its results are kept as they are
                continue
            if not stale:
                continue
            est = self.engine.stale_seconds(r["id"], stale) or jobs.DEFAULT_S["partido"]
            plan.append((r, stale, est))
            total += est
        long_plan = total > jobs.CONFIRM_ABOVE_S
        for r, stale, est in plan:
            jobs.enqueue(self.db, "partido", match=r["id"], player=r["player"], estimate_s=est, confirm=long_plan,
                         reason=f"nueva versión: cambió {', '.join(stale)}")
        code = report_code()
        rebuilt_reports = 0
        if self.db.setting("report_code") != code:
            for a in self.db.q("SELECT player, stroke FROM analyses"):
                jobs.enqueue(self.db, "informe", player=a["player"], stroke=a["stroke"], reason="nueva versión del informe")
                rebuilt_reports += 1
            self.db.set_setting("report_code", code)
        if plan:
            nights = max(1, round(total / (8 * 3600) + .49))
            text = (f"Nueva versión: recalcula {len(plan)} partido(s) ≈ {jobs.fmt_duration(total)}"
                    + (f", {nights} noche(s). Confirma con un clic para empezar." if long_plan else ", desde las cachés."))
            self.db.notice("plan", "aviso" if long_plan else "info", text)
        return {"matches": len(plan), "seconds": total, "confirm": long_plan, "reports": rebuilt_reports, "no_video": no_video}

    def confirm_plan(self) -> int:
        n = len(self.db.q("SELECT id FROM jobs WHERE state='por confirmar'"))
        self.db.x("UPDATE jobs SET state='pendiente' WHERE state='por confirmar'")
        self.db.clear_notice("plan")
        return n

    # --- running ------------------------------------------------------------------------------------
    def work(self, once: bool = True, **kw):
        return jobs.work(self.db, self.paths, self.engine, self.cfg, once=once, **kw)

    # --- reading ------------------------------------------------------------------------------------
    def status(self) -> str:
        db = self.db
        out = []
        run = db.one("SELECT * FROM jobs WHERE state='en curso'")
        e = jobs.eta(db)
        out.append(f"Ahora: {run['kind']} {run.get('match') or ''} {run.get('player') or ''}".rstrip() if run else "Ahora: nada en curso")
        if e["seconds"]:
            out.append(f"En cola: ≈ {jobs.fmt_duration(e['seconds'])}, termina hacia las {e['ends']}")
        np_ = self.db.one("SELECT count(*) AS n FROM players")["n"]
        out.append(f"Jugadoras: {np_} · partidos: {self.db.one('SELECT count(*) AS n FROM matches')['n']}")
        out.append("")
        out.append("Análisis:")
        for a in db.q("SELECT * FROM analyses ORDER BY player, stroke"):
            out.append(f"  {a['player']} · {STROKE_ES.get(a['stroke'], a['stroke'])}: v{a['version']} · {a['state']} · "
                       f"{a['verdict']} · {a['n_strokes']} golpes")
        out.append("Partidos:")
        for m in db.q("SELECT * FROM matches ORDER BY date, id"):
            out.append(f"  {m['id']}: {m['state']}" + (f" — {m['note']}" if m["note"] else ""))
        q = db.q("SELECT * FROM jobs WHERE state IN ('pendiente', 'en curso', 'esperando espacio', 'por confirmar') ORDER BY priority, id")
        out.append(f"Cola ({len(q)}):")
        for j in q:
            out.append(f"  #{j['id']} {j['kind']} {j.get('match') or ''} {j.get('player') or ''} {j.get('stroke') or ''} · "
                       f"{j['state']} · {j['reason']}" + (f" · {j['message']}" if j["message"] else ""))
        n = db.q("SELECT * FROM notices WHERE seen=0 ORDER BY id DESC")
        if n:
            out.append("Avisos:")
            out += [f"  [{x['level']}] {x['text']}" for x in n]
        return "\n".join(out)
