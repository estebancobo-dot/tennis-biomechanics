"""The window (docs/aplicacion_local.md §3-4, part 2): the 8 screens of the validated mockup, fed with the real
index, in a window of its own. It uses WebView2, the web engine Windows 11 already has (pywebview, free):
no server and no open port, the page talks to the core through `Api` (pywebview's js_api).

The queue runs in a thread of the same program while the window is open; a job cut by closing the window
resumes at the next start (jobs.recover). Without the window engine (pywebview missing or failing) the
screens open read-only in the system browser and every analysis web opens there too (§5.4)."""
import json
import os
import sys
import threading
import time
import webbrowser
from dataclasses import asdict
from pathlib import Path

from . import jobs, quality, state, storage, videos
from .core import App

UI = Path(__file__).with_name("ui.html")
VIDEO_TYPES = ("Vídeos (*.mp4;*.mkv;*.ts;*.mov;*.avi;*.webm)", "Todos los ficheros (*.*)")


def render(st: dict) -> str:
    """The screens with a snapshot of the index inside (read-only until the window's bridge is ready)."""
    return UI.read_text(encoding="utf-8").replace("/*STATE*/", json.dumps(st, ensure_ascii=False).replace("</", "<\\/"))


def write_page(app: App, dest: Path | None = None, with_storage: bool = True) -> Path:
    dest = dest or app.paths.data / "tennisbio.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(state.snapshot(app, with_storage=with_storage)), encoding="utf-8")
    return dest


def open_path(p: str | Path):
    p = Path(p)
    if os.name == "nt":
        os.startfile(str(p))                          # noqa: S606 — the user's own file, with its own program
    else:
        webbrowser.open(p.resolve().as_uri())


class Api:
    """What the page can ask the core. Every method returns plain JSON; an exception reaches the page as a
    rejected promise and is shown as «No se pudo: …» (the window never hangs)."""

    def __init__(self, app: App):
        self.app = app
        self.window = None
        self.lock = threading.RLock()

    # reading
    def state(self, full: bool = False) -> dict:
        with self.lock:
            return state.snapshot(self.app, with_storage=bool(full))

    def storage(self) -> dict:
        with self.lock:
            return state.storage_info(self.app)

    # adding a match
    def choose_video(self) -> str | None:
        import webview
        r = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=VIDEO_TYPES)
        return str(r[0]) if r else None

    def propose(self, path: str) -> dict:
        with self.lock:
            p = self.app.propose(Path(path))
            d = asdict(p)
            d.update(path=str(p.path), name=p.path.name)
            return d

    def confirm(self, path: str, f: dict) -> dict:
        with self.lock:
            prop = self.app.propose(Path(path))
            mid = videos.confirm(self.app.db, prop, f.get("player") or None, f.get("opponent_id") or None,
                                 choose=f.get("choose") or "nuevo",
                                 **{k: f[k] for k in ("tournament", "date", "round", "surface") if f.get(k)})
            e = jobs.eta(self.app.db)
            return {"match_id": mid, "text": (f"Termina hacia las {e['ends']} (≈ {jobs.fmt_duration(e['seconds'])} con lo que hay en la cola). "
                                              "Te aviso al terminar, con su auditoría.") if mid and e["seconds"] else ""}

    def also(self, player: str, stroke: str) -> str:
        with self.lock:
            return self.app.analyze_also(player, stroke)

    # the queue
    def plan(self) -> str:
        with self.lock:
            r = self.app.plan_updates()
        return (f"{r['matches']} partido(s) a recalcular, {r['reports']} informe(s)"
                + (" — espera tu confirmación" if r["confirm"] else ""))

    def confirm_plan(self) -> str:
        with self.lock:
            return f"{self.app.confirm_plan()} trabajos confirmados"

    def pause(self, on: bool) -> str:
        self.app.db.set_setting("pausa", bool(on))
        return "Cola en pausa: el trabajo en curso termina y guarda lo hecho" if on else "Cola reanudada donde se quedó"

    def band(self, band: list | None) -> str:
        self.app.db.set_setting("franja", band or None)
        return f"Trabajos pesados solo de {band[0]} a {band[1]}" if band else "Sin franja: trabaja siempre"

    def retry(self, job_id: int) -> str:
        self.app.db.x("UPDATE jobs SET state='pendiente', attempts=0, message='reintento pedido' WHERE id=? AND state IN ('error', 'aviso')",
                      int(job_id))
        return "Vuelve a la cola"

    def priority(self, job_id: int, delta: int) -> str:
        self.app.db.x("UPDATE jobs SET priority=MAX(0, priority + ?) WHERE id=?", int(delta), int(job_id))
        return "Prioridad cambiada"

    def reanalyze(self, match_id: str) -> str:
        with self.lock:
            m = self.app.db.one("SELECT player FROM matches WHERE id=?", match_id)
            jobs.enqueue(self.app.db, "partido", match=match_id, player=(m or {}).get("player"), reason="reanalizar (pedido)")
        return "Encolado: rehace solo lo que haya cambiado, desde las cachés; nada se borra"

    def archive(self, match_id: str) -> str:
        self.app.db.x("UPDATE matches SET state='archivado', note='Archivado por ti: sale de las listas, no se borra nada.' WHERE id=?",
                      match_id)
        return "Archivado: sale de las listas, no se borra"

    # players
    def set_height(self, player: str, h: float) -> str:
        import yaml
        h = round(float(h), 2)
        with self.lock:
            self.app.db.x("UPDATE players SET height_m=?, height_known=1 WHERE id=?", h, player)
            self.app.db.clear_notice(f"height_{player}")
            f = self.app.config_dir / "players" / f"{player}.yaml"
            d = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
            d["height_m"] = h
            f.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            for a in self.app.db.q("SELECT stroke FROM analyses WHERE player=?", player):
                jobs.enqueue(self.app.db, "informe", player=player, stroke=a["stroke"], reason="altura nueva")
        return "Altura guardada: se recalculan solo los informes"

    # storage and files
    def free(self) -> float:
        with self.lock:
            return storage.free_regenerable(self.app.paths.output)

    def open_path(self, p: str) -> bool:
        open_path(p)
        return True


