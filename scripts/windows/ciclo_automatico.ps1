# Ciclo automatico (sin el usuario): Windows lo lanza cada 10 minutos en segundo plano.
# Si hay codigo nuevo en GitHub: lo descarga, decide que hace falta (medidas de nuevo desde la cache,
# solo el informe, o nada), lo ejecuta, revisa el resultado frente a la ejecucion anterior
# (revision_automatica.md: OK / REGRESION / ERROR) y sube todo a pc-logs para Claude.
# No hace nada si no hay codigo nuevo o si ya hay otro analisis en marcha (prueba, partido).
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Out = "$Base\output"
$Log = "$Out\ciclo_automatico.log"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
# senal de vida (como mucho una por hora): sale sin trabajo pero se ve que la tarea corre y por que no hizo nada
function Senal-Vida($motivo) {
    $vivo = "$Out\ciclo_vivo.txt"
    try { "$(Get-Date -Format s) $motivo" | Add-Content "$Out\ciclo_arranque.txt" } catch {}
    if (-not (Test-Path $vivo) -or ((Get-Date) - (Get-Item $vivo).LastWriteTime).TotalMinutes -ge 60) {
        "ultimo ciclo sin trabajo: $(Get-Date -Format s); $motivo" | Set-Content $vivo
        Subir-Registros | Out-Null
    }
    exit 0
}
# rastro de cada arranque (antes de cualquier cosa que pueda fallar): se sube con la senal de vida
try { "arranque: $(Get-Date -Format s) (pid $PID)" | Set-Content "$Out\ciclo_arranque.txt" } catch {}

# otro analisis en marcha (los .bat del usuario o una ejecucion anterior de este ciclo): no molestar
$ocupado = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match "prueba_rapida|analisis_completo|recalcular_medidas|solo_informe|ciclo_automatico|instalar" }
if ($ocupado) { Senal-Vida "otro analisis en marcha ($(($ocupado | ForEach-Object { $_.ProcessId }) -join ','))" }

Refrescar-Path
if (-not (Tiene git) -or -not (Test-Path "$RepoDir\.git")) { Senal-Vida "sin git o sin repositorio en $RepoDir" }
$ErrorActionPreference = "Continue"
git -C $RepoDir fetch -q origin $Rama 2>$null
if ($LASTEXITCODE -ne 0) { Senal-Vida "git fetch fallo (sin red o sin permiso)" }
$antes = (git -C $RepoDir rev-parse HEAD).Trim()
$nuevo = (git -C $RepoDir rev-parse FETCH_HEAD).Trim()
$forzar = Test-Path "$Out\forzar_ciclo.txt"
if ($antes -eq $nuevo -and -not $forzar) { Senal-Vida "sin codigo nuevo ($($antes.Substring(0,7)))" }

Start-Transcript -Path $Log | Out-Null
try {
    $cambios = @(git -C $RepoDir diff --name-only $antes $nuevo)
    Paso "Codigo nuevo ($($antes.Substring(0,7)) -> $($nuevo.Substring(0,7))): $($cambios.Count) ficheros"
    $cambios | ForEach-Object { "    $_" } | Out-Host
    Actualizar-Codigo
    Comprobar-Instalacion
    Set-Location $RepoDir
    if ($forzar) { $modo = "medidas"; Remove-Item "$Out\forzar_ciclo.txt" -Force -ErrorAction SilentlyContinue }
    else {
        $r = & uv run python scripts/auto_cycle.py decide @cambios | Select-Object -Last 1
        $modo = if ($r) { "$r".Trim() } else { "informe" }
    }
    Paso "Que hace falta: $modo"
    $aud = "$Out\_smoke\auditoria\auditoria.json"
    $prev = "$Out\_smoke\auditoria\auditoria_anterior.json"
    if ($modo -ne "nada" -and (Test-Path $aud)) { Copy-Item $aud $prev -Force }
    $ErrorActionPreference = "Stop"
    if ($modo -eq "medidas") { Ejecutar uv @("run", "python", "scripts/recompute_measures.py") }
    elseif ($modo -eq "informe") { Ejecutar uv @("run", "python", "scripts/rebuild_report.py") }
    $ErrorActionPreference = "Continue"
    if ($modo -ne "nada") {
        Paso "Revision automatica frente a la ejecucion anterior"
        & uv run python scripts/auto_cycle.py review $aud $prev "$Out\revision_automatica.md" $Log 2>&1 | Out-Host
    }
    Ok "Ciclo automatico terminado ($modo)."
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    "# Revision automatica: ERROR`n`n$_" | Set-Content "$Out\revision_automatica.md" -Encoding UTF8
} finally {
    Resumen-Tiempo
    Stop-Transcript | Out-Null
    Subir-Registros
}
