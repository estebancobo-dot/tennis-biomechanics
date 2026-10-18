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

from . import backup, jobs, mobile, notify, phone, state, storage, videos
from .core import App
from .db import STROKE_ES

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

    # part 3: notifications and backup
    def notices_settings(self, d: dict) -> dict:
        cur = notify.settings(self.app.db)
        cur.update({k: bool(v) for k, v in (d or {}).items() if k in notify.DEFAULT})
        self.app.db.set_setting("avisos", cur)
        return cur

    def drives(self) -> list:
        return [{**d, "plan": None} for d in backup.removable_drives()]

    def backup_plan(self, root: str, videos: bool = False) -> dict:
        with self.lock:
            p = backup.plan(self.app, Path(root), bool(videos))
        return {k: v for k, v in p.items() if k != "todo"}

    def backup(self, root: str, videos: bool = False) -> str:
        """Starts the copy in the background; its progress and result are in the state («copia»)."""
        if getattr(self, "_bk", None) and self._bk.is_alive():
            return "Ya hay una copia en marcha"
        self.backup_progress = {"done": 0, "total": 0, "bytes": 0, "dest": root}

        def go():
            try:
                with self.lock:
                    res = backup.run(self.app, Path(root), bool(videos),
                                     lambda i, n, b: self.backup_progress.update(done=i, total=n, bytes=b))
                self.app.db.notice("backup", "ok" if not res["errors"] else "aviso",
                                   f"Copia de seguridad hecha en {root}: {res['copied']} ficheros nuevos o cambiados"
                                   f" ({storage._gb(res['bytes'])} GB). " + ("Nada se ha borrado." if not res["errors"]
                                                                             else f"{len(res['errors'])} ficheros no se pudieron copiar."))
            except Exception as e:               # noqa: BLE001 — it does not fit, the drive was pulled out…
                self.app.db.notice("backup", "aviso", f"La copia de seguridad no se hizo: {e}")
            finally:
                self.backup_progress = None
        self._bk = threading.Thread(target=go, name="copia", daemon=True)
        self._bk.start()
        return "Copia en marcha: solo lo nuevo o cambiado; no se borra nada"

    def backup_state(self) -> dict | None:
        return getattr(self, "backup_progress", None)

    # part 4: the copy for the phone
    def mobile(self, aid: str) -> str:
        """Starts the phone copy of one analysis in the background (encoding takes minutes; the index is not
        held meanwhile); its progress is in mobile_state() and its result in the settings («movil»)."""
        if getattr(self, "_mb", None) and self._mb.is_alive():
            return "Ya se está haciendo una copia para el móvil"
        with self.lock:
            a = self.app.db.one("SELECT player, stroke FROM analyses WHERE id=?", aid)
        if not a:
            raise ValueError(f"no hay análisis {aid}")
        self.mobile_progress = {"id": aid, "done": 0, "total": 0}

        def go():
            try:
                res = mobile.make(self.app.paths, a["player"], a["stroke"],
                                  progress=lambda i, n: self.mobile_progress.update(done=i, total=n))
                devs = phone.devices()                   # the phone by cable: straight to it
                sent = None
                if devs:
                    self.mobile_progress.update(phone=devs[0]["name"])
                    sent = phone.send(Path(res["dest"]), devs[0])
                cur = self.app.db.setting("movil") or {}
                cur[aid] = {"when": time.strftime("%Y-%m-%dT%H:%M:%S"), **{k: res[k] for k in
                            ("dest", "bytes", "strokes", "with_video", "encoded", "failed", "missing") if k in res},
                            "zip": res.get("zip"), "phone": sent}
                self.app.db.set_setting("movil", cur)
                bad = len(res["failed"]) + res["missing"]
                where = (f"Ya está en tu {sent['device']}: ábrela en Chrome con {sent['url']} (guárdala en marcadores; "
                         "siempre abre la última copia)" if sent and sent["ok"]
                         else f"No se pudo pasar al {sent['device']}: {sent['why']}. Está en {res.get('zip') or res['dest']}" if sent
                         else f"Está en {res.get('zip') or res['dest']}; conecta el móvil por cable y vuelve a pulsar para pasarla directa")
                self.app.db.notice(f"movil_{aid}", "ok" if not bad and (not sent or sent["ok"]) else "aviso",
                                   f"Copia para el móvil lista: {res['with_video']} golpes con vídeo, {storage._gb(res['bytes'])} GB. "
                                   + where + (f"; {bad} golpes sin vídeo (su clip no está o no se pudo convertir)." if bad else "."))
            except Exception as e:               # noqa: BLE001 — no space, no analysis yet, ffmpeg missing…
                self.app.db.notice(f"movil_{aid}", "aviso", f"La copia para el móvil no se hizo. {e}")
            finally:
                self.mobile_progress = None
        self._mb = threading.Thread(target=go, name="movil", daemon=True)
        self._mb.start()
        return "Copia para el móvil en marcha: convierte los vídeos a 720p; te aviso al terminar"

    def phones(self) -> list:
        return phone.devices()

    def mobile_state(self) -> dict | None:
        return getattr(self, "mobile_progress", None)


def worker(cfg: dict, stop: threading.Event, idle_s: float = 30.0, tray=None):
    """The queue, in the background while the program runs (its own connection to the index): one job at a
    time, the disk guard before each, the Windows notifications after, the tray label kept current."""
    app = App(cfg)
    try:
        while not stop.is_set():
            ran = jobs.work(app.db, app.paths, app.engine, cfg, once=True, max_jobs=1, stop=stop.is_set)
            notify.send_pending(app.db)
            if tray is not None:
                tray.update(tray_text(app))
            if not ran:
                stop.wait(idle_s)
    finally:
        app.close()


