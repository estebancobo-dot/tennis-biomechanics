"""Which programs have a window on the PC's screen (12-11: the user sees an empty PowerShell window that nothing of the
analysis should show). Every process with a visible main window: name, title, its command line and its parent's, so
whatever opens it can be told. Writes <output>/capturas_diag/ventanas_visibles.json. Windows only; reads only."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennisbio.config import load_config  # noqa: E402

PS = ("$all = Get-CimInstance Win32_Process; Get-Process | Where-Object { $_.MainWindowHandle -ne 0 } | ForEach-Object { "
      "$p = $all | Where-Object ProcessId -eq $_.Id; $pp = $all | Where-Object ProcessId -eq $p.ParentProcessId; "
      "[pscustomobject]@{ name = $_.ProcessName; title = $_.MainWindowTitle; pid = $_.Id; cmd = $p.CommandLine; "
      "parent = $pp.Name; parent_cmd = $pp.CommandLine; start = \"$($_.StartTime)\" } } | ConvertTo-Json -Depth 3")


def main() -> None:
    cfg = load_config()
    root = Path((cfg.get("paths") or {}).get("output") or "output")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", PS],
                       capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        rows = json.loads(r.stdout or "[]")
        rep = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "ventanas": rows if isinstance(rows, list) else [rows]}
    except ValueError:
        rep = {"fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "error": (r.stdout or r.stderr or "")[:2000]}
    dst = root / "capturas_diag"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "ventanas_visibles.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
