"""Use of the PC by stage (26-10): min / mean / max of CPU, RAM, iGPU and disk from the samples of
scripts/windows/medir_recursos.ps1 (one row every 15 s), and what limits each stage.

    uv run python scripts/resources_summary.py <csv>... [--out recursos.md]
"""
import argparse
import csv
from pathlib import Path

COLS = ["cpu_total", "cpu_python", "cpu_ffmpeg", "ram_usada_gb", "gpu_3d", "gpu_compute", "gpu_decode", "disco"]
NAMES = {"cpu_total": "CPU total %", "cpu_python": "CPU Python %", "cpu_ffmpeg": "CPU ffmpeg %", "ram_usada_gb": "RAM usada GB",
         "gpu_3d": "iGPU 3D %", "gpu_compute": "iGPU cálculo %", "gpu_decode": "iGPU vídeo %", "disco": "Disco %"}


def read(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, encoding="ascii", errors="replace", newline="") as f:
            for r in csv.DictReader(f):
                for c in COLS + ["ram_total_gb"]:
                    try:
                        r[c] = float(r.get(c) or "nan")
                    except ValueError:
                        r[c] = float("nan")
                rows.append(r)
    return rows


def limit(s: dict, ram_total: float) -> str:
    """What holds a stage back, from its means and peaks."""
    gpu = max(s["gpu_3d"][1], s["gpu_compute"][1])
    if gpu >= 80:
        return "iGPU al límite"
    if s["cpu_total"][1] >= 85:
        return "CPU al límite"
    if s["disco"][1] >= 80:
        return "disco al límite"
    if ram_total == ram_total and s["ram_usada_gb"][2] >= 0.95 * ram_total:
        return "RAM al límite"
    if s["cpu_total"][1] < 35 and gpu < 35:
        return "equipo infrautilizado: trabajo en serie (se puede repartir)"
    return "uso medio: margen para repartir trabajo"


def summarize(rows: list[dict], every_s: float = 15.0) -> list[dict]:
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r.get("partido", ""), r.get("etapa", "")), []).append(r)
    ram_total = max((r["ram_total_gb"] for r in rows if r["ram_total_gb"] == r["ram_total_gb"]), default=float("nan"))
    out = []
    for (m, st), rs in groups.items():
        s = {}
        for c in COLS:
            v = [r[c] for r in rs if r[c] == r[c]]
            s[c] = (min(v), sum(v) / len(v), max(v)) if v else (float("nan"),) * 3
        out.append({"partido": m, "etapa": st, "minutos": round(len(rs) * every_s / 60, 1), "stats": s, "limite": limit(s, ram_total)})
    return out


def markdown(summary: list[dict]) -> str:
    lines = ["# Uso del PC por etapa (mín / media / máx)", "",
             "| Partido | Etapa | min | " + " | ".join(NAMES[c] for c in COLS) + " | Qué la limita |",
             "|---|---|---|" + "---|" * len(COLS) + "---|"]
    for g in summary:
        cells = [" / ".join(f"{x:.0f}" if c != "ram_usada_gb" else f"{x:.1f}" for x in g["stats"][c]) for c in COLS]
        lines.append(f"| {g['partido']} | {g['etapa']} | {g['minutos']} | " + " | ".join(cells) + f" | {g['limite']} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    md = markdown(summarize(read(a.csv)))
    if a.out:
        a.out.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
