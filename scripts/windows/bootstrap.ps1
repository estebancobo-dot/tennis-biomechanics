# Arranque sin Git: descarga el proyecto (zip de GitHub) en C:\tenis\tennis-biomech, conserva la
# configuracion, los modelos y el entorno si ya existian, y lanza la instalacion.
# Uso (una sola linea en PowerShell):
#   irm https://raw.githubusercontent.com/estebancobo-dot/tennis-biomechanics/claude/tennis-biomech-setup-jggqb0/scripts/windows/bootstrap.ps1 | iex
$ErrorActionPreference = "Stop"
$Base = "C:\tenis"
$Dest = "$Base\tennis-biomech"
$Rama = "claude/tennis-biomech-setup-jggqb0"
$Zip = "https://codeload.github.com/estebancobo-dot/tennis-biomechanics/zip/refs/heads/$Rama"
New-Item -ItemType Directory -Force -Path $Base, "$Base\videos", "$Base\output" | Out-Null
$tmp = Join-Path $env:TEMP ("tennisbio_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Write-Host "==> Descargando el proyecto..." -ForegroundColor Cyan
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $Zip -OutFile "$tmp\repo.zip" -UseBasicParsing
Expand-Archive -Path "$tmp\repo.zip" -DestinationPath $tmp -Force
$src = Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like "tennis-biomechanics-*" } | Select-Object -First 1
if (-not $src) { throw "El zip no tiene el formato esperado" }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
# copiar el codigo nuevo sin tocar lo local (configuracion, catalogo, modelos, entorno de Python)
$keep = @("config\local.yaml", "config\matches.yaml")
$saved = @{}
foreach ($k in $keep) { $p = Join-Path $Dest $k; if (Test-Path $p) { $saved[$k] = Get-Content -Raw $p } }
robocopy $src.FullName $Dest /E /XD ".venv" "models" /NFL /NDL /NJH /NJS /NP | Out-Null
foreach ($k in $saved.Keys) { Set-Content -Path (Join-Path $Dest $k) -Value $saved[$k] -NoNewline }
Remove-Item -Recurse -Force $tmp
Write-Host "==> Proyecto en $Dest" -ForegroundColor Green
& powershell -NoProfile -ExecutionPolicy Bypass -File "$Dest\scripts\windows\instalar.ps1"
