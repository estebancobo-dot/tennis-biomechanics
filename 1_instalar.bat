@echo off
rem Doble clic: descarga la ultima version del proyecto (sin Git) e instala todo lo que falte.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\bootstrap.ps1"
echo.
pause
