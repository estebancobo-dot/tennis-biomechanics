# Bucle del ciclo automatico: arranca solo al iniciar sesion (carpeta Inicio de Windows) y se queda en
# segundo plano. Cada 10 minutos lanza ciclo_automatico.ps1 desde el disco, asi que cada version nueva
# del ciclo que llegue con el codigo se usa sola, sin volver a instalar nada. Una sola copia a la vez.
$m = New-Object System.Threading.Mutex($false, "Global\tenis-ciclo-bucle")
if (-not $m.WaitOne(0)) { exit 0 }
$ps1 = Join-Path $PSScriptRoot "ciclo_automatico.ps1"
$vbs = Join-Path $PSScriptRoot "oculto.vbs"
# el equipo no se suspende mientras el bucle vive (la pantalla si puede apagarse)
try {
    Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);' -ErrorAction SilentlyContinue
    [Win32.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null
} catch {}
$repo = Split-Path (Split-Path $PSScriptRoot)
$pausa = Join-Path $repo "config\pausa_pc.txt"
# 15-11 (#304): en pausa el bucle ya no termina: no hace ningun trabajo, pero cada 10 minutos mira en GitHub si Claude
# quito la pausa ("pausa: no"); si es asi, lanza el ciclo, que trae el codigo y sigue. Antes, para salir de la pausa
# hacia falta un doble clic en el PC (y el usuario puede no estar delante)
function Pausa-Quitada-En-GitHub {
    try {
        $rama = (git -C $repo rev-parse --abbrev-ref HEAD 2>$null | Select-Object -First 1)
        if (-not $rama) { return $false }
        git -C $repo fetch -q origin $rama 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        $txt = (git -C $repo show "FETCH_HEAD:config/pausa_pc.txt" 2>$null) -join "`n"
        return ($txt -and ($txt -notmatch '(?m)^pausa:\s*si\b'))
    } catch { return $false }
}
while ($true) {
    # pausa total pedida por el usuario (config/pausa_pc.txt, "pausa: si"): ningun trabajo; solo se escucha (29-10, 15-11)
    if (((Get-Content $pausa -ErrorAction SilentlyContinue) -match '^pausa:\s*si\b') -and -not (Pausa-Quitada-En-GitHub)) {
        # en pausa el equipo puede suspenderse como siempre (solo se escucha mientras esta despierto)
        try { [Win32.Power]::SetThreadExecutionState([uint32]"0x80000000") | Out-Null } catch {}
        Start-Sleep -Seconds 600
        continue
    }
    try { [Win32.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null } catch {}
    try {
        # sin ventana ni parpadeo (oculto.vbs); si faltara, como antes
        if (Test-Path $vbs) { Start-Process wscript.exe -Wait -ArgumentList @("//B", "`"$vbs`"", "`"$ps1`"") }
        else { Start-Process powershell.exe -WindowStyle Hidden -Wait -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$ps1`"") }
    } catch {}
    Start-Sleep -Seconds 600
}
