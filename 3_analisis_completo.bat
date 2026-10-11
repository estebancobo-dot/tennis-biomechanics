@echo off
rem Doble clic para ejecutar. Ver scripts\windows\analisis_completo.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\analisis_completo.ps1"
echo.
pause
