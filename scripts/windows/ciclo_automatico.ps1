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
    while ((Get-Date) -lt $fin) {
        Start-Sleep -Seconds 60
        git -C $RepoDir fetch -q origin $Rama 2>$null
        $f = (git -C $RepoDir rev-parse FETCH_HEAD 2>$null)
        if ($f -and $h -and "$f".Trim() -ne "$h".Trim()) { Relanzar }
    }
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
        Subir-Registros | Out-Null
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
        & uv run tennisbio run --all --stages @et --force 2>&1 | ForEach-Object { "$_" } | Add-Content $lg -Encoding UTF8
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoDir "scripts\windows\analisis_completo.ps1") | Out-Host
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
        foreach ($orden in @("status", "plan", "status")) {
            "== tennisbio app $orden" | Add-Content $lg -Encoding UTF8
            & uv run tennisbio app $orden 2>&1 |
                ForEach-Object { $l = "$_"; Add-Content $lg $l -Encoding UTF8; $l } | Out-Host
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
# rastro de cada arranque (antes de cualquier cosa que pueda fallar): se sube con la senal de vida
try { "arranque: $(Get-Date -Format s) (pid $PID)" | Set-Content "$Out\ciclo_arranque.txt" } catch {}

# el ciclo que nos lanzo para usar el script nuevo (Relanzar) no cuenta como otro analisis
$PadrePid = -1
try { $PadrePid = [int](Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId } catch {}
# otro analisis en marcha (los .bat del usuario o una ejecucion anterior de este ciclo): no molestar
$ocupado = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessId -ne $PID -and $_.ProcessId -ne $PadrePid -and $_.CommandLine -match "prueba_rapida|analisis_completo|recalcular_medidas|solo_informe|ciclo_automatico|instalar" }
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
