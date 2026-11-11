"""End-to-end check of the single orchestrator on the PC (11-11, task 7 of package B8, docs/orquestador.md, phase F).

As the chat does: submits the flow «prueba_pausa» (tennisbio jobs submit). When its long step runs, pauses the queue
«now» with the application's own button code (window.Api.pause, «Parar ya»): the job must go back to the queue at
that step. Then resumes as the chat does (tennisbio jobs resume): the flow must end «hecho» without repeating its first
step. Writes <output>/capturas_diag/e2e_orquestador.json (uploaded to pc-logs) with every check and the events.

    uv run python scripts/e2e_orquestador.py [--timeout-min 360]"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio import orchestrator as O  # noqa: E402
from tennisbio.config import load_config  # noqa: E402


def wait(db, jid: int, ok, timeout_s: float, poll_s: float = 2.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        row = db.one("SELECT * FROM jobs WHERE id=?", jid)
        if ok(row):
            return row
        time.sleep(poll_s)
    return db.one("SELECT * FROM jobs WHERE id=?", jid)


def run(cfg: dict, timeout_s: float, poll_s: float = 2.0) -> dict:
    from tennisbio import cli
    from tennisbio.app import window
    from tennisbio.app.core import App
    res: dict = {"checks": {}}
    db = O.open_db(cfg)
    try:
        cli.main(["jobs", "submit", "--source", "claude e2e", "--", "flujo", "prueba_pausa"])       # as the chat
        jid = db.q("SELECT id FROM jobs WHERE kind='flujo' ORDER BY id DESC LIMIT 1")[0]["id"]
        res["job"] = jid
        row = wait(db, jid, lambda r: r["state"] == "en curso" and (r["paso"] or 0) == 1, timeout_s, poll_s)
        res["checks"]["llega al paso largo"] = row["state"] == "en curso" and row["paso"] == 1
        if not res["checks"]["llega al paso largo"]:
            res["row"] = row
            return res
        time.sleep(5)
        app = App(cfg)
        try:
            res["app_says"] = window.Api(app).pause(True, True)                                     # «Parar ya» in the app
        finally:
            app.close()
        row = wait(db, jid, lambda r: r["state"] == "pendiente", 120, poll_s)
        res["checks"]["la pausa lo devuelve a la cola en su paso"] = row["state"] == "pendiente" and row["paso"] == 1
        cli.main(["jobs", "resume", "--source", "claude e2e"])                                       # as the chat
        row = wait(db, jid, lambda r: r["state"] in ("hecho", "error", "cancelado"), timeout_s, poll_s)
        res["checks"]["reanudado, acaba hecho"] = row["state"] == "hecho" and row["paso"] == row["pasos"] == 3
        ev = [e for e in O.status(db, events=400)["eventos"] if e["job"] == jid]
        steps = [e["text"] for e in ev if e["kind"] == "paso"]
        res["checks"]["no repite el primer paso"] = sum(t.startswith("1/") for t in steps) == 1
        res["checks"]["repite solo el paso cortado"] = sum(t.startswith("2/") for t in steps) == 2
        res["events"] = list(reversed(ev))
        res["row"] = row
    finally:
        db.close()
    res["ok"] = bool(res["checks"]) and all(res["checks"].values())
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout-min", type=float, default=360)
    args = ap.parse_args()
    cfg = load_config()
    res = run(cfg, args.timeout_min * 60)
    out = Path((cfg.get("paths") or {}).get("output") or "output") / "capturas_diag"
    out.mkdir(parents=True, exist_ok=True)
    (out / "e2e_orquestador.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"ok": res.get("ok"), "checks": res["checks"]}, ensure_ascii=False, indent=1))
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
