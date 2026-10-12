@echo off
rem Doble clic para ejecutar. Ver scripts\windows\analisis_completo.ps1
rem Primero trae la ultima version del codigo (si el proyecto esta clonado con Git)
where git >nul 2>nul && if exist "%~dp0.git" git -C "%~dp0." pull --ff-only origin claude/tennis-biomech-setup-jggqb0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\analisis_completo.ps1"
echo.
pause
