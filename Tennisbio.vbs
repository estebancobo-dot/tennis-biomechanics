' Abre Tennisbio: la ventana de la aplicacion (doble clic). Sin consola; la cola trabaja mientras esta abierta.
' Si algo falla, el registro queda en %TEMP%\tennisbio_ventana.log.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c uv run --extra app tennisbio app ventana > ""%TEMP%\tennisbio_ventana.log"" 2>&1", 0, False
