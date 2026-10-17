' Lanza un script de PowerShell sin ninguna ventana. Con "powershell.exe -WindowStyle Hidden" Windows
' crea antes la consola y la esconde despues: cada 10 minutos se veia un terminal que se cerraba solo.
' Uso: wscript.exe //B oculto.vbs "ruta\script.ps1"   (espera a que el script termine)
If WScript.Arguments.Count < 1 Then WScript.Quit 1
CreateObject("WScript.Shell").Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & WScript.Arguments(0) & """", 0, True
