# Ciclo automatico (sin el usuario): Windows lo lanza cada 10 minutos en segundo plano.
# Si hay codigo nuevo en GitHub: lo descarga, decide que hace falta (medidas de nuevo desde la cache,
# solo el informe, o nada), lo ejecuta, revisa el resultado frente a la ejecucion anterior
# (revision_automatica.md: OK / REGRESION / ERROR) y sube todo a pc-logs para Claude.
# No hace nada si no hay codigo nuevo o si ya hay otro analisis en marcha (prueba, partido).
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Out = "$Base\output"
$Log = "$Out\ciclo_automatico.log"
# el de GitHub Actions en su propio registro (02-11: un ciclo lanzado por GitHub con codigo nuevo termino a mitad sin
# decir por que, y el siguiente ciclo de 10 min borro su registro)
if ($env:GITHUB_ACTIONS) { $Log = "$Out\ciclo_actions.log" }
New-Item -ItemType Directory -Force -Path $Out | Out-Null
# senal de vida (como mucho una por hora): sale sin trabajo pero se ve que la tarea corre y por que no hizo nada
# el ciclo con el script recien llegado (27-10: una peticion con una accion nueva esperaba 10 min al ciclo siguiente)
function Relanzar {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath
    exit 0
}
# sin nada que hacer, mira GitHub cada minuto durante un rato (27-10: cada peticion tardaba hasta 10 min en empezar)
function Esperar-Novedades($minutos = 45) {
    if ($env:GITHUB_ACTIONS) { return }        # en el ejecutor de GitHub: cada peticion ya lanza su propio trabajo
    $fin = (Get-Date).AddMinutes($minutos)
    $h = (git -C $RepoDir rev-parse HEAD 2>$null)
    # este ciclo solo espera (06-11, #237): el trabajo de GitHub Actions no lo cuenta como otro analisis
    $esp = "$Out\ciclo_esperando.txt"
    try { "$PID" | Set-Content $esp } catch {}
    while ((Get-Date) -lt $fin) {
        Start-Sleep -Seconds 60
        git -C $RepoDir fetch -q origin $Rama 2>$null
        $f = (git -C $RepoDir rev-parse FETCH_HEAD 2>$null)
        if ($f -and $h -and "$f".Trim() -ne "$h".Trim()) { Remove-Item $esp -Force -ErrorAction SilentlyContinue; Relanzar }
    }
    Remove-Item $esp -Force -ErrorAction SilentlyContinue
}
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
# Cola (20-10): el fichero puede tener varios bloques separados por una linea "---", cada uno con su id, su
# accion y sus parametros; se hacen en orden, uno detras de otro en el mismo ciclo. Un solo bloque (sin "---")
# funciona igual que antes. Ids hechos: output\peticiones_hechas.txt (uno por linea) y el antiguo
# output\peticion_hecha.txt (un id). La misma lectura en Python: scripts/pc_requests.py
function Leer-Peticiones {
    $f = Join-Path $RepoDir "config\peticion_pc.txt"
    $bloques = New-Object System.Collections.ArrayList
    if (-not (Test-Path $f)) { return ,$bloques }
    $p = @{}
    foreach ($l in Get-Content $f) {
        if ($l -match "^\s*---\s*$") { if ($p.Count) { [void]$bloques.Add($p) }; $p = @{}; continue }
        if ($l -match "^\s*(\w+)\s*:\s*(.+?)\s*$") { $p[$Matches[1]] = $Matches[2] }
    }
    if ($p.Count) { [void]$bloques.Add($p) }
    return ,$bloques
}
function Peticiones-Hechas {
    $h = @()
    foreach ($f in @("$Out\peticiones_hechas.txt", "$Out\peticion_hecha.txt")) {
        if (Test-Path $f) { $h += @(Get-Content $f | ForEach-Object { "$_".Trim() } | Where-Object { $_ }) }
    }
    return ,$h
}
# el primer bloque con id y accion que aun no se ha hecho ("accion: ninguna" no cuenta), o $null
function Peticion-Pendiente {
    $hechas = Peticiones-Hechas
    foreach ($p in (Leer-Peticiones)) {
        if (-not $p["id"] -or -not $p["accion"] -or $p["accion"] -eq "ninguna") { continue }
        if ($hechas -notcontains $p["id"]) { return $p }
    }
    return $null
}
# todas las pendientes seguidas en este ciclo; para si una accion es desconocida (llega con codigo nuevo)
# o si hay codigo nuevo en GitHub: el siguiente ciclo sigue con el script nuevo
# orquestador unico (10-11, fase D de docs/orquestador.md): en cada ciclo, el registro de partidos al dia, el ejecutor
# unico vivo (tennisbio worker: el unico que ejecuta trabajos; la aplicacion y Claude solo los piden) y su estado
# (estado_trabajos.json) a pc-logs cuando cambia. Desde GitHub Actions no se arranca el ejecutor: el ejecutor de
# Actions mata al acabar los procesos que deja; lo arranca el ciclo de la tarea de Windows (cada 10 min)
# las ordenes de tennisbio del ciclo (11-11): sin reinstalar el proyecto (--no-sync; la instalacion la hacen los .bat y el
# codigo es editable) y con python -m, nunca con tennisbio.exe: el ejecutor arrancado con tennisbio.exe lo dejaba
# bloqueado y cada "uv run" que queria reinstalar fallaba (peticion 185: "failed to remove file ... tennisbio.exe")
function Tb { & uv --directory $RepoDir run --no-sync python -m tennisbio.cli @args }
function Orquestador {
    $ErrorActionPreference = "Continue"
    try {
        Push-Location $RepoDir
        # un ejecutor antiguo arrancado con tennisbio.exe y sin trabajo en curso se cierra (nada se pierde: la cola esta
        # en la base de datos) y se arranca otra vez con python -m
        $viejos = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'tennisbio(\.exe)?"?\s+worker' -and $_.CommandLine -notmatch 'tennisbio\.cli' })
        $trabajando = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match "jobs run-one" })
        if ($viejos.Count -and -not $trabajando.Count) {
            foreach ($v in $viejos) { & taskkill.exe /T /F /PID $v.ProcessId 2>&1 | Out-Null }
            "$(Get-Date -Format s) ejecutor antiguo (tennisbio.exe) cerrado sin trabajo en curso" | Add-Content "$Out\ciclo_arranque.txt"
            Start-Sleep -Seconds 3
        }
        Tb registry sync 2>&1 | Out-Null
        Tb registry list --json "$Out\registro_partidos.json" 2>&1 | Out-Null
        Tb jobs status --source ciclo --json "$Out\estado_trabajos.json" 2>&1 | Out-Null
        $st = Get-Content "$Out\estado_trabajos.json" -Raw -Encoding UTF8 | ConvertFrom-Json
        $vivo = $st.ejecutor.vivo -and -not ($viejos.Count -and -not $trabajando.Count)
        if (-not $vivo -and -not $env:GITHUB_ACTIONS) {
            Start-Process -FilePath "uv" -ArgumentList @("--directory", $RepoDir, "run", "--no-sync", "python", "-m", "tennisbio.cli", "worker") `
                -WorkingDirectory $RepoDir -WindowStyle Hidden
            "$(Get-Date -Format s) ejecutor unico arrancado" | Add-Content "$Out\ciclo_arranque.txt"
        }
        $marca = "$Out\estado_trabajos.firma"
        $antes = if (Test-Path $marca) { "$(Get-Content $marca -Raw)".Trim() } else { "" }
        if ($st.firma -and $st.firma -ne $antes) {
            Subir-Registros | Out-Null
            Set-Content $marca $st.firma
        }
    } catch { Write-Host "orquestador: $_" -ForegroundColor Yellow }
    finally { Pop-Location }
}
function Hacer-Peticiones {
    $ErrorActionPreference = "Continue"
    $n = 0
    while ($true) {
        $p = Peticion-Pendiente
        if (-not $p) { break }
        Hacer-Peticion $p
        $n++
        if ($script:PeticionDesconocida) { break }
        if ($n -ge 20) { Write-Host "20 peticiones seguidas en este ciclo: el resto, en el siguiente" -ForegroundColor Yellow; break }
        if (-not (Peticion-Pendiente)) { break }
        Subir-Registros | Out-Null                                  # el registro de la que acaba, ya
        git -C $RepoDir fetch -q origin $Rama 2>$null
        if ($LASTEXITCODE -eq 0) {
            $h = (git -C $RepoDir rev-parse HEAD).Trim()
            $f = (git -C $RepoDir rev-parse FETCH_HEAD).Trim()
            if ($h -ne $f) { Write-Host "Codigo nuevo en GitHub: la siguiente peticion de la cola, en el proximo ciclo" -ForegroundColor Yellow; break }
        }
    }
}
function Hacer-Peticion($p) {
    $script:PeticionDesconocida = $false
    $p["id"] | Add-Content "$Out\peticiones_hechas.txt"        # una sola vez, salga bien o mal
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
    } elseif ($p["accion"] -eq "completo") {
        # los partidos completos (lo pidio el usuario el 18-10): primero la lista de videos, subida ya,
        # y despues el analisis completo de todos (3_analisis_completo: partidos, informes, exportacion,
        # auditoria); se puede cortar y relanzar, continua donde lo dejo
        $lg = "$Base\output\prueba_completo.log"
        "Peticion $($p['id']): analisis completo de los partidos ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Get-ChildItem "$Base\videos" -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -match '^\.(mp4|mkv|ts|mov|avi|webm|m2ts)$' } |
            ForEach-Object { "  video: {0} ({1:N2} GB)" -f $_.FullName, ($_.Length / 1GB) } | Add-Content $lg -Encoding UTF8
        "libre C: $([math]::Round((Get-PSDrive C).Free / 1GB)) GB" | Add-Content $lg -Encoding UTF8
        # prevision antes de horas de trabajo (03-11): que etapas se rehacen en cada partido y cuanto tardaran; si el
        # peor caso pasa de 6 h (o de horas_max: N) no se lanza (04-11) y se dice en el registro
        $mx = if ($p["horas_max"]) { "$($p['horas_max'])" } else { "6" }
        & uv run python scripts/preflight.py --max-h $mx 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        $pf = $LASTEXITCODE
        Subir-Registros | Out-Null
        if ($pf -eq 3) { "Peticion $($p['id']): no se lanza, la prevision supera $mx h (prevision.md)" | Add-Content $lg -Encoding UTF8; "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8; return }
        Paso "Peticion $($p['id']): analisis completo de todos los partidos (horas; registro: analisis_completo.log)"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoDir "scripts\windows\analisis_completo.ps1") | Out-Host
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "rehacer") {
        # un partido entero de nuevo (todas sus etapas, p. ej. tras arreglar la lectura de su video) y despues
        # el analisis completo (lo que haya cambiado en los demas, informes, exportacion y auditoria)
        $m = "$($p['partido'])"
        $lg = "$Base\output\prueba_rehacer.log"
        "Peticion $($p['id']): rehacer el partido $m ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        if ($m -notmatch '^[a-z0-9][a-z0-9-]+$') { "  nombre de partido no valido: '$m'" | Add-Content $lg -Encoding UTF8; return }
        Paso "Peticion $($p['id']): el partido $m entero de nuevo y despues el analisis completo"
        & uv run tennisbio run --match $m --force 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoDir "scripts\windows\analisis_completo.ps1") | Out-Host
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "repetir") {
        # unas etapas de todos los partidos de nuevo aunque esten al dia (etapas: fine[,fine_doubtful]; 29-10: medir
        # una etapa tras cambiar su velocidad sin cambiar sus resultados) y despues el analisis completo
        $lg = "$Base\output\prueba_repetir.log"
        $et = @("$($p['etapas'])" -split '[,\s]+' | Where-Object { $_ })
        "Peticion $($p['id']): repetir $($et -join ', ') ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        if (-not $et -or ($et | Where-Object { $_ -notmatch '^[a-z_]+$' })) { "  etapas no validas: '$($p['etapas'])'" | Add-Content $lg -Encoding UTF8; return }
        Paso "Peticion $($p['id']): repetir $($et -join ', ') en todos los partidos y despues el analisis completo"
        & uv run python scripts/preflight.py --stages ($et -join ',') 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        Subir-Registros | Out-Null
        & uv run tennisbio run --all --stages @et --force 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoDir "scripts\windows\analisis_completo.ps1") | Out-Host
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "app_nuevo") {
        # B7 (04-11): un partido nuevo de principio a fin con la aplicacion, sin el ciclo: un tramo de un partido
        # (minutos: 35 por defecto) se anade como partido nuevo y la cola de la aplicacion lo analiza entero, en una
        # carpeta aparte (output\_app_nuevo, con su propio indice: TENNISBIO_SANDBOX); nunca toca el indice real
        $sbx = "$Base\output\_app_nuevo"
        $lg = "$Base\output\prueba_app_nuevo.log"
        "Peticion $($p['id']): partido nuevo con la aplicacion ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Remove-Item $sbx -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path "$sbx\videos", "$sbx\output", "$sbx\datos" | Out-Null
        $src = Get-ChildItem "$Base\videos" -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -match '^\.(mp4|mkv|ts|mov)$' } | Sort-Object Length | Select-Object -First 1
        $min = if ($p["minutos"]) { [int]$p["minutos"] } else { 35 }
        $clip = "$sbx\videos\prueba_app_$($min)m$($src.Extension)"
        & ffmpeg -v error -y -ss 1800 -i $src.FullName -t ($min * 60) -c copy $clip 2>&1 | Add-Content $lg -Encoding UTF8
        # la biblioteca tambien aparte: si no, la del usuario (C:\tenis\biblioteca) estaria activa aqui
        "paths:`n  videos: $sbx\videos`n  output: $sbx\output`n  data: $sbx\datos`n  library: $sbx\biblioteca" | Set-Content "$sbx\sandbox.yaml" -Encoding UTF8
        $env:TENNISBIO_SANDBOX = "$sbx\sandbox.yaml"
        "  tramo: $min min de $($src.Name) desde 30:00" | Add-Content $lg -Encoding UTF8
        $t0 = Get-Date
        $jug = "$(uv run python -c "from tennisbio.config import default_player; print(default_player())" 2>$null)".Trim()
        & uv run --extra app tennisbio app add $clip --si --usar nuevo --jugadora $jug 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        & uv run --extra app tennisbio app work 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        & uv run --extra app tennisbio app status 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        Remove-Item Env:\TENNISBIO_SANDBOX -ErrorAction SilentlyContinue
        "duracion total: $([math]::Round(((Get-Date) - $t0).TotalMinutes, 1)) min; termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "prevision") {
        # solo la prevision (03-11): que se rehace y cuanto tardaria, sin ejecutar nada (output\prevision.md)
        $lg = "$Base\output\prevision.log"
        "Peticion $($p['id']): prevision ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        $ar = @(); if ($p["etapas"]) { $ar = @("--stages", "$($p['etapas'])") }
        & uv run python scripts/preflight.py @ar 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        # como todos los registros: cuando termina (04-11, peticion #66; antes solo decia cuando empezaba)
        "codigo de salida: $LASTEXITCODE; termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "trabajo") {
        # un trabajo para el ejecutor unico (10-11, fase D): "comando: run --all" -> tennisbio jobs submit -- run --all;
        # no se ejecuta aqui: lo hace el ejecutor (uno por PC), y se ve en estado_trabajos.json
        $c = "$($p['comando'])".Trim()
        $lg = "$Base\output\trabajos.log"
        if (-not $c -or $c -notmatch '^[A-Za-z0-9_,. =:/-]+$') {
            "$(Get-Date -Format s) peticion $($p['id']): comando no valido: '$c'" | Add-Content $lg -Encoding UTF8; return }
        $r = Tb jobs submit --source "claude $($p['id'])" -- @($c -split '\s+') 2>&1
        "$(Get-Date -Format s) peticion $($p['id']): $r" | Add-Content $lg -Encoding UTF8
        Orquestador
    } elseif ($p["accion"] -eq "control") {
        # pausar | pausar_ya | reanudar | cancelar (trabajo: N o todos) | reiniciar: las mismas ordenes que la aplicacion
        $o = "$($p['orden'])".Trim()
        $lg = "$Base\output\trabajos.log"
        $map = @{ "pausar" = @("pause"); "pausar_ya" = @("pause", "now"); "reanudar" = @("resume"); "reiniciar" = @("restart") }
        if ($o -eq "cancelar") {
            $t = "$($p['trabajo'])".Trim()
            $a = if ($t -eq "todos") { @("cancel", "all") } elseif ($t -match '^\d+$') { @("cancel", $t) } else { $null }
        } else { $a = $map[$o] }
        if (-not $a) { "$(Get-Date -Format s) peticion $($p['id']): orden no valida: '$o'" | Add-Content $lg -Encoding UTF8; return }
        $r = Tb jobs @($a[0]) --source "claude $($p['id'])" @($a | Select-Object -Skip 1) 2>&1
        "$(Get-Date -Format s) peticion $($p['id']): $o -> $r" | Add-Content $lg -Encoding UTF8
        Orquestador
    } elseif ($p["accion"] -eq "medir") {
        # una medida de Claude con un script del repositorio (script: bench_ball -> scripts\bench_ball.py, sin
        # tocar ningun analisis); registro output\medir_<script>.log (se sube solo)
        $sc = "$($p['script'])"
        $lg = "$Base\output\medir_$sc.log"
        if ($sc -notmatch '^[a-z0-9_]+$' -or -not (Test-Path (Join-Path $RepoDir "scripts\$sc.py"))) {
            "Peticion $($p['id']): script no valido: '$sc'" | Set-Content "$Base\output\medir.log" -Encoding UTF8; return }
        "Peticion $($p['id']): medir $sc ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Paso "Peticion $($p['id']): medida scripts\$sc.py"
        # argumentos (03-11): opciones del script, solo letras, numeros, guiones, comas y espacios (p. ej. "--only ocr5,bounce")
        $ar = @()
        if ($p["argumentos"]) {
            if ("$($p['argumentos'])" -notmatch '^[A-Za-z0-9_,. =-]+$') {
                "Peticion $($p['id']): argumentos no validos: '$($p['argumentos'])'" | Add-Content $lg -Encoding UTF8; return }
            $ar = @("$($p['argumentos'])".Trim() -split '\s+')
        }
        & uv run python "scripts/$sc.py" @ar 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "recall") {
        # cuantos golpes suyos encuentra el analisis frente a los anotados por personas (F3Set, 650 golpes),
        # por lado, tipo y etapa donde se pierde cada uno, e identidad (scripts/validate_recall.py)
        $lg = "$Base\output\prueba_recall.log"
        "Peticion $($p['id']): medida de golpes encontrados frente a anotados ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        $extra = @(); if ($p["puntos"]) { $extra = @("--max-points", "$($p['puntos'])") }
        # detector=si: candidatos del detector entrenado (spotter.enabled); informe recall_validation_detector.*
        if ("$($p['detector'])" -match '^(si|true|1)$') { $extra += @("--spotter") }
        Subir-Registros | Out-Null
        # horas de trabajo: el registro sube cada 20 min para que se vea por donde va (si no, parece el PC apagado)
        $script:subido = Get-Date
        & uv run python scripts/validate_recall.py --root "$Base\datasets" @extra 2>&1 | ForEach-Object {
            "$_" | Add-Content $lg -Encoding UTF8
            if (((Get-Date) - $script:subido).TotalMinutes -ge 20) { $script:subido = Get-Date; Subir-Registros | Out-Null }
        }
        foreach ($f in @("recall_validation.md", "recall_validation.json", "recall_validation_detector.md", "recall_validation_detector.json")) {
            if (Test-Path "$Base\datasets\reports\$f") { Copy-Item "$Base\datasets\reports\$f" "$Base\output\$f" -Force }
        }
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "entreno") {
        # datos para entrenar el detector de golpes (19-10, plan hibrido): partidos de F3Set pasados por la pasada
        # barata y exportados como numeros (nunca imagenes) a datasets\spotting; suben a pc-logs/entreno_golpes
        $lg = "$Base\output\prueba_entreno.log"
        "Peticion $($p['id']): datos de entrenamiento del detector de golpes ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        $extra = @()
        if ($p["partidos"]) { $extra += @("--matches", "$($p['partidos'])") }
        if ($p["horas"]) { $extra += @("--hours", "$($p['horas'])") }
        if ($p["fps"]) { $extra += @("--fps", "$($p['fps'])") }
        if ("$($p['bola'])" -match '^si$') { $extra += @("--ball") }     # plan N2: tambien la bola (entreno_golpes_bola)
        Subir-Registros | Out-Null
        $script:subido = Get-Date
        & uv run python scripts/spotting_data.py --root "$Base\datasets" @extra 2>&1 | ForEach-Object {
            "$_" | Add-Content $lg -Encoding UTF8
            if (((Get-Date) - $script:subido).TotalMinutes -ge 20) { $script:subido = Get-Date; Subir-Registros | Out-Null }
        }
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "diag") {
        # por que un partido da pocos minutos de camara principal: hojas de fotogramas de los planos que el
        # color toma por juego y las lineas no confirman (scripts/diag_scenes.py), a pc-logs/capturas_diag
        $lg = "$Base\output\prueba_diag.log"
        "Peticion $($p['id']): diagnostico de planos ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        # carpetas: rutas relativas a C:\tenis separadas por coma (p. ej. una compilacion de F3Set); sin ellas, los partidos
        $dirs = @(); if ($p["carpetas"]) { $dirs = @($p["carpetas"].Split(",") | ForEach-Object { Join-Path $Base $_.Trim() }) }
        & uv run python scripts/diag_scenes.py "$Base\output\capturas_diag" @dirs 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "identidad") {
        # el clic del usuario (19-10): pasada barata hasta la identidad de cada partido y una foto por grupo de
        # ropa (scripts/identity_prepare.py), para que la aplicacion las ensene al momento; nunca hace el clic
        $lg = "$Base\output\prueba_identidad.log"
        "Peticion $($p['id']): preparar el clic de identidad ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        # los videos nuevos de la carpeta entran antes en el catalogo (09-11: la prueba final con los videos del usuario)
        & uv run python scripts/auto_catalog.py 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        Subir-Registros | Out-Null
        $script:subido = Get-Date
        & uv run python scripts/identity_prepare.py "$Base\output\capturas_identidad" 2>&1 | ForEach-Object {
            "$_" | Add-Content $lg -Encoding UTF8
            if (((Get-Date) - $script:subido).TotalMinutes -ge 20) { $script:subido = Get-Date; Subir-Registros | Out-Null }
        }
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "migrar") {
        # estructura definitiva (bloque 4): copia output\<id>\ a biblioteca\partidos\, comprueba la copia y solo
        # entonces la activa (scripts/migrate_library.py); nunca borra las carpetas viejas
        $lg = "$Base\output\prueba_migrar.log"
        "Peticion $($p['id']): biblioteca ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        & uv run python scripts/migrate_library.py 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "referencia") {
        # golpes de la referencia y sus series fotograma a fotograma en un zip (27-10), para diagnosticar las medidas
        # en la nube sin volver a analizar nada (scripts/pack_reference.py); se sube con los registros
        $lg = "$Base\output\prueba_referencia.log"
        $golpe = if ($p["golpe"]) { "$($p['golpe'])" } else { "forehand" }
        "Peticion $($p['id']): referencia $golpe ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        & uv run python scripts/pack_reference.py --stroke $golpe 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        "termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
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
    } elseif ($p["accion"] -eq "youtube") {
        # videos de analisis que eligio el usuario (urls: ...): texto e imagenes pequenas en output\investigacion_<id>
        $s = "$Base\output\investigacion_$($p['id'])"
        $lg = "$Base\output\prueba_youtube.log"
        "Peticion $($p['id']): videos de analisis elegidos por el usuario ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Paso "Peticion $($p['id']): videos de YouTube elegidos por el usuario en output\investigacion_$($p['id'])"
        $env:UV_NO_PROGRESS = "1"
        & uv run python scripts/youtube_research.py --out $s --urls "$($p['urls'])" 2>&1 |
            ForEach-Object { $l = "$_"; Add-Content $lg $l -Encoding UTF8; $l } | Out-Host
        "codigo de salida: $LASTEXITCODE; termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "app") {
        # la aplicacion local (nucleo): crea o lee su indice en C:\tenis\datos con los datos reales y
        # dice que recalcularia; no ejecuta ningun trabajo de la cola
        $lg = "$Base\output\prueba_app.log"
        "Peticion $($p['id']): indice de la aplicacion local ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Paso "Peticion $($p['id']): indice de la aplicacion local (registro: $lg)"
        $env:UV_NO_PROGRESS = "1"
        $planTxt = @()
        foreach ($orden in @("status", "plan", "status")) {
            "== tennisbio app $orden" | Add-Content $lg -Encoding UTF8
            & uv run tennisbio app $orden 2>&1 |
                ForEach-Object { $l = "$_"; Add-Content $lg $l -Encoding UTF8; if ($orden -eq "plan") { $planTxt += $l }; $l } | Out-Host
        }
        # trabajar: si (04-11) = despues del plan, la cola de la aplicacion SOLO si no hay ningun partido que recalcular
        # (asi solo se hacen los analisis/informes, minutos, nunca etapas)
        if ("$($p['trabajar'])" -match '^(si|true|1)$') {
            if (($planTxt -join "`n") -match '(^|\D)0 partido\(s\) a recalcular') {
                "== tennisbio app work (solo informes)" | Add-Content $lg -Encoding UTF8
                & uv run --extra app tennisbio app work 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
                & uv run tennisbio app status 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
            } else { "  no se ejecuta la cola: el plan tiene partidos que recalcular (ver arriba)" | Add-Content $lg -Encoding UTF8 }
        }
        "codigo de salida: $LASTEXITCODE; termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "ventana") {
        # la ventana de la aplicacion: todas sus pantallas pintadas con el indice real en el navegador
        # (solo lectura, sin abrir ninguna ventana al usuario) y si este PC puede abrirla (pywebview, WebView2)
        $s = "$Base\output\capturas_app"
        $lg = "$Base\output\prueba_ventana.log"
        "Peticion $($p['id']): pantallas de la aplicacion ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Paso "Peticion $($p['id']): pantallas de la aplicacion en output\capturas_app (registro: $lg)"
        $env:UV_NO_PROGRESS = "1"
        # con tope de 15 min: si algo no responde se mata con todo lo que lanzo (el 18-10 una ventana oculta
        # que no cargaba dejo el ciclo parado; nunca mas)
        $o = "$Base\output\prueba_ventana.out"
        $pr = Start-Process uv -ArgumentList @("run", "--extra", "app", "tennisbio", "app", "comprobar", $s, "--real") `
            -NoNewWindow -PassThru -RedirectStandardOutput $o -RedirectStandardError "$o.err"
        if (-not $pr.WaitForExit(900000)) {
            & taskkill.exe /T /F /PID $pr.Id 2>&1 | Out-Null
            "TOPE: sin terminar en 15 min; se ha parado (proceso $($pr.Id) y sus hijos)" | Add-Content $lg -Encoding UTF8
        }
        foreach ($f in @($o, "$o.err")) { if (Test-Path $f) { Get-Content $f -Encoding UTF8 | Add-Content $lg -Encoding UTF8 } }
        "codigo de salida: $($pr.ExitCode); termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "movil") {
        # la copia al movil de cada analisis (videos a 720p) abierta en el navegador del PC a tamano movil,
        # y el acceso directo del escritorio; tope de 40 min
        $s = "$Base\output\capturas_app"
        $lg = "$Base\output\prueba_movil.log"
        "Peticion $($p['id']): copia al movil y acceso directo ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        Paso "Peticion $($p['id']): copia al movil (registro: $lg)"
        $env:UV_NO_PROGRESS = "1"
        $o = "$Base\output\prueba_movil.out"
        $pr = Start-Process uv -ArgumentList @("run", "--extra", "app", "tennisbio", "app", "comprobar-movil", $s) `
            -NoNewWindow -PassThru -RedirectStandardOutput $o -RedirectStandardError "$o.err"
        if (-not $pr.WaitForExit(2400000)) {
            & taskkill.exe /T /F /PID $pr.Id 2>&1 | Out-Null
            "TOPE: sin terminar en 40 min; se ha parado (proceso $($pr.Id) y sus hijos)" | Add-Content $lg -Encoding UTF8
        }
        foreach ($f in @($o, "$o.err")) { if (Test-Path $f) { Get-Content $f -Encoding UTF8 | Add-Content $lg -Encoding UTF8 } }
        "codigo de salida: $($pr.ExitCode); termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
    } elseif ($p["accion"] -eq "borrar") {
        # borra carpetas de pruebas de velocidad ya documentadas (lo pide el usuario); solo nombres
        # _poc, _pocN o _pocN_M y, nombrada a mano, _poc9_largo (08-11, #146: la aplicacion ya no la usa; su
        # auditoria sigue en pc-logs): nunca _smoke ni nada mas
        $lg = "$Base\output\prueba_borrado.log"
        "Peticion $($p['id']): borrar carpetas de pruebas ($(Get-Date -Format s))" | Set-Content $lg -Encoding UTF8
        foreach ($c in ("$($p['carpetas'])" -split ",")) {
            $c = $c.Trim()
            if ($c -notmatch '^(_poc\d*(_\d+)?|_poc9_largo)$') { "  no se toca (nombre no permitido): '$c'" | Add-Content $lg -Encoding UTF8; continue }
            $d = "$Base\output\$c"
            if (-not (Test-Path $d)) { "  no existe: $c" | Add-Content $lg -Encoding UTF8; continue }
            $mb = [math]::Round(((Get-ChildItem $d -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1MB, 1)
            try { Remove-Item $d -Recurse -Force -ErrorAction Stop; "  borrada: $c ($mb MB)" | Add-Content $lg -Encoding UTF8 }
            catch { "  ERROR al borrar ${c}: $_" | Add-Content $lg -Encoding UTF8 }
        }
        "libre en C: $([math]::Round((Get-PSDrive C).Free / 1GB)) GB; termina $(Get-Date -Format s)" | Add-Content $lg -Encoding UTF8
        Get-Content $lg | Out-Host
    } else {
        # una accion nueva llega en el mismo git pull que su peticion, y este proceso sigue con la version vieja de
        # este script (19-10 y 20-10, peticiones 33 y 36 perdidas): no se da por hecha; el siguiente ciclo, ya con
        # el script nuevo, la hace
        Write-Host "Peticion $($p['id']) con accion '$($p['accion'])' que este ciclo aun no conoce: se hara en el siguiente" -ForegroundColor Yellow
        # (y la cola para aqui: el orden de las peticiones se respeta)
        $script:PeticionDesconocida = $true
        $hf = "$Out\peticiones_hechas.txt"
        $resto = @(Get-Content $hf -ErrorAction SilentlyContinue | Where-Object { "$_".Trim() -ne $p["id"] })
        if ($resto.Count) { $resto | Set-Content $hf } else { Remove-Item $hf -Force -ErrorAction SilentlyContinue }
    }
}
# el equipo no se suspende mientras el ciclo exista (la pantalla si puede apagarse): cada arranque, cada
# 10 min, reinicia el contador de inactividad de Windows; durante un trabajo largo lo mantiene despierto
try { Sin-Suspender } catch {}
# prioridad normal para este ciclo y todo lo que lance (02-11): la tarea de Windows lo arrancaba por debajo de lo
# normal y el analisis iba unas 3 veces mas lento; los procesos hijos heredan la prioridad
try { (Get-Process -Id $PID).PriorityClass = [System.Diagnostics.ProcessPriorityClass]::Normal } catch {}
# rastro de cada arranque (antes de cualquier cosa que pueda fallar): se sube con la senal de vida
try { "arranque: $(Get-Date -Format s) (pid $PID)" | Set-Content "$Out\ciclo_arranque.txt" } catch {}

# PAUSA TOTAL pedida por el usuario (29-10): config/pausa_pc.txt con "pausa: si" (en GitHub, o ya en el disco si no hay
# red) corta todo lo de este proyecto que este en marcha, apaga la tarea de Windows de cada 10 min y no hace nada mas;
# el bucle de inicio de sesion (ciclo_bucle.ps1) tampoco sigue: no se corta desde aqui (es el abuelo de este ciclo),
# lee la pausa del disco y termina. Se reanuda solo cuando Claude pone "pausa: no".
function En-Pausa {
    $txt = ""
    try {
        git -C $RepoDir fetch -q origin $Rama 2>$null
        if ($LASTEXITCODE -eq 0) { $txt = (git -C $RepoDir show "FETCH_HEAD:config/pausa_pc.txt" 2>$null) -join "`n" }
    } catch {}
    if (-not $txt) { $txt = (Get-Content (Join-Path $RepoDir "config\pausa_pc.txt") -ErrorAction SilentlyContinue) -join "`n" }
    return ($txt -match '(?m)^pausa:\s*si\b')
}
if (En-Pausa) {
    $ErrorActionPreference = "Continue"
    $padre = -1
    try { $padre = [int](Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId } catch {}
    $mios = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessId -ne $PID -and $_.ProcessId -ne $padre -and $_.CommandLine -match "prueba_rapida|analisis_completo|recalcular_medidas|solo_informe|ciclo_automatico|medir_recursos|instalar" }
    foreach ($o in $mios) { & taskkill.exe /T /F /PID $o.ProcessId 2>&1 | Out-Null }
    try { Disable-ScheduledTask -TaskName "tenis-ciclo-automatico" -ErrorAction SilentlyContinue | Out-Null } catch {}
    # el codigo al dia (sin ejecutar nada): asi la pausa tambien esta en el disco y vale sin red
    try { git -C $RepoDir merge -q --ff-only FETCH_HEAD 2>&1 | Out-Null } catch {}
    "$(Get-Date -Format s) EN PAUSA (config/pausa_pc.txt): cortados $((@($mios) | ForEach-Object { $_.ProcessId }) -join ','); tarea de Windows apagada" |
        Add-Content "$Out\paradas.log"
    try { "en pausa desde $(Get-Date -Format s): nada en marcha" | Set-Content "$Out\ciclo_vivo.txt"; Subir-Registros | Out-Null } catch {}
    exit 0
}
# fuera de pausa, la tarea de Windows vuelve a estar encendida (Registrar-Ciclo la deja al dia mas abajo)
try { Enable-ScheduledTask -TaskName "tenis-ciclo-automatico" -ErrorAction SilentlyContinue | Out-Null } catch {}

# los ciclos que nos lanzaron para usar el script nuevo (Relanzar) no cuentan como otro analisis: el padre y
# tambien el abuelo y los de mas arriba (06-11, peticion #237: un ciclo que esperaba novedades relanzo uno que, al
# terminar, relanzo otro; este veia al abuelo como "otro analisis" y la peticion 110 espero 22 min al ciclo siguiente)
function Antecesores {
    $ids = @()
    $p = $PID
    for ($i = 0; $i -lt 12; $i++) {
        $pp = -1
        try { $pp = [int](Get-CimInstance Win32_Process -Filter "ProcessId=$p").ParentProcessId } catch {}
        if ($pp -le 0 -or $ids -contains $pp) { break }
        $ids += $pp
        $p = $pp
    }
    return ,$ids
}
$PadrePid = -1
try { $PadrePid = [int](Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId } catch {}
$MisAntecesores = Antecesores
# otro analisis en marcha (los .bat del usuario o una ejecucion anterior de este ciclo): no molestar
function Otros-Analisis {
    # para el trabajo de GitHub Actions, un ciclo que solo espera novedades (Esperar-Novedades) no es trabajo
    $esperando = -1
    if ($env:GITHUB_ACTIONS) { try { $esperando = [int]("$(Get-Content "$Out\ciclo_esperando.txt" -ErrorAction Stop)".Trim()) } catch {} }
    # 11-11: dos ciclos de GitHub Actions que esperan a "otro analisis" se esperaban el uno al otro (desde el 10-11
    # 12:41 hasta la parada 15): un ciclo que solo espera se apunta en output\esperando\<pid> y no cuenta como trabajo
    $quietos = @(Get-ChildItem "$Out\esperando" -File -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.Name })
    return @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessId -ne $PID -and $_.ProcessId -ne $PadrePid -and $MisAntecesores -notcontains $_.ProcessId -and
            $_.ProcessId -ne $esperando -and $quietos -notcontains $_.ProcessId -and
            $_.CommandLine -match "prueba_rapida|analisis_completo|recalcular_medidas|solo_informe|ciclo_automatico|instalar" }) +
        # un trabajo del ejecutor unico (10-11, docs/orquestador.md) tambien es un analisis en marcha
        @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match "jobs run-one" })
}
$ocupado = Otros-Analisis
if (-not $ocupado.Count) { $ocupado = $null }
# parada pedida por Claude (24-10): config/parar_pc.txt en GitHub con "id: N" nuevo corta el trabajo en marcha (un
# trabajo largo que va mal, con codigo viejo, ya no espera a que el usuario reinicie el PC); se mira sin descargar
# el codigo (git show del FETCH_HEAD), una vez por id (output\paradas_hechas.txt), y queda en output\paradas.log
if ($ocupado) {
    $ErrorActionPreference = "Continue"
    git -C $RepoDir fetch -q origin $Rama 2>$null
    if ($LASTEXITCODE -eq 0) {
        $txt = (git -C $RepoDir show "FETCH_HEAD:config/parar_pc.txt" 2>$null) -join "`n"
        if ($txt -match '(?m)^id:\s*(\d+)') {
            $idp = $Matches[1]
            $hechas = @(Get-Content "$Out\paradas_hechas.txt" -ErrorAction SilentlyContinue | ForEach-Object { "$_".Trim() })
            if ($hechas -notcontains $idp) {
                $idp | Add-Content "$Out\paradas_hechas.txt"
                $pids = ($ocupado | ForEach-Object { $_.ProcessId }) -join ','
                try { & uv --directory $RepoDir run --no-sync python -m tennisbio.cli jobs pause now --source parada 2>&1 | Out-Null } catch {}
                foreach ($o in $ocupado) { & taskkill.exe /T /F /PID $o.ProcessId 2>&1 | Out-Null }
                "$(Get-Date -Format s) parada $idp pedida por Claude: cortados $pids" | Add-Content "$Out\paradas.log"
                $ocupado = $null
            }
        }
    }
}
# arreglos solo de la aplicacion (src\tennisbio\app\ y docs\) tambien con un trabajo largo en marcha (24-10: la
# ventana colgada tuvo que esperar a que acabara un trabajo de horas): el trabajo en marcha no usa esos ficheros, y
# la aplicacion los lee al abrirse. Cualquier otro cambio espera, como siempre, a que el PC quede libre.
if ($ocupado) {
    $ErrorActionPreference = "Continue"
    $h = (git -C $RepoDir rev-parse HEAD).Trim()
    $f = (git -C $RepoDir rev-parse FETCH_HEAD 2>$null)
    if ($f) { $f = "$f".Trim() }
    if ($f -and $h -ne $f) {
        $files = @(git -C $RepoDir diff --name-only $h $f)
        $otros = @($files | Where-Object { $_ -and $_ -notmatch '^(src/tennisbio/app/|docs/)' })
        if ($files.Count -and -not $otros.Count) {
            git -C $RepoDir merge -q --ff-only $f 2>&1 | Out-Null
            "$(Get-Date -Format s) solo la aplicacion al dia ($($h.Substring(0,7)) -> $($f.Substring(0,7))) con un trabajo en marcha" |
                Add-Content "$Out\ciclo_arranque.txt"
        }
    }
}
# uso de recursos mientras dure el analisis (26-10): una sola medicion a la vez, oculta; termina sola con el analisis
if ($ocupado) {
    $mr = Join-Path $PSScriptRoot "medir_recursos.ps1"
    $ya = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "medir_recursos" })
    if ((Test-Path $mr) -and -not $ya.Count) {
        try { Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$mr`"") } catch {}
    }
}
# el trabajo de GitHub Actions espera a que acabe el otro y entonces hace la peticion (06-11, peticion #237: salia en
# 2 s y la peticion esperaba al ciclo de 10 min siguiente, o a que acabara el analisis largo y luego otros 10 min).
# Mientras espera, los ciclos de 10 min lo ven como otro analisis y no la toman; una parada (parar_pc.txt) o la pausa
# lo cortan como a cualquier otro. Si el script cambio mientras esperaba, sigue con el nuevo (Relanzar).
if ($ocupado -and $env:GITHUB_ACTIONS) {
    $ErrorActionPreference = "Continue"
    $t0 = Get-Date
    $guion = (Get-Item $PSCommandPath).LastWriteTime
    try { "$(Get-Date -Format s) GitHub Actions espera a que acabe otro analisis ($(($ocupado | ForEach-Object { $_.ProcessId }) -join ','))" |
        Add-Content "$Out\ciclo_arranque.txt" } catch {}
    New-Item -ItemType Directory -Force -Path "$Out\esperando" | Out-Null
    $yo = "$Out\esperando\$PID"
    "$(Get-Date -Format s)" | Set-Content $yo
    try {
        while ($ocupado -and ((Get-Date) - $t0).TotalHours -lt 70) {
            Start-Sleep -Seconds 30
            $ocupado = Otros-Analisis
            if (-not $ocupado.Count) { $ocupado = $null }
        }
    } finally { Remove-Item $yo -Force -ErrorAction SilentlyContinue }
    # los apuntes de ciclos que ya no existen (cortados por una parada o un reinicio) se borran
    Get-ChildItem "$Out\esperando" -File -ErrorAction SilentlyContinue | Where-Object {
        -not (Get-Process -Id ([int]$_.Name) -ErrorAction SilentlyContinue) } | Remove-Item -Force -ErrorAction SilentlyContinue
    if (-not $ocupado) {
        try { "$(Get-Date -Format s) GitHub Actions: libre tras $([math]::Round(((Get-Date) - $t0).TotalMinutes, 1)) min de espera" |
            Add-Content "$Out\ciclo_arranque.txt" } catch {}
        if ((Get-Item $PSCommandPath).LastWriteTime -gt $guion) { Relanzar }
    }
}
if ($ocupado) { Senal-Vida "otro analisis en marcha ($(($ocupado | ForEach-Object { $_.ProcessId }) -join ','))" }

Refrescar-Path
Registrar-Ciclo          # tarea de Windows al dia (limite de 12 h, instancias en paralelo) aunque no haya codigo nuevo
Orquestador              # registro unico, ejecutor vivo y su estado a pc-logs cuando cambia (10-11, fase D)
if (-not (Tiene git) -or -not (Test-Path "$RepoDir\.git")) { Senal-Vida "sin git o sin repositorio en $RepoDir" }
$ErrorActionPreference = "Continue"
git -C $RepoDir fetch -q origin $Rama 2>$null
if ($LASTEXITCODE -ne 0) { Senal-Vida "git fetch fallo (sin red o sin permiso)" }
$antes = (git -C $RepoDir rev-parse HEAD).Trim()
$nuevo = (git -C $RepoDir rev-parse FETCH_HEAD).Trim()
$forzar = Test-Path "$Out\forzar_ciclo.txt"
$relanzar = $false
if ($antes -eq $nuevo -and -not $forzar) {
    # sin codigo nuevo: una prueba pedida por Claude (el codigo que la pide llego en el ciclo anterior)
    # o la prueba de modelos a medias (otro tramo)
    $pet = Peticion-Pendiente
    if ($pet -or (Pruebas-Pendientes)) {
        Set-Location $RepoDir
        Start-Transcript -Path $Log | Out-Null
        try { if ($pet) { Hacer-Peticiones } else { Prueba-Modelos } } finally { Resumen-Tiempo; Stop-Transcript | Out-Null; Subir-Registros }
        exit 0
    }
    Esperar-Novedades
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
    # codigo nuevo: el ejecutor unico se reinicia entre dos trabajos (nunca a mitad) para usarlo (10-11, fase D)
    try { Tb jobs restart --source ciclo 2>&1 | Out-Host } catch {}
    Start-Sleep -Seconds 15          # un ejecutor sin trabajo sale en ~10 s; Orquestador arranca el nuevo
    Orquestador
    # las pruebas del codigo nuevo en este PC, en segundo plano y por debajo de lo normal (03-11; pruebas_fondo.ps1)
    try {
        Start-Process wscript.exe -ArgumentList @("//B", "`"$(Join-Path $PSScriptRoot 'oculto.vbs')`"",
            "`"$(Join-Path $PSScriptRoot 'pruebas_fondo.ps1')`"") | Out-Null
    } catch {}
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
    # pruebas pedidas por Claude en config/peticion_pc.txt (ids nuevos, en cola): primero eso, sin la prueba de modelos a la vez
    if (Peticion-Pendiente) { $relanzar = $true }
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
# las peticiones con el script nuevo (el de este proceso es el anterior a la actualizacion)
if ($relanzar) { Relanzar }
