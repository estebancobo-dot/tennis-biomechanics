"""The phone copy straight to the phone (part 4, asked on 18-10 for the user's Google Pixel 8): when an Android
phone is connected by cable in «Transferencia de archivos», «Copiar al móvil» leaves the folder already
unpacked in its Download folder, opened in Chrome from one fixed bookmark: file:///sdcard/Download/<id>.html
always goes to the newest copy (each copy goes to a folder of its own, <id>_<fecha>, so the script knows it is
complete when all its files are there; the older ones are then taken off the phone).

Android phones are not drives on Windows (MTP): Python cannot write to them, Windows' own Shell can. The copy
runs in Windows' PowerShell (Shell.Application, nothing to install), with no dialog; MTP copies are
asynchronous, so the script waits until every file of the folder is on the phone (or says how many arrived)."""
import base64
import json
import subprocess
import sys
from pathlib import Path

# devices under «Este equipo» that are not drives: phones and cameras (MTP). Their Shell path names the USB device.
_LIST = r"""$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject Shell.Application
$out = @()
foreach ($d in $sh.NameSpace(17).Items()) {
  if ($d.IsFileSystem -or -not $d.IsFolder -or $d.Path -notmatch 'usb#vid_') { continue }
  $st = @($d.GetFolder.Items() | Where-Object { $_.IsFolder } | ForEach-Object { $_.Name })
  $out += [pscustomobject]@{ name = $d.Name; path = $d.Path; storages = $st }
}
ConvertTo-Json -InputObject @($out) -Compress
"""

_SEND = r"""$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject Shell.Application
$dev = $null
foreach ($d in $sh.NameSpace(17).Items()) { if ($d.Path -eq {device}) { $dev = $d } }
if (-not $dev) { Write-Output '{"ok": false, "why": "desconectado"}'; exit }
$st = @($dev.GetFolder.Items() | Where-Object { $_.IsFolder })[0]
if (-not $st) { Write-Output '{"ok": false, "why": "bloqueado"}'; exit }
$dl = $st.GetFolder.ParseName('Download')
if (-not $dl) { Write-Output '{"ok": false, "why": "sin Download"}'; exit }
$dl = $dl.GetFolder
# 4 no progress window, 16 yes to all, 512 no question to make folders, 1024 no error window
$F = 1556
function Count($f) { $n = 0; foreach ($i in $f.Items()) { if ($i.IsFolder) { $n += Count $i.GetFolder } else { $n++ } }; $n }
function Wait($f, $want, $secs) { $t0 = Get-Date; $n = 0
  while (((Get-Date) - $t0).TotalSeconds -lt $secs) { Start-Sleep -Seconds 3; $n = Count $f; if ($n -ge $want) { break } }; $n }
# 1) the copy in a folder of its own: when all its files are there, it is complete
$dl.NewFolder({new})
Start-Sleep -Seconds 2
$nf = $dl.ParseName({new})
if (-not $nf) { Write-Output '{"ok": false, "why": "sin carpeta"}'; exit }
$nf.GetFolder.CopyHere($sh.NameSpace({src}).Items(), $F)
$n = Wait $nf.GetFolder {expected} {timeout}
if ($n -lt {expected}) { Write-Output ('{"ok": false, "why": "tiempo", "files": ' + $n + '}'); exit }
# 2) the fixed page the bookmark opens, now pointing to this copy
$dl.CopyHere({launcher}, $F)
Start-Sleep -Seconds 3
# 3) the older copies leave the phone: moved to the PC (no question on the phone), deleted there
$old = 0
foreach ($i in @($dl.Items())) {
  if ($i.IsFolder -and $i.Name -like {pattern} -and $i.Name -ne {new}) { $sh.NameSpace({trash}).MoveHere($i, $F); $old++ }
}
# moving is asynchronous too: wait until they are gone from the phone (this process must outlive the move)
$t0 = Get-Date
while ($old -and ((Get-Date) - $t0).TotalSeconds -lt {timeout}) {
  Start-Sleep -Seconds 3
  if (-not @($dl.Items() | Where-Object { $_.IsFolder -and $_.Name -like {pattern} -and $_.Name -ne {new} }).Count) { break }
}
Write-Output ('{"ok": true, "files": ' + $n + ', "old": ' + $old + '}')
"""

