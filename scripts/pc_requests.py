"""The requests Claude queues for the PC in config/peticion_pc.txt, read as the PowerShell cycle reads them
(scripts/windows/ciclo_automatico.ps1: Leer-Peticiones, Peticiones-Hechas, Peticion-Pendiente).

The file holds one or more blocks separated by a line ``---``; each block has ``key: value`` lines (``id``,
``accion`` and the action's parameters). Lines that are not ``key: value`` (``#`` comments, blank lines) are
ignored. Keys are case-insensitive (a PowerShell hashtable), so they are lower-cased here; the last value of a
key in a block wins. A file without ``---`` is a single block, as before the queue.

Done ids: ``output/peticiones_hechas.txt`` (one per line) plus the old ``output/peticion_hecha.txt`` (one id).

    python scripts/pc_requests.py [config/peticion_pc.txt] [done file ...]   → prints the blocks and which is next
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "config" / "peticion_pc.txt"
SEPARATOR = re.compile(r"^\s*---\s*$")
KEY_VALUE = re.compile(r"^\s*(\w+)\s*:\s*(.+?)\s*$")


def parse(text: str) -> list[dict]:
    """Blocks of the request file, in order; blocks with no ``key: value`` line are dropped."""
    blocks, cur = [], {}
    for line in text.splitlines():
        if SEPARATOR.match(line):
            if cur:
                blocks.append(cur)
            cur = {}
            continue
        m = KEY_VALUE.match(line)
        if m:
            cur[m.group(1).lower()] = m.group(2)
    if cur:
        blocks.append(cur)
    return blocks


def read_done(*files: Path) -> set[str]:
    """Done ids from the done-list files that exist (one id per line)."""
    done = set()
    for f in files:
        f = Path(f)
        if f.exists():
            done |= {ln.strip() for ln in f.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()}
    return done


def runnable(block: dict) -> bool:
    """A block the cycle can run: it has an id and an action, and the action is not «ninguna»."""
    return bool(block.get("id")) and bool(block.get("accion")) and block["accion"].lower() != "ninguna"


def pending(blocks: list[dict], done_ids) -> list[dict]:
    """Runnable blocks whose id is not done, in queue order (the first one is the next the PC runs)."""
    done = {str(d).strip() for d in done_ids}
    return [b for b in blocks if runnable(b) and b["id"].strip() not in done]


def load(path: Path = REQUESTS) -> list[dict]:
    path = Path(path)
    return parse(path.read_text(encoding="utf-8", errors="replace")) if path.exists() else []


def param(key: str, accion: str, path: Path = REQUESTS) -> str | None:
    """A parameter of a request, for a script whose (possibly older) cycle script did not pass it on the
    command line: taken from the first block with that action (the cycle marks a block done before running
    it, so the done list cannot say which block is running; with one block per action it is that one)."""
    for b in load(path):
        if b.get("accion", "").lower() == accion.lower():
            return b.get(key.lower())
    return None


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else REQUESTS
    blocks = load(path)
    done = read_done(*[Path(a) for a in argv[1:]])
    nxt = pending(blocks, done)
    for b in blocks:
        state = "hecha" if b.get("id", "").strip() in done else ("pendiente" if b in nxt else "no se ejecuta")
        print(f"id {b.get('id', '?')}: {b.get('accion', '?')} ({state}) "
              + ", ".join(f"{k}={v}" for k, v in b.items() if k not in ("id", "accion")))
    print(f"siguiente: {nxt[0]['id'] if nxt else 'ninguna'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
