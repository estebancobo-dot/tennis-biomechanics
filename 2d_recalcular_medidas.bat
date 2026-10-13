@echo off
rem Doble clic. Vuelve a medir los golpes ya analizados con el codigo nuevo (minutos: sin cortar video ni repetir la pasada barata) y rehace la web, el PDF y la auditoria.
where git >nul 2>nul && if exist "%~dp0.git" git -C "%~dp0." pull --ff-only origin claude/tennis-biomech-setup-jggqb0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\recalcular_medidas.ps1"
echo.
pause
