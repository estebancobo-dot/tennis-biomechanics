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

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
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
        }
        # imagenes de diagnostico de la prueba rapida (planos con la pista dibujada) y lo que lee el OCR
        if (Test-Path "$Base\output\_smoke\diag") {
            New-Item -ItemType Directory -Force -Path "$d\diag" | Out-Null
            Remove-Item "$d\diag\*" -Force -ErrorAction SilentlyContinue
            Copy-Item "$Base\output\_smoke\diag\*" "$d\diag" -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path "$Base\output\progreso.json") { Copy-Item "$Base\output\progreso.json" "$d\progreso.json" -Force }
        if (Test-Path "$Base\output\_smoke\progreso.json") { Copy-Item "$Base\output\_smoke\progreso.json" "$d\progreso_prueba.json" -Force }
        foreach ($f in @("$Base\output\benchmark\results.json", "$Base\datasets\reports\f3set_validation.json")) {
            if (Test-Path $f) { Copy-Item $f "$d\$(Split-Path $f -Leaf)" -Force }
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
            if (Tiene uv) {
                Push-Location $RepoDir
                uv sync --extra yolo --extra ocr --extra dev --extra validation 2>&1 | ForEach-Object { "$_" } | Out-Host
                Pop-Location
            }
        }
    } catch { Aviso "No se pudo actualizar el codigo: $_" }
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
