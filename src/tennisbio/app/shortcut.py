"""The desktop shortcut «Tennisbio» (docs/aplicacion_local.md §6 «Lanzar», part 4): one double click opens the
window and the queue starts. Made by the installer and, if it is missing, by the PC's cycle (the user never
installs anything again). It points to Tennisbio.vbs through wscript (no console window) and carries the «TB»
icon of the window, written to <datos>/tennisbio.ico. Windows makes the shortcut itself (WScript.Shell);
the desktop is the one Windows says (it may be inside OneDrive)."""
import base64
import subprocess
import sys
from pathlib import Path

from ..config import ROOT

NAME = "Tennisbio"


def write_icon(dest: Path) -> Path:
    from .window import tray_image
    dest.parent.mkdir(parents=True, exist_ok=True)
    tray_image(256).save(dest, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return dest


def script(link: str | None, icon: Path, repo: Path = ROOT) -> str:
    """The PowerShell that makes (or refreshes) the shortcut; prints where it is."""
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    where = q(link) if link else "(Join-Path ([Environment]::GetFolderPath('Desktop')) " + q(NAME + ".lnk") + ")"
    return "\n".join([
        f"$l = {where}",
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($l)",
        "$s.TargetPath = Join-Path $env:WINDIR 'System32\\wscript.exe'",
        f"$s.Arguments = '\"' + {q(repo / 'Tennisbio.vbs')} + '\"'",
        f"$s.WorkingDirectory = {q(repo)}",
        f"$s.IconLocation = {q(icon)} + ',0'",
        "$s.Description = 'Tennisbio: analiza los partidos y abre sus análisis'",
        "$s.Save()",
        "Write-Output $l"])


def desktop_link() -> Path | None:
    if sys.platform != "win32":
        return None
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                       capture_output=True, text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    d = r.stdout.strip()
    return Path(d) / f"{NAME}.lnk" if d else None


def create(data_dir: Path, only_if_missing: bool = False, link: Path | None = None) -> dict:
    """Makes the shortcut; {"link": path, "made": bool} or {"error": …}. Outside Windows it only says so."""
    if sys.platform != "win32":
        return {"link": None, "made": False, "error": "no es Windows"}
    try:
        link = link or desktop_link()
        if only_if_missing and link and link.exists():
            return {"link": str(link), "made": False}
        icon = write_icon(data_dir / "tennisbio.ico")
        enc = base64.b64encode(script(str(link) if link else None, icon).encode("utf-16-le")).decode()
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], capture_output=True,
                           text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (r.stdout or "").strip().splitlines()
        if r.returncode != 0 or not out:
            return {"link": str(link) if link else None, "made": False, "error": (r.stderr or "sin salida").strip()[-300:]}
        return {"link": out[-1], "made": True}
    except (OSError, subprocess.SubprocessError) as e:
        return {"link": None, "made": False, "error": f"{type(e).__name__}: {e}"[:300]}