def worker(cfg: dict, stop: threading.Event, idle_s: float = 30.0):
    """The queue, in the background while the window is open (its own connection to the index)."""
    app = App(cfg)
    try:
        while not stop.is_set():
            ran = jobs.work(app.db, app.paths, app.engine, cfg, once=True, stop=stop.is_set)
            if not ran:
                stop.wait(idle_s)
    finally:
        app.close()


def run(cfg: dict, with_queue: bool = True) -> int:
    app = App(cfg)
    page = write_page(app, with_storage=False)
    try:
        import webview
    except ImportError:
        webview = None
    if webview is None:
        return fallback(app, page, "falta el motor de la ventana (pywebview)")
    stop = threading.Event()
    th = threading.Thread(target=worker, args=(cfg, stop), name="cola", daemon=True) if with_queue else None
    api = Api(app)
    try:
        api.window = webview.create_window("Tennisbio", url=str(page), js_api=api, width=1360, height=900, min_size=(900, 600))
        if th:
            th.start()
        webview.start()
    except Exception as e:                       # noqa: BLE001 — no WebView2 runtime, no display…
        stop.set()
        return fallback(app, page, f"la ventana no arrancó ({type(e).__name__}: {e})")
    finally:
        stop.set()
    app.close()
    return 0


def fallback(app: App, page: Path, why: str) -> int:
    """§5.4 «Navegador o motor de la ventana ausente»: the same screens, read-only, in the system browser;
    the analyses' webs open there as always; the queue keeps working with «tennisbio app work --siempre»."""
    write_page(app, page, with_storage=True)
    print(f"Sin ventana: {why}. Se abre en el navegador, solo para mirar: {page}")
    print("Los trabajos de la cola siguen con: tennisbio app work --siempre")
    webbrowser.open(page.resolve().as_uri())
    app.close()
    return 0


if __name__ == "__main__":
    from ..config import load_config
    sys.exit(run(load_config()))
