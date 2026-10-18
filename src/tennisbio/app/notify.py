"""Windows notifications (docs/aplicacion_local.md §6 «Monitorizar», part 3): «Derecha de Rybakina actualizada:
336 ✔, 0 ✘», a job in error, little disk. They come from the index's notices: each notice is shown once
(again only if its text changes), and the user chooses which kinds in Ajustes.

No extra program: the toast is made by Windows itself (WinRT, through the PowerShell that Windows has),
started without any console window. Outside Windows nothing is shown (the notices stay in Inicio)."""
import base64
import subprocess
import sys
from xml.sax.saxutils import escape

from .db import DB

# which notices each switch of Ajustes covers
KINDS = {"fin": lambda n: n["level"] == "ok", "fallo": lambda n: n["level"] == "crit",
         "disco": lambda n: n["key"] in ("disk_low", "disk_wait")}
DEFAULT = {"fin": True, "fallo": True, "disco": True}
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"   # Windows' own PowerShell

_PS = """[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml(@'
{xml}
'@)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app}').Show([Windows.UI.Notifications.ToastNotification]::new($x))
"""


def toast_xml(title: str, text: str) -> str:
    return ('<toast><visual><binding template="ToastGeneric">'
            f"<text>{escape(title[:120])}</text><text>{escape(text[:300])}</text>"
            "</binding></visual></toast>")


def can_show() -> dict:
    """Whether Windows can make the notification here: the same script, building the toast without showing
    it (for the PC's check: nothing pops up)."""
    if sys.platform != "win32":
        return {"ok": False, "why": "no es Windows"}
    script = _PS.replace("{xml}", toast_xml("prueba", "prueba")).replace("{app}", APP_ID).replace(
        "::CreateToastNotifier('" + APP_ID + "').Show(", "::CreateToastNotifier('" + APP_ID + "') | Out-Null; (")
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], timeout=30,
                           capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"ok": r.returncode == 0, "why": (r.stderr or "").strip()[-200:]}
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "why": str(e)[:200]}


def show(title: str, text: str) -> bool:
    """One Windows notification; False when it cannot be shown (not Windows, PowerShell missing)."""
    if sys.platform != "win32":
        return False
    script = _PS.replace("{xml}", toast_xml(title, text)).replace("{app}", APP_ID)
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    try:
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], timeout=20,
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def settings(db: DB) -> dict:
    return {**DEFAULT, **(db.setting("avisos") or {})}


def send_pending(db: DB, show_fn=None) -> list[str]:
    """Shows the notices not shown yet that the user wants; returns their texts. A notice the user does not
    want is marked as handled too (switching it on later does not flood old ones)."""
    show_fn = show_fn or show
    want = settings(db)
    sent = []
    for n in db.q("SELECT * FROM notices WHERE toasted=0 ORDER BY id"):
        kinds = [k for k, f in KINDS.items() if f(n)]
        if kinds and any(want.get(k) for k in kinds):
            title, _, rest = n["text"].partition(". ")
            if show_fn("Tennisbio · " + title, rest or ""):
                sent.append(n["text"])
        db.x("UPDATE notices SET toasted=1 WHERE id=?", n["id"])
    return sent
