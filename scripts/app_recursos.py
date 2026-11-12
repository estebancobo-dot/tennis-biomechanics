"""What the application costs the PC while it is open (11-11, R8 of the review of the Base, request #225: «la aplicación no
se cuelga ni ralentiza el PC», never measured). Opens the real window without its queue (`tennisbio app ventana
--sin-cola`), waits for it to load, samples for a minute the CPU and memory of its process and all its children (the
WebView2 browser it paints with) and closes it. Writes <output>/capturas_diag/app_recursos.json (uploaded to pc-logs);
the audit judges it («Aplicación: lo que consume abierta»). Windows only (PowerShell); reads nothing of the analyses.

    uv run python scripts/app_recursos.py [--segundos 60]"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.config import load_config  # noqa: E402

# the process and its descendants: total CPU seconds and private memory
PS = ("$ids=@({pid}); $all=Get-CimInstance Win32_Process; $n=0; while($n -ne $ids.Count){{$n=$ids.Count; "
      "$ids=@(@($ids + ($all | Where-Object {{ $ids -contains $_.ParentProcessId }} | ForEach-Object {{ $_.ProcessId }})) "
      "| Sort-Object -Unique)}}; $p=Get-Process -Id $ids -ErrorAction SilentlyContinue; "
      "'{{0}};{{1}};{{2}}' -f ($p | Measure-Object CPU -Sum).Sum, ($p | Measure-Object PrivateMemorySize64 -Sum).Sum, $p.Count")


def sample(pid: int) -> tuple[float, float, int] | None:
    try:
        # 12-11: without a window of its own (a console could stay visible on the PC's screen)
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                            PS.format(pid=pid)], capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        cpu, mem, n = r.stdout.strip().split(";")
        return float(cpu or 0), float(mem or 0) / 1e6, int(n or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def summary(samples: list[tuple[float, float, float, int]], cores: int) -> dict:
    """(time s, cpu s, MB, processes) samples → mean and max CPU % of the whole PC, mean and max MB."""
    cpu = [100.0 * (b[1] - a[1]) / max(1e-6, b[0] - a[0]) / cores for a, b in zip(samples, samples[1:])]
    mem = [s[2] for s in samples]
    return {"muestras": len(samples), "cpu_media_pct": round(sum(cpu) / len(cpu), 2) if cpu else None,
            "cpu_max_pct": round(max(cpu), 2) if cpu else None, "ram_media_mb": round(sum(mem) / len(mem)) if mem else None,
            "ram_max_mb": round(max(mem)) if mem else None, "procesos": max((s[3] for s in samples), default=0)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segundos", type=float, default=60)
    ap.add_argument("--espera", type=float, default=25, help="segundos para que la ventana cargue antes de medir")
    a = ap.parse_args()
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    kw = {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)} if os.name == "nt" else {}
    p = subprocess.Popen([sys.executable, "-m", "tennisbio.cli", "app", "ventana", "--sin-cola"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
    t_start = time.time()
    rows, err = [], ""
    try:
        time.sleep(a.espera)
        if p.poll() is not None:
            err = f"la ventana se cerró sola (código {p.returncode})"
        t0 = time.time()
        while not err and time.time() - t0 < a.segundos:
            s = sample(p.pid)
            if s is not None:
                rows.append((time.time(), *s))
            time.sleep(5)
    finally:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            p.kill()
    rep = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "nucleos": os.cpu_count(), "espera_s": a.espera,
           "error": err, **summary(rows, os.cpu_count() or 1), "segundos": round(time.time() - t_start)}
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "app_recursos.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
