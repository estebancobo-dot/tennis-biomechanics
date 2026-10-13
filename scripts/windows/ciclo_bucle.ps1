# Bucle del ciclo automatico: arranca solo al iniciar sesion (carpeta Inicio de Windows) y se queda en
# segundo plano. Cada 10 minutos lanza ciclo_automatico.ps1 desde el disco, asi que cada version nueva
# del ciclo que llegue con el codigo se usa sola, sin volver a instalar nada. Una sola copia a la vez.
$m = New-Object System.Threading.Mutex($false, "Global\tenis-ciclo-bucle")
if (-not $m.WaitOne(0)) { exit 0 }
$ps1 = Join-Path $PSScriptRoot "ciclo_automatico.ps1"
while ($true) {
    try {
        Start-Process powershell.exe -WindowStyle Hidden -Wait -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$ps1`"")
    } catch {}
    Start-Sleep -Seconds 600
}
