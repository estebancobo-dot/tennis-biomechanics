@echo off
rem Doble clic. Quita el ciclo automatico (descargar el codigo nuevo, recalcular, revisar y subir los registros cada 10 minutos).
rem Para volver a activarlo: borra C:\tenis\output\ciclo_desactivado.txt y usa cualquier otro boton.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Unregister-ScheduledTask -TaskName 'tenis-ciclo-automatico' -Confirm:$false -ErrorAction SilentlyContinue; New-Item -ItemType File -Force -Path 'C:\tenis\output\ciclo_desactivado.txt' | Out-Null; Write-Host 'Ciclo automatico quitado.'"
pause
