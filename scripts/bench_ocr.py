"""One OCR engine reading the scoreboard of sampled frames, for scripts/bench_candidates.py (candidate `ocr5`).

Run twice on the same plan: with our engine in the project's environment, and with PP-OCRv5 in rapidocr 3.x's
(`uv run --with rapidocr==3.10.0`, which the project does not install: tennisbio.candidates.ocr5). Both read through
tennisbio.scoreboard.ScoreReader exactly as the `score` stage does, except that the OCR of the scoreboard is never
reused between samples (max_reuse 0): every sample is one real OCR.

    python scripts/bench_ocr.py --engine ours|ppocrv5 --plan plan.json --out readings.json [--device cpu]

plan.json: {"matches": [{"id", "video", "names": [player, opponent], "times": [s, ...]}]}. Writes, per match, the
reading of each time (None when nothing was read), the seconds spent reading (decoding not included) and the OCR
calls made.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def engine(name: str, device: str):
    if name == "ours":
        from rapidocr_onnxruntime import RapidOCR             # as tennisbio.scoreboard.ScoreReader builds it

        return RapidOCR()
    from tennisbio.candidates.ocr5 import MODEL_DIR, RapidOcr3

    return RapidOcr3(MODEL_DIR, device)


def read_match(ocr, m: dict) -> dict:
    from tennisbio.io.video import frames_at, probe
    from tennisbio.scoreboard import ScoreReader

    reader = ScoreReader(*m["names"], max_reuse=0, ocr=ocr)
    readings, secs = [], 0.0
    times = sorted(m["times"])
    for _, fr in frames_at(probe(Path(m["video"])), times):
        t0 = time.perf_counter()
        st = reader.read(fr) if fr is not None else None
        secs += time.perf_counter() - t0
        readings.append(st.to_dict() if st is not None else None)
    return {"id": m["id"], "times": times, "readings": readings, "seconds": round(secs, 2), "ocr_calls": reader.ocr_calls}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=("ours", "ppocrv5"), required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cpu", help="the score stage runs on the CPU, next to the iGPU work")
    a = ap.parse_args(argv)
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    ocr = engine(a.engine, a.device)
    out = {"engine": a.engine, "device": a.device, "matches": []}
    for m in plan["matches"]:
        out["matches"].append(read_match(ocr, m))
        print(f"  {a.engine} {m['id']}: {sum(r is not None for r in out['matches'][-1]['readings'])} de "
              f"{len(m['times'])} leídas en {out['matches'][-1]['seconds']} s", flush=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
