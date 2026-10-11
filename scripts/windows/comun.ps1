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
