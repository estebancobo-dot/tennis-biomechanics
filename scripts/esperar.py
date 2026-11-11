"""A step that only waits (the end-to-end check of the single orchestrator pauses a flow in the middle of it).

    uv run python scripts/esperar.py SECONDS"""
import sys
import time

if __name__ == "__main__":
    s = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    t0 = time.time()
    while time.time() - t0 < s:
        time.sleep(0.5)
    print(f"esperados {s:g} s")
