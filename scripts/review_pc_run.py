"""What changed in the last run on the PC, read from the pc-logs branch (no tokens, no PC access):
the audit totals, the checks that got worse or better since the previous run, what still fails,
the practice videos, sizes on disk and the time of each step.

    python scripts/review_pc_run.py [--log prueba_rapida.log] [--audit auditoria_prueba.json]
"""
import argparse
import json
import re
import subprocess
import sys

RANK = {"falta": 0, "aviso": 1, "pocos datos": 2, "ok": 3}


def git(*a) -> str:
    r = subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def at(rev: str, path: str):
    txt = git("show", f"{rev}:{path}")
    return txt or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="prueba_rapida.log")
    ap.add_argument("--audit", default="auditoria_prueba.json")
    args = ap.parse_args()
    git("fetch", "-q", "origin", "pc-logs")
    revs = git("log", "origin/pc-logs", "--format=%H %cd", "--date=iso", "--", args.audit).splitlines()
    if not revs:
        print("No hay auditorías en pc-logs.")
        return 1
    new_rev, new_date = revs[0].split(" ", 1)
    old_rev = next((r.split(" ", 1)[0] for r in revs[1:] if at(r.split(" ", 1)[0], args.audit) != at(new_rev, args.audit)), None)
    new = json.loads(at(new_rev, args.audit))
    old = json.loads(at(old_rev, args.audit)) if old_rev else {"items": []}
    s = new.get("summary", {})
    print(f"Ejecución subida {new_date}: ✔ {s.get('ok')} · ✘ {s.get('falta')} · … {s.get('pocos datos')} · ! {s.get('aviso')}"
          f" ({new.get('near')} golpes del lado cercano)")
    key = lambda i: (i.get("area"), i["name"])
    before = {key(i): i for i in old.get("items", [])}
    worse, better, fresh = [], [], []
    for i in new["items"]:
        b = before.get(key(i))
        if b is None:
            fresh.append(i)
        elif RANK[i["status"]] < RANK[b["status"]]:
            worse.append((b, i))
        elif RANK[i["status"]] > RANK[b["status"]]:
            better.append((b, i))
    print(f"\nPeor que la vez anterior ({len(worse)}):")
    for b, i in worse:
        print(f"  {b['status']} → {i['status']}: {i['name']} — {i['detail'][:160]}")
    print(f"\nMejor que la vez anterior ({len(better)}):")
    for b, i in better[:30]:
        print(f"  {b['status']} → {i['status']}: {i['name']}")
    print(f"\nComprobaciones nuevas ({len(fresh)}):")
    for i in fresh[:40]:
        print(f"  {i['status']}: {i['name']} — {i['detail'][:140]}")
    print("\nNo cumplido ahora:")
    for i in new["items"]:
        if i["status"] == "falta":
            print(f"  {i['name']} — {i['detail'][:160]}")
    log = at("origin/pc-logs", args.log) or ""
    print("\nPasos y tiempos:")
    for line in log.splitlines():
        if re.match(r"==> \[", line) or re.search(r"Duraci|Tiempo total|derechas|ERROR|Traceback|Auditoría:", line):
            print("  " + line.strip()[:170])
    pr = at("origin/pc-logs", "entrenamiento/entrenamiento.json")
    if pr:
        d = json.loads(pr)
        st = d.get("strokes", [])
        fh = [x for x in st if x.get("stroke") == "forehand"]
        print(f"\nVista lateral: {len(d.get('videos', []))} vídeos, {len(st)} golpes ({len(fh)} derechas); cámara {d.get('views')}; "
              f"descartados {sum(1 for x in st if x.get('discarded'))}, 3D descartado {sum(1 for x in st if x.get('discarded_3d'))}")
        for k, e in (d.get("summary") or {}).items():
            print(f"  {e['label']}: n={e['n']}" + (f", mediana {e['median']}" if e.get("median") is not None else ""))
    sizes = at("origin/pc-logs", "tamanos.txt")
    if sizes:
        print("\nTamaños:\n" + "\n".join("  " + x for x in sizes.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
