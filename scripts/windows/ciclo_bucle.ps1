# Bucle del ciclo automatico: arranca solo al iniciar sesion (carpeta Inicio de Windows) y se queda en
# segundo plano. Cada 10 minutos lanza ciclo_automatico.ps1 desde el disco, asi que cada version nueva
# del ciclo que llegue con el codigo se usa sola, sin volver a instalar nada. Una sola copia a la vez.
$m = New-Object System.Threading.Mutex($false, "Global\tenis-ciclo-bucle")
if (-not $m.WaitOne(0)) { exit 0 }
$ps1 = Join-Path $PSScriptRoot "ciclo_automatico.ps1"
# el equipo no se suspende mientras el bucle vive (la pantalla si puede apagarse)
try {
    Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);' -ErrorAction SilentlyContinue
    [Win32.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null
} catch {}
while ($true) {
    try {
        Start-Process powershell.exe -WindowStyle Hidden -Wait -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$ps1`"")
    } catch {}
    Start-Sleep -Seconds 600
}
