# Funciones comunes de los scripts de Windows (se cargan con ". comun.ps1").
$Base = "C:\tenis"
$RepoDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)       # scripts\windows -> repo
$RepoUrl = "https://github.com/estebancobo-dot/tennis-biomechanics.git"
$Rama = "claude/tennis-biomech-setup-jggqb0"

# Python y PowerShell en UTF-8: nombres de video en cirilico o con acentos no rompen nada
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
# sin esto Python guarda lo que escribe y la ventana no muestra el progreso hasta el final
$env:PYTHONUNBUFFERED = "1"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$OutputEncoding = [System.Text.Encoding]::UTF8

# Cada paso con su fecha y hora, y lo que tardo el anterior (en el registro y en pantalla)
$script:InicioScript = Get-Date
$script:InicioPaso = $null
function Duracion($ts) { if ($ts.TotalHours -ge 1) { "{0} h {1:00} min" -f [int][math]::Floor($ts.TotalHours), $ts.Minutes } elseif ($ts.TotalMinutes -ge 1) { "{0} min {1:00} s" -f [int][math]::Floor($ts.TotalMinutes), $ts.Seconds } else { "{0} s" -f [int]$ts.TotalSeconds } }
function Fin-Paso { if ($script:InicioPaso) { Write-Host ("    (paso terminado en {0})" -f (Duracion ((Get-Date) - $script:InicioPaso))) -ForegroundColor DarkGray } }
function Paso($texto) {
    Fin-Paso
    $script:InicioPaso = Get-Date
    Write-Host ""; Write-Host ("==> [{0:yyyy-MM-dd HH:mm:ss}] $texto" -f $script:InicioPaso) -ForegroundColor Cyan
}
function Resumen-Tiempo {
    Fin-Paso; $script:InicioPaso = $null
    Write-Host ("Empezado {0:yyyy-MM-dd HH:mm:ss} - terminado {1:yyyy-MM-dd HH:mm:ss} - duracion total {2}" -f $script:InicioScript, (Get-Date), (Duracion ((Get-Date) - $script:InicioScript))) -ForegroundColor Cyan
}
function Ok($texto) { Write-Host $texto -ForegroundColor Green }
function Aviso($texto) { Write-Host $texto -ForegroundColor Yellow }
function Tiene($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refrescar-Path {
    # winget deja ffmpeg en WinGet\Links; uv en .local\bin
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User") + ";$HOME\.local\bin;" +
                "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        $ff = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
              Select-Object -First 1
        if ($ff) { $env:Path += ";" + $ff.DirectoryName }
    }
}
# Ejecuta un programa y para todo si falla (PowerShell no lo hace solo con programas externos)
# Su salida pasa por PowerShell para que quede en el registro (si no, el registro no dice por que fallo)
function Ejecutar {
    param([string]$Exe, [string[]]$Argumentos, [int[]]$CodigosOk = @(0))
    $ErrorActionPreference = "Continue"           # los avisos en stderr no son errores
    $env:UV_NO_PROGRESS = "1"
    & $Exe @Argumentos 2>&1 | ForEach-Object { "$_" } | Out-Host
    $code = $LASTEXITCODE
    if ($CodigosOk -notcontains $code) { throw "Fallo: $Exe $($Argumentos -join ' ') (codigo $code)" }
}
# Evita que el PC se suspenda mientras el script trabaja
function Sin-Suspender {
    Add-Type -Namespace Win32 -Name Power -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);
'@ -ErrorAction SilentlyContinue
    [Win32.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
}
function Comprobar-Instalacion {
    Refrescar-Path
    if (-not (Tiene uv) -or -not (Test-Path (Join-Path $RepoDir ".venv"))) {
        throw "Falta la instalacion. Ejecuta primero 1_instalar.bat"
    }
}

