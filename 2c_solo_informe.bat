@echo off
rem Doble clic. Rehace la web, el PDF y la auditoria con lo ya analizado (1-2 min, sin analizar video).
where git >nul 2>nul && if exist "%~dp0.git" git -C "%~dp0." pull --ff-only origin claude/tennis-biomech-setup-jggqb0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\solo_informe.ps1"
echo.
pause
