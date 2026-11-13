@echo off
rem Doble clic, una sola vez (prueba de la nube, 13-11). Guarda en este PC la clave de Modal para subir los datos de la prueba.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\clave_nube.ps1"
pause
