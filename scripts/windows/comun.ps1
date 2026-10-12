# Funciones comunes de los scripts de Windows (se cargan con ". comun.ps1").
$Base = "C:\tenis"
$RepoDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)       # scripts\windows -> repo
$RepoUrl = "https://github.com/estebancobo-dot/tennis-biomechanics.git"
$Rama = "claude/tennis-biomech-setup-jggqb0"

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Ok($texto) { Write-Host $texto -ForegroundColor Green }
function Aviso($texto) { Write-Host $texto -ForegroundColor Yellow }
function Tiene($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refrescar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User") + ";$HOME\.local\bin"
}
# Ejecuta un programa y para todo si falla (PowerShell no lo hace solo con programas externos)
function Ejecutar {
    param([string]$Exe, [string[]]$Argumentos)
    & $Exe @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Fallo: $Exe $($Argumentos -join ' ') (codigo $LASTEXITCODE)" }
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
        Get-ChildItem "$Base\output" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $r = Join-Path $_.FullName "registro.log"
            if (Test-Path $r) { Copy-Item $r "$d\partidos\$($_.Name).log" -Force }
            foreach ($j in @("manifest.json", "strokes_errores.json")) {
                $f = Join-Path $_.FullName $j
                if (Test-Path $f) { Copy-Item $f "$d\partidos\$($_.Name)_$j" -Force }
            }
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