# Sube los registros del PC a la rama pc-logs del repositorio, para que Claude los lea sin que el
# usuario copie nada. Nunca para el script si falla (sin Git, sin red o sin permiso).
function Subir-Registros {
    # git escribe avisos en stderr: con "Stop", Windows PowerShell los convertiria en errores
    $ErrorActionPreference = "Continue"
    try {
        Refrescar-Path
        if (-not (Tiene git)) { return }
        $d = "$Base\registros"
        if (-not (Test-Path "$d\.git")) {
            New-Item -ItemType Directory -Force -Path $d | Out-Null
            git -C $d init -q 2>$null
            git -C $d remote add origin $RepoUrl 2>$null
        }
        git -C $d fetch -q origin pc-logs 2>$null
        if ($LASTEXITCODE -eq 0) { git -C $d checkout -q -B pc-logs FETCH_HEAD 2>$null }
        else { git -C $d checkout -q -B pc-logs 2>$null }
        Copy-Item "$Base\output\*.log" $d -Force -ErrorAction SilentlyContinue
        Copy-Item "$Base\output\revision_automatica.md" $d -Force -ErrorAction SilentlyContinue
        Estado-Ciclo
        Copy-Item "$Base\output\ciclo_vivo.txt", "$Base\output\ciclo_tarea.txt", "$Base\output\ciclo_arranque.txt" $d -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path "$d\partidos" | Out-Null
        # cada partido (y los de la prueba rapida, en output\_smoke): registro, etapas y errores;
        # de la prueba rapida tambien sus golpes (pocos), para revisar la calidad de lo medido
        $dirs = @(Get-ChildItem "$Base\output" -Directory -ErrorAction SilentlyContinue) +
                @(Get-ChildItem "$Base\output\_smoke" -Directory -ErrorAction SilentlyContinue)
        foreach ($m in $dirs) {
            $r = Join-Path $m.FullName "registro.log"
            if (Test-Path $r) { Copy-Item $r "$d\partidos\$($m.Name).log" -Force }
            $extra = @("manifest.json", "strokes_errores.json")
            if ($m.Name -like "smoke_*") { $extra += @("strokes.json", "candidates.json", "identity.json", "score.json", "court.json", "probe.json") }
            foreach ($j in $extra) {
                $f = Join-Path $m.FullName $j
                if (Test-Path $f) { Copy-Item $f "$d\partidos\$($m.Name)_$j" -Force }
            }
            # de la prueba rapida: las series fotograma a fotograma de sus golpes (unos 100 KB cada una)
            if ($m.Name -like "smoke_*" -and (Test-Path "$($m.FullName)\series")) {
                New-Item -ItemType Directory -Force -Path "$d\series" | Out-Null
                Remove-Item "$d\series\*" -Force -ErrorAction SilentlyContinue
                Copy-Item "$($m.FullName)\series\*.json" "$d\series" -Force -ErrorAction SilentlyContinue
            }
        }
        # pruebas aparte pedidas por Claude (output\_poc*: velocidad), con otro nombre para no pisar las de _smoke
        foreach ($p in @(Get-ChildItem "$Base\output" -Directory -Filter "_poc*" -ErrorAction SilentlyContinue)) {
            foreach ($m in @(Get-ChildItem $p.FullName -Directory -ErrorAction SilentlyContinue)) {
                foreach ($j in @("registro.log", "manifest.json", "strokes_errores.json", "strokes.json", "court.json", "score.json")) {
                    $f = Join-Path $m.FullName $j
                    if (Test-Path $f) { Copy-Item $f "$d\partidos\$($p.Name.TrimStart('_'))_$($m.Name)_$j" -Force }
                }
            }
            if (Test-Path "$($p.FullName)\auditoria\auditoria.md") { Copy-Item "$($p.FullName)\auditoria\auditoria.md" "$d\auditoria_$($p.Name.TrimStart('_')).md" -Force }
        }
        # imagenes de diagnostico de la prueba rapida (planos con la pista dibujada) y lo que lee el OCR
        if (Test-Path "$Base\output\_smoke\diag") {
            New-Item -ItemType Directory -Force -Path "$d\diag" | Out-Null
            Remove-Item "$d\diag\*" -Force -ErrorAction SilentlyContinue
            Copy-Item "$Base\output\_smoke\diag\*" "$d\diag" -Force -ErrorAction SilentlyContinue
        }
        # auditoria de requisitos y capturas del informe (de la prueba rapida y del analisis completo)
        foreach ($a in @(@("$Base\output\_smoke\auditoria", "prueba"), @("$Base\output\auditoria", "partidos"))) {
            if (Test-Path "$($a[0])\auditoria.md") {
                Copy-Item "$($a[0])\auditoria.md" "$d\auditoria_$($a[1]).md" -Force
                Copy-Item "$($a[0])\auditoria.json" "$d\auditoria_$($a[1]).json" -Force -ErrorAction SilentlyContinue
                $c = "$d\capturas_$($a[1])"
                New-Item -ItemType Directory -Force -Path $c | Out-Null
                Remove-Item "$c\*" -Force -ErrorAction SilentlyContinue
                Copy-Item "$($a[0])\capturas\*" $c -Force -ErrorAction SilentlyContinue
            }
        }
        # pantallas de la aplicacion (peticion "ventana"): su comprobacion y sus capturas
        if (Test-Path "$Base\output\capturas_app\ventana.md") {
            $c = "$d\capturas_app"
            New-Item -ItemType Directory -Force -Path $c | Out-Null
            Remove-Item "$c\*" -Force -ErrorAction SilentlyContinue
            Copy-Item "$Base\output\capturas_app\*.png", "$Base\output\capturas_app\ventana.*" $c -Force -ErrorAction SilentlyContinue
        }
        # videos de analisis de entrenadores (texto e imagenes pequenas), una sola vez
        if ((Test-Path "$Base\output\investigacion\indice.json") -and -not (Test-Path "$d\investigacion\indice.json")) {
            New-Item -ItemType Directory -Force -Path "$d\investigacion" | Out-Null
            Copy-Item "$Base\output\investigacion\*" "$d\investigacion" -Recurse -Force -ErrorAction SilentlyContinue
        }
        # videos de analisis elegidos por el usuario (peticiones "youtube"): cada carpeta, entera
        Get-ChildItem "$Base\output" -Directory -Filter "investigacion_*" -ErrorAction SilentlyContinue | ForEach-Object {
            New-Item -ItemType Directory -Force -Path "$d\$($_.Name)" | Out-Null
            Copy-Item "$($_.FullName)\*" "$d\$($_.Name)" -Recurse -Force -ErrorAction SilentlyContinue
        }
        # vista lateral de entrenamiento: el resumen y las imagenes del impacto (los videos no)
        if (Test-Path "$Base\output\entrenamiento\entrenamiento.json") {
            $e = "$d\entrenamiento"
            New-Item -ItemType Directory -Force -Path $e | Out-Null
            Remove-Item "$e\*" -Force -ErrorAction SilentlyContinue
            Copy-Item "$Base\output\entrenamiento\entrenamiento.json", "$Base\output\entrenamiento\videos.json" $e -Force -ErrorAction SilentlyContinue
            Get-ChildItem "$Base\output\entrenamiento\clips\*.jpg" -ErrorAction SilentlyContinue | Select-Object -First 40 |
                ForEach-Object { Copy-Item $_.FullName $e -Force }
        }
        if (Test-Path "$Base\output\progreso.json") { Copy-Item "$Base\output\progreso.json" "$d\progreso.json" -Force }
        if (Test-Path "$Base\output\_smoke\progreso.json") { Copy-Item "$Base\output\_smoke\progreso.json" "$d\progreso_prueba.json" -Force }
        foreach ($f in @("$Base\output\benchmark\results.json", "$Base\datasets\reports\f3set_validation.json", "$Base\datasets\reports\model_trials.json", "$Base\datasets\reports\model_trials.md")) {
            if (Test-Path $f) { Copy-Item $f "$d\$(Split-Path $f -Leaf)" -Force }
        }
        # cuanto ocupa cada carpeta de salida (MB), para vigilar el disco
        $tam = "$d\tamanos.txt"
        "fecha: $(Get-Date -Format s)" | Set-Content $tam
        foreach ($c in @(Get-ChildItem "$Base\output" -Directory -ErrorAction SilentlyContinue) + @(Get-ChildItem "$Base\output\_smoke" -Directory -ErrorAction SilentlyContinue)) {
            try {
                $mb = [math]::Round(((Get-ChildItem $c.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum) / 1MB, 1)
                "{0,10} MB  {1}" -f $mb, $c.FullName.Substring($Base.Length) | Add-Content $tam
            } catch {}
        }
        # equipo: lo necesario para entender la velocidad (sin datos personales)
        $eq = "$d\equipo.txt"
        "fecha: $(Get-Date -Format s)" | Set-Content $eq
        try { (Get-CimInstance Win32_Processor | Select-Object -First 1).Name | Add-Content $eq } catch {}
        try { (Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join "; " | Add-Content $eq } catch {}
        try { "RAM GB: " + [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB) | Add-Content $eq } catch {}
        try { "libre C: GB " + [math]::Round((Get-PSDrive C).Free / 1GB) | Add-Content $eq } catch {}
        git -C $d add -A 2>$null
        git -C $d -c user.name="PC tenis" -c user.email="pc@tenis.local" commit -q -m "registros $(Get-Date -Format s)" 2>$null
        git -C $d push -q origin pc-logs 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "Registro enviado a Claude (no hace falta copiar nada)." }
        else { Aviso "No se pudo enviar el registro a Claude (sin red o sin permiso en GitHub)." }
    } catch { Aviso "No se pudo enviar el registro a Claude: $_" }
}

# Trae la ultima version del codigo (con Git) antes de trabajar: el usuario solo hace doble clic.
# Las librerias se ajustan si cambiaron (rapido si no hay nada nuevo). Nunca para el script.
function Actualizar-Codigo {
    $ErrorActionPreference = "Continue"
    try {
        Refrescar-Path
        if ((Test-Path "$RepoDir\.git") -and (Tiene git)) {
            git -C $RepoDir pull --ff-only origin $Rama 2>&1 | ForEach-Object { "$_" } | Out-Host
            if ($LASTEXITCODE -ne 0) { Aviso "No se pudo actualizar el codigo; se usa la version que hay." }
            Registrar-Ciclo
            if (Tiene uv) {
                Push-Location $RepoDir
                uv sync --extra yolo --extra ocr --extra dev --extra validation --extra app 2>&1 | ForEach-Object { "$_" } | Out-Host
                # modelos nuevos que pida el codigo (p. ej. transnetv2.onnx): solo crea los que falten
                uv run python scripts/setup_models.py 2>&1 | ForEach-Object { "$_" } | Out-Host
                Pop-Location
            }
        }
    } catch { Aviso "No se pudo actualizar el codigo: $_" }
}

# El ciclo automatico (ciclo_automatico.ps1) queda programado en Windows cada 10 minutos, en segundo
# plano y solo con la sesion del usuario abierta: trae el codigo nuevo, ejecuta lo que haga falta,
# revisa el resultado y sube los registros. Se registra solo al usar cualquier boton; nunca para el script.
function Registrar-Ciclo {
    $ErrorActionPreference = "Continue"
    try {
        $nombre = "tenis-ciclo-automatico"
        # v4: todo se lanza con oculto.vbs (wscript): sin el terminal que aparecia y se cerraba solo
        $version = "ciclo v4"
        if (Test-Path "$Base\output\ciclo_desactivado.txt") { return }
        $vbs = Join-Path $RepoDir "scripts\windows\oculto.vbs"
        # 1) bucle en segundo plano que arranca con la sesion (carpeta Inicio): no depende del
        #    Programador de tareas; se pone en marcha ya si no lo esta
        $bucle = Join-Path $RepoDir "scripts\windows\ciclo_bucle.ps1"
        $inicio = [Environment]::GetFolderPath("Startup")
        if ($inicio) {
            "CreateObject(`"WScript.Shell`").Run `"wscript.exe //B `"`"$vbs`"`" `"`"$bucle`"`"`", 0, False" |
                Set-Content (Join-Path $inicio "tenis-ciclo.vbs") -Encoding ASCII
            Remove-Item (Join-Path $inicio "tenis-ciclo.cmd") -Force -ErrorAction SilentlyContinue
        }
        $vivo = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match "ciclo_bucle" }
        if (-not $vivo) {
            Start-Process wscript.exe -ArgumentList @("//B", "`"$vbs`"", "`"$bucle`"")
            Ok "Ciclo automatico en marcha (cada 10 minutos, en segundo plano; arranca solo al encender)."
        }
        # 2) ademas, la tarea de Windows (por si el bucle se cierra)
        $t = Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue
        if ($t -and $t.Description -like "*$version*") { return }
        $ps1 = Join-Path $RepoDir "scripts\windows\ciclo_automatico.ps1"
        $accion = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "//B `"$vbs`" `"$ps1`"" -WorkingDirectory $RepoDir
        # cada 10 minutos todo el dia, todos los dias (diario con repeticion de 1 dia: funciona en
        # cualquier Windows, sin depender de una duracion "indefinida"), y tambien al iniciar sesion
        $diario = New-ScheduledTaskTrigger -Daily -At "00:00"
        $diario.Repetition = (New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
        $alEntrar = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
        # Parallel: si el ciclo anterior sigue trabajando, el nuevo arranca, lo ve y sale sin error
        # (con IgnoreNew Windows lo rechazaba y lo marcaba como fallo, 0x800710E0, cada 10 minutos)
        $ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances Parallel -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 12)
        $quien = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger @($diario, $alEntrar) -Settings $ajustes -Principal $quien `
            -Description "Tenis ($version): trae el codigo nuevo, recalcula lo necesario, revisa y sube los registros" -Force | Out-Null
        Ok "Ciclo automatico programado: cada 10 minutos, en segundo plano (9_parar_ciclo_automatico.bat lo quita)."
    } catch { Aviso "No se pudo programar el ciclo automatico: $_" }
}

# Estado de la tarea del ciclo (ultima ejecucion, resultado, proxima): se sube con los registros para
# que Claude vea si Windows la lanza y como termina, sin que el usuario mire nada.
function Estado-Ciclo {
    $ErrorActionPreference = "Continue"
    try {
        $t = Get-ScheduledTask -TaskName "tenis-ciclo-automatico" -ErrorAction SilentlyContinue
        $f = "$Base\output\ciclo_tarea.txt"
        if (-not $t) { "tarea: no existe ($(Get-Date -Format s))" | Set-Content $f; return }
        $i = Get-ScheduledTaskInfo -TaskName "tenis-ciclo-automatico"
        @("fecha: $(Get-Date -Format s)", "estado: $($t.State)", "descripcion: $($t.Description)",
          "ultima ejecucion: $($i.LastRunTime)", "resultado (0 = bien, 267009 = en marcha, 267011 = nunca, 2147946720 = rechazada porque la anterior seguia trabajando): $($i.LastTaskResult)",
          "proxima: $($i.NextRunTime)", "perdidas: $($i.NumberOfMissedRuns)",
          "disparadores: $(($t.Triggers | ForEach-Object { $_.CimClass.CimClassName + ' ' + $_.Repetition.Interval }) -join '; ')",
          "accion: $($t.Actions[0].Execute) $($t.Actions[0].Arguments)") | Set-Content $f
    } catch {}
}

# Mientras un script largo trabaja, sube su registro cada 10 minutos: Claude ve el avance sin esperar
# al final. Devuelve el trabajo en segundo plano (pararlo con Stop-Job al terminar).
function Iniciar-Avisos {
    $comun = Join-Path $PSScriptRoot "comun.ps1"
    Start-Job -ArgumentList $comun -ScriptBlock {
        param($comun)
        . $comun
        while ($true) { Start-Sleep -Seconds 600; Subir-Registros | Out-Null }
    }
}
