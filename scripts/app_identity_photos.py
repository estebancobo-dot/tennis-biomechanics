"""The click's photos exactly as the application shows them (09-11: the PC's photos of Rybakina-Pegula were two women,
the app's were Pegula twice: they came from another folder). Calls the window's own Api.identity_photos with the app's
real index for every match (or --match TEXT ...), writes each photo as app_foto_<match>_<k>.jpg and app_fotos.json
(folder used, the folder the index has, the check, the text the screen shows). Nothing is saved as a click.

    uv run python scripts/app_identity_photos.py [OUT_DIR] [--match TEXT ...]
Default OUT_DIR: <output>/capturas_diag (uploaded to pc-logs/capturas_diag)."""
import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.config import load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?")
    ap.add_argument("--match", nargs="+")
    args = ap.parse_args()
    cfg = load_config()
    root = Path(cfg.get("paths", {}).get("output", "output"))
    out = Path(args.out) if args.out else root / "capturas_diag"
    out.mkdir(parents=True, exist_ok=True)
    from tennisbio.app import window
    from tennisbio.app.core import App
    app = App(cfg)
    api = window.Api(app)
    rep = []
    try:
        ids = [r["id"] for r in app.db.q("SELECT id FROM matches")]
        for mid in ids:
            if args.match and not any(s in mid for s in args.match):
                continue
            r = {"match": mid}
            try:
                r["index_dir"] = str(app.engine.dir(mid))
                r["used_dir"] = str(api._ident_dir(mid))
                w = api.identity_photos(mid)
                r.update({k: w.get(k) for k in ("possible", "done", "pick", "check", "by", "error") if k in w})
                r["photos"] = []
                for k, p in enumerate(w.get("photos") or []):
                    src = p.get("src") or ""
                    if "," in src:
                        f = out / f"app_foto_{mid[:40]}_{k}.jpg"
                        f.write_bytes(base64.b64decode(src.split(",", 1)[1]))
                        r["photos"].append({"file": f.name, "t": p.get("t"), "cluster": p.get("cluster")})
            except Exception as e:  # noqa: BLE001 — one match never stops the others
                r["error"] = f"{type(e).__name__}: {e}"[:300]
            print(json.dumps(r, ensure_ascii=False), flush=True)
            rep.append(r)
    finally:
        app.close()
    (out / "app_fotos.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