WHY = {"desconectado": "el teléfono se ha desconectado",
       "bloqueado": "el teléfono está bloqueado o no está en «Transferencia de archivos»: desbloquéalo y elige esa opción en su aviso USB",
       "sin Download": "no se encuentra su carpeta Download",
       "tiempo": "la copia no terminó a tiempo",
       "sin carpeta": "no se pudo crear la carpeta en el teléfono"}


def _q(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _ps(script: str, timeout: float) -> str:
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], capture_output=True,
                       text=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else ""


def send_script(src: Path, device: str, new: str, launcher: Path, trash: Path, expected: int, timeout_s: int,
                stem: str) -> str:
    return (_SEND.replace("{device}", _q(device)).replace("{src}", _q(src)).replace("{new}", _q(new))
            .replace("{launcher}", _q(launcher)).replace("{trash}", _q(trash)).replace("{pattern}", _q(stem + "_2*"))
            .replace("{expected}", str(int(expected))).replace("{timeout}", str(int(timeout_s))))


def launcher(dest: Path, target: str) -> Path:
    """<movil>/<id>.html: the page the phone's bookmark opens; it goes on to the newest copy."""
    f = dest.parent / f"{dest.name}.html"
    f.write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                 f'<title>Tennisbio</title><script>location.replace({json.dumps(target + "/index.html")});</script>'
                 f'<a href="{target}/index.html">Abrir el análisis</a>\n', encoding="utf-8")
    return f


def devices(run=_ps) -> list[dict]:
    """Phones connected by cable: [{"name": "Pixel 8", "path": …, "storages": [...]}]; [] outside Windows.
    A phone locked or not in «Transferencia de archivos» shows no storage."""
    if sys.platform != "win32" and run is _ps:
        return []
    try:
        out = json.loads(run(_LIST, 60) or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    return [{"name": d.get("name") or "Móvil", "path": d.get("path"), "storages": d.get("storages") or []}
            for d in (out if isinstance(out, list) else [out]) if d and d.get("path")]


def send(folder: Path, device: dict, run=_ps, stamp: str | None = None) -> dict:
    """Copies the phone folder into the phone's Download as <id>_<stamp>, points <id>.html to it and takes the
    older copies off the phone; {"ok", "files", "expected", "url" | "why"}. The url is the bookmark's: always
    the same, always the newest copy."""
    import shutil
    import tempfile
    import time
    folder = Path(folder)
    expected = sum(1 for f in folder.rglob("*") if f.is_file())
    if not device.get("storages"):
        return {"ok": False, "expected": expected, "files": 0, "device": device.get("name"), "why": WHY["bloqueado"]}
    new = f"{folder.name}_{stamp or time.strftime('%Y%m%d-%H%M%S')}"
    page = launcher(folder, new)
    trash = Path(tempfile.mkdtemp(prefix="tennisbio_movil_retirado_"))
    timeout_s = 120 + expected // 2 + int(sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 8e6)
    try:
        r = json.loads(run(send_script(folder, device["path"], new, page, trash, expected, timeout_s, folder.name),
                           2 * timeout_s + 120) or "{}")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        r = {"ok": False, "why": f"{type(e).__name__}: {e}"[:200]}
    finally:
        shutil.rmtree(trash, ignore_errors=True)          # the older copies, once off the phone
    r = {"ok": bool(r.get("ok")), "files": r.get("files", 0), "expected": expected, "device": device["name"],
         "folder": new, "old": r.get("old", 0),
         **({"why": WHY.get(r.get("why"), r.get("why") or "sin respuesta")} if not r.get("ok") else {})}
    if r["ok"]:
        r["url"] = f"file:///sdcard/Download/{folder.name}.html"
    return r
