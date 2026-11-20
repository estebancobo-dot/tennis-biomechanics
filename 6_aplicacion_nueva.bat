@echo off
rem Doble clic. Abre la aplicacion nueva (P0.5e) en una ventana; su gestion va a la cola de la nube.
where git >nul 2>nul && if exist "%~dp0.git" git -C "%~dp0." pull --ff-only origin claude/tennis-biomech-setup-jggqb0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\aplicacion_nueva.ps1"
echo.
pause
