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
    # con un analisis en marcha se sube cada 20 min (Claude ve su registro mientras avanza); sin trabajo, cada hora
    $cada = if ($motivo -like "otro analisis*") { 20 } else { 60 }
    if (-not (Test-Path $vivo) -or ((Get-Date) - (Get-Item $vivo).LastWriteTime).TotalMinutes -ge $cada) {
        "ultimo ciclo sin trabajo: $(Get-Date -Format s); $motivo" | Set-Content $vivo
        Subir-Registros | Out-Null
    }
    exit 0
}
# prueba de modelos (scripts/model_trials.py) en tramos de 40 min: sigue donde lo dejo, ciclo a ciclo
function Pruebas-Pendientes {
    $pm = "$Base\datasets\reports\model_trials.json"
    if (-not (Test-Path $pm)) { return $true }
    try { $j = Get-Content $pm -Raw | ConvertFrom-Json; return (-not $j.complete) -or ($j.version -lt 2) } catch { return $true }
}
function Prueba-Modelos {
    Paso "Prueba de modelos (pose y bola, actual frente a alternativas; tramo de 40 min, sigue en el proximo ciclo)"
    & uv run python scripts/model_trials.py --root "$Base\datasets" --device dml --budget-min 40 2>&1 | Out-Host
}
# pruebas que pide Claude desde el repositorio (config/peticion_pc.txt: "id: N" y "accion: ..."), una vez cada id
#   poc = prueba de velocidad en carpetas aparte: 4 min (_poc4) y, si sale bien, 35 min (_poc); nunca toca _smoke
#   largo = el video entero en output\_pocN_largo (una noche); nunca toca _smoke
#   informe (con "carpeta: _pocN_largo") = medidas desde las caches + informe + auditoria de esa carpeta (minutos)
function Leer-Peticion {
    $f = Join-Path $RepoDir "config\peticion_pc.txt"
    if (-not (Test-Path $f)) { return $null }
    $p = @{}
    foreach ($l in Get-Content $f) { if ($l -match "^\s*(\w+)\s*:\s*(.+?)\s*$") { $p[$Matches[1]] = $Matches[2] } }
    return $p
}
function Peticion-Pendiente {
    $p = Leer-Peticion
    if (-not $p -or -not $p["id"] -or $p["accion"] -eq "ninguna") { return $false }
    $hecha = "$Out\peticion_hecha.txt"
    return -not ((Test-Path $hecha) -and ((Get-Content $hecha -Raw).Trim() -eq $p["id"]))
}
function Hacer-Peticion {
    $p = Leer-Peticion
    $p["id"] | Set-Content "$Out\peticion_hecha.txt"           # una sola vez, salga bien o mal
    $ps1 = Join-Path $RepoDir "scripts\windows\prueba_rapida.ps1"
    if ($p["accion"] -eq "poc") {
        # carpetas nuevas por peticion: sin caches de otra prueba, el tiempo medido es el real
        $s4 = "_poc4"; $s35 = "_poc"
        if ($p["id"] -ne "1") { $s4 = "_poc$($p['id'])_4"; $s35 = "_poc$($p['id'])_35" }
        Paso "Peticion $($p['id']): prueba de velocidad, 4 min de partido en output\$s4"
        $t0 = Get-Date
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ps1 -Minutos 4 -Salida $s4 | Out-Host
        $inf = "$Base\output\$s4\informe\index.html"
        if ((Test-Path $inf) -and (Get-Item $inf).LastWriteTime -gt $t0) {
            Paso "Peticion $($p['id']): sin errores; ahora 35 min de partido en output\$s35"
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ps1 -Minutos 35 -Salida $s35 | Out-Host
        } else { Write-Host "La prueba de 4 min no termino bien: no se lanza la de 35 (ver prueba$s4.log)" -ForegroundColor Red }
    } elseif ($p["accion"] -eq "largo") {
        # el video entero (tramo largo) en su propia carpeta _pocN_largo: muchos golpes por situacion
        # y el tiempo real de un partido; nunca toca _smoke
        $s = "_poc$($p['id'])_largo"
        Paso "Peticion $($p['id']): el video entero en output\$s (unas 6-7 h)"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ps1 -Minutos 600 -Salida $s | Out-Host
    } elseif ($p["accion"] -eq "informe") {
        # medidas de nuevo desde las caches de una prueba ya hecha (sin pose ni video nuevos) + informe
        # y auditoria de esa carpeta; registro en output\prueba<carpeta>_informe.log (se sube solo)
        $c = "$($p['carpeta'])"
        if ($c -notmatch '^_[A-Za-z0-9_-]+$' -or -not (Test-Path "$Base\output\$c")) {
            Write-Host "Peticion $($p['id']): carpeta no valida o inexistente: '$c' (p. ej. carpeta: _poc9_largo)" -ForegroundColor Red
            return
        }
        $lg = "$Base\output\prueba$($c)_informe.log"
        "Peticion $($p['id']): medidas desde las caches, informe y auditoria de output\$c ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Paso "Peticion $($p['id']): medidas desde las caches, informe y auditoria de output\$c (registro: $lg)"
        $env:UV_NO_PROGRESS = "1"
        # linea a linea en UTF-8 (Tee-Object de PowerShell 5.1 escribiria UTF-16)
        & uv run python scripts/recompute_measures.py --out-name $c 2>&1 |
            ForEach-Object { $l = "$_"; Add-Content $lg $l -Encoding UTF8; $l } | Out-Host
        "codigo de salida: $LASTEXITCODE; termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "borrar") {
        # borra carpetas de pruebas de velocidad ya documentadas (lo pide el usuario); solo nombres
        # _poc, _pocN o _pocN_M: nunca _poc9_largo, _smoke ni nada mas
        $lg = "$Base\output\prueba_borrado.log"
        "Peticion $($p['id']): borrar carpetas de pruebas ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        foreach ($c in ("$($p['carpetas'])" -split ",")) {
            $c = $c.Trim()
            if ($c -notmatch '^_poc\d*(_\d+)?$') { "  no se toca (nombre no permitido): '$c'" | Add-Content $lg -Encoding UTF8; continue }
            $d = "$Base\output\$c"
            if (-not (Test-Path $d)) { "  no existe: $c" | Add-Content $lg -Encoding UTF8; continue }
            $mb = [math]::Round(((Get-ChildItem $d -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1MB, 1)
            try { Remove-Item $d -Recurse -Force -ErrorAction Stop; "  borrada: $c ($mb MB)" | Add-Content $lg -Encoding UTF8 }
            catch { "  ERROR al borrar ${c}: $_" | Add-Content $lg -Encoding UTF8 }
        }
        "libre en C: $([math]::Round((Get-PSDrive C).Free / 1GB)) GB; termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
        Get-Content $lg | Out-Host
    } else { Write-Host "Peticion desconocida: $($p['accion'])" -ForegroundColor Yellow }
}
# el equipo no se suspende mientras el ciclo exista (la pantalla si puede apagarse): cada arranque, cada
# 10 min, reinicia el contador de inactividad de Windows; durante un trabajo largo lo mantiene despierto
try { Sin-Suspender } catch {}
# rastro de cada arranque (antes de cualquier cosa que pueda fallar): se sube con la senal de vida
try { "arranque: $(Get-Date -Format s) (pid $PID)" | Set-Content "$Out\ciclo_arranque.txt" } catch {}

# otro analisis en marcha (los .bat del usuario o una ejecucion anterior de este ciclo): no molestar
$ocupado = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match "prueba_rapida|analisis_completo|recalcular_medidas|solo_informe|ciclo_automatico|instalar" }
if ($ocupado) { Senal-Vida "otro analisis en marcha ($(($ocupado | ForEach-Object { $_.ProcessId }) -join ','))" }

