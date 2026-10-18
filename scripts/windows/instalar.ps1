# Instala todo lo necesario. Se puede repetir: solo instala lo que falta.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
New-Item -ItemType Directory -Force -Path "$Base\videos", "$Base\output" | Out-Null
$Log = "$Base\output\instalacion.log"
Start-Transcript -Path $Log -Append | Out-Null
try {
    Sin-Suspender
    if (-not (Tiene winget)) { throw "Falta winget (App Installer). Instalalo desde Microsoft Store y repite." }

    Paso "1/7 Actualizar el codigo"
    Ok "se actualiza con 1_instalar.bat (con Git si el proyecto esta clonado; si no, zip de GitHub)"

    Paso "2/7 ffmpeg (lectura de video y audio)"
    Refrescar-Path
    if (Tiene ffmpeg) { Ok "ya estaba" } else {
        # -1978335189 / -1978335212: ya instalado o sin actualizacion (winget lo trata como error)
        Ejecutar winget @("install", "--id", "Gyan.FFmpeg", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements") @(0, -1978335189, -1978335212)
        Refrescar-Path
        if (-not (Tiene ffmpeg)) { Aviso "ffmpeg instalado; si el paso 7 falla, cierra esta ventana y repite 1_instalar.bat" }
    }

    Paso "3/7 uv (gestor de Python)"
    if (Tiene uv) { Ok "ya estaba" } else {
        powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        Refrescar-Path
        if (-not (Tiene uv)) { throw "No se pudo instalar uv" }
    }

    Paso "4/7 Codigo del proyecto"
    if (-not (Test-Path (Join-Path $RepoDir "pyproject.toml"))) {
        throw "Este script debe estar dentro del proyecto. Usa el comando de arranque (bootstrap.ps1)."
    }
    Set-Location $RepoDir
    Ok "proyecto en $RepoDir"

    Paso "5/7 Python 3.11 y librerias (10-15 min la primera vez)"
    Ejecutar uv @("python", "install", "3.11")
    Ejecutar uv @("sync", "--extra", "yolo", "--extra", "ocr", "--extra", "dev", "--extra", "validation", "--extra", "app")

    Paso "6/7 Configuracion y modelos (~1 GB la primera vez)"
    $local = Join-Path $RepoDir "config\local.yaml"
    if (-not (Test-Path $local)) {
        "paths:`r`n  videos: '$Base\videos'`r`n  output: '$Base\output'`r`n" | Set-Content -Encoding UTF8 $local
    }
    Ejecutar uv @("run", "python", "scripts/setup_models.py")
    # el acceso directo "Tennisbio" en el escritorio: doble clic abre la ventana y la cola arranca sola
    Ejecutar uv @("run", "--extra", "app", "tennisbio", "app", "acceso")

    Paso "7/7 Comprobacion"
    Ejecutar uv @("run", "python", "scripts/check_env.py")
    # las pruebas no bloquean la instalacion: su resultado se guarda y llega a Claude
    $ErrorActionPreference = "Continue"
    $salida = uv run pytest -q -p no:cacheprovider 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $salida | Out-Host
    $salida | Out-File -FilePath "$Base\output\pruebas.log" -Encoding utf8      # Tee-Object escribe UTF-16
    $global:LASTEXITCODE = $code
    if ($LASTEXITCODE -ne 0) { Aviso "Alguna prueba automatica fallo (detalle en pruebas.log, ya enviado a Claude). Se puede seguir." }
    $ErrorActionPreference = "Stop"

    Write-Host ""
    Ok "TODO LISTO."
    Ok "Abre Tennisbio con el acceso directo del escritorio y anade los partidos desde la ventana."
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "El registro ($Log) se envia a Claude automaticamente." -ForegroundColor Red
} finally {
    Resumen-Tiempo
    Stop-Transcript | Out-Null
    Subir-Registros
}