def tray_text(app) -> str:
    """The label of the icon next to the clock: what it is doing and when it ends (≤ 127 characters)."""
    db = app.db
    run_ = db.one("SELECT * FROM jobs WHERE state='en curso' ORDER BY id LIMIT 1")
    if db.setting("pausa", False):
        txt = "Tennisbio · cola en pausa"
    elif run_:
        what = (f"informe {STROKE_ES.get(run_['stroke'], run_['stroke'])} de {run_['player']}" if run_["kind"] == "informe"
                else f"{run_['match']}")
        e = jobs.eta(db)
        txt = f"Tennisbio · analizando {what}" + (f" · termina {e['ends']}" if e["ends"] else "")
    else:
        n = len(db.q("SELECT id FROM jobs WHERE state IN ('pendiente', 'esperando espacio', 'por confirmar')"))
        txt = "Tennisbio · " + (f"{n} trabajo(s) esperando" if n else "todo al día")
    crit = db.one("SELECT count(*) AS n FROM notices WHERE level='crit'")["n"]
    return (txt + (f" · {crit} aviso(s)" if crit else ""))[:127]


def tray_image(size: int = 64):
    """The «TB» mark of the window, drawn (no image file to ship)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([2, 2, size - 3, size - 3], radius=size // 5, fill=(212, 240, 58, 255))
    try:
        f = ImageFont.truetype("arialbd.ttf", size // 2 - 4)
    except OSError:
        f = ImageFont.load_default()
    d.text((size / 2, size / 2), "TB", fill=(17, 17, 17, 255), font=f, anchor="mm")
    return im


class Tray:
    """The icon next to the clock (pystray, free): open the window, pause or resume the queue, quit. Closing
    the window only hides it: the queue keeps working; «Salir» stops it (the job in course resumes later)."""

    def __init__(self, app: App, window_ref, stop: threading.Event):
        import pystray
        self.app, self.win, self.stop = app, window_ref, stop
        self.quitting = False
        m = pystray.Menu
        it = pystray.MenuItem
        self.icon = pystray.Icon("tennisbio", tray_image(), "Tennisbio", menu=m(
            it("Abrir Tennisbio", self.open, default=True),
            it(lambda i: "Reanudar la cola" if self.app.db.setting("pausa", False) else "Pausar la cola", self.toggle),
            it("Salir (la cola se para y sigue al volver)", self.quit)))

    def start(self):
        threading.Thread(target=self.icon.run, name="bandeja", daemon=True).start()

    def update(self, text: str):
        try:
            self.icon.title = text
        except Exception:                         # noqa: BLE001 — the icon is cosmetic: never stop the queue
            pass

    def open(self, *_):
        self.win.show()
        self.win.restore()

    def toggle(self, *_):
        self.app.db.set_setting("pausa", not self.app.db.setting("pausa", False))

    def quit(self, *_):
        self.quitting = True
        self.stop.set()
        self.icon.stop()
        self.win.destroy()

    def on_closing(self) -> bool:
        """The window's ✕: hide it and keep working (only once, a notification says where it went)."""
        if self.quitting:
            return True
        self.win.hide()
        if not self.app.db.setting("bandeja_avisada", False):
            notify.show("Tennisbio sigue trabajando", "La cola sigue junto al reloj. Ábrela con el icono TB; «Salir» la para.")
            self.app.db.set_setting("bandeja_avisada", True)
        return False


def already_open(app) -> bool:
    """Only one Tennisbio at a time (two queues would do the same work twice): <data>/ventana.pid holds the
    running one; a second double click only says where it is."""
    f = app.paths.data / "ventana.pid"
    try:
        pid = int(f.read_text().strip())
    except (OSError, ValueError):
        pid = 0
    if pid and pid != os.getpid() and jobs._alive(pid):
        return True
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(str(os.getpid()))
    return False


def run(cfg: dict, with_queue: bool = True) -> int:
    app = App(cfg)
    if already_open(app):
        notify.show("Tennisbio ya está abierto", "Está junto al reloj: pulsa el icono TB para abrir la ventana.")
        print("Tennisbio ya está abierto (icono junto al reloj).")
        app.close()
        return 0
    page = write_page(app, with_storage=False)
    try:
        import webview
    except ImportError:
        webview = None
    if webview is None:
        return fallback(app, page, "falta el motor de la ventana (pywebview)")
    stop = threading.Event()
    api = Api(app)
    try:
        api.window = webview.create_window("Tennisbio", url=str(page), js_api=api, width=1360, height=900, min_size=(900, 600))
        tray = None
        try:
            tray = Tray(app, api.window, stop)
            api.window.events.closing += tray.on_closing
            tray.start()
        except Exception as e:                   # noqa: BLE001 — without the icon, closing the window stops the queue
            print(f"Sin icono junto al reloj: {e}")
        if with_queue:
            threading.Thread(target=worker, args=(cfg, stop), kwargs={"tray": tray}, name="cola", daemon=True).start()
        webview.start()
    except Exception as e:                       # noqa: BLE001 — no WebView2 runtime, no display…
        stop.set()
        return fallback(app, page, f"la ventana no arrancó ({type(e).__name__}: {e})")
    finally:
        stop.set()
        try:
            (app.paths.data / "ventana.pid").unlink()
        except OSError:
            pass
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