Refrescar-Path
Registrar-Ciclo          # tarea de Windows al dia (limite de 12 h, instancias en paralelo) aunque no haya codigo nuevo
if (-not (Tiene git) -or -not (Test-Path "$RepoDir\.git")) { Senal-Vida "sin git o sin repositorio en $RepoDir" }
$ErrorActionPreference = "Continue"
git -C $RepoDir fetch -q origin $Rama 2>$null
if ($LASTEXITCODE -ne 0) { Senal-Vida "git fetch fallo (sin red o sin permiso)" }
$antes = (git -C $RepoDir rev-parse HEAD).Trim()
$nuevo = (git -C $RepoDir rev-parse FETCH_HEAD).Trim()
$forzar = Test-Path "$Out\forzar_ciclo.txt"
if ($antes -eq $nuevo -and -not $forzar) {
    # sin codigo nuevo: una prueba pedida por Claude (el codigo que la pide llego en el ciclo anterior)
    # o la prueba de modelos a medias (otro tramo)
    $pet = Peticion-Pendiente
    if ($pet -or (Pruebas-Pendientes)) {
        Set-Location $RepoDir
        Start-Transcript -Path $Log | Out-Null
        try { if ($pet) { Hacer-Peticion } else { Prueba-Modelos } } finally { Resumen-Tiempo; Stop-Transcript | Out-Null; Subir-Registros }
        exit 0
    }
    Senal-Vida "sin codigo nuevo ($($antes.Substring(0,7)))"
}

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
    # prueba de modelos en este PC (scripts/model_trials.py): cuando cambia la prueba o aun no existe
    # prueba pedida por Claude en config/peticion_pc.txt (id nuevo): primero eso, sin la prueba de modelos a la vez
    if (Peticion-Pendiente) { Hacer-Peticion }
    elseif ((Pruebas-Pendientes) -or ($cambios -match "model_trials\.py|pose/variants\.py")) { Prueba-Modelos }
    Ok "Ciclo automatico terminado ($modo)."
} catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    "# Revision automatica: ERROR`n`n$_" | Set-Content "$Out\revision_automatica.md" -Encoding UTF8
} finally {
    Resumen-Tiempo
    Stop-Transcript | Out-Null
    Subir-Registros
}
