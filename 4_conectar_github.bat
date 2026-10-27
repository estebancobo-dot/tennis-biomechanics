@echo off
rem Doble clic, una sola vez. Conecta el PC con GitHub Actions: las peticiones de Claude empiezan al momento.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\instalar_runner.ps1"
pause
