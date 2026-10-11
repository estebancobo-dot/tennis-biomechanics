# Instala todo lo necesario. Se puede repetir: solo instala lo que falta.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
New-Item -ItemType Directory -Force -Path "$Base\videos", "$Base\output" | Out-Null
$Log = "$Base\output\instalacion.log"
Start-Transcript -Path $Log -Append | Out-Null
try {
    Sin-Suspender
    if (-not (Tiene winget)) { throw "Falta winget (App Installer). Instalalo desde Microsoft Store y repite." }

    Paso "1/7 Actualizar el codigo (sin Git: zip de GitHub)"
    Ok "se actualiza con 1_instalar.bat / bootstrap; Git no hace falta"

    Paso "2/7 ffmpeg (lectura de video y audio)"
    if (Tiene ffmpeg) { Ok "ya estaba" } else {
        Ejecutar winget @("install", "--id", "Gyan.FFmpeg", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements")
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
    Ejecutar uv @("sync", "--extra", "yolo", "--extra", "ocr", "--extra", "dev")

    Paso "6/7 Configuracion y modelos (~1 GB la primera vez)"
    $local = Join-Path $RepoDir "config\local.yaml"
    if (-not (Test-Path $local)) {
        "paths:`r`n  videos: '$Base\videos'`r`n  output: '$Base\output'`r`n" | Set-Content -Encoding UTF8 $local
    }
    Ejecutar uv @("run", "python", "scripts/setup_models.py")

    Paso "7/7 Comprobacion"
    Ejecutar uv @("run", "python", "scripts/check_env.py")
    Ejecutar uv @("run", "pytest", "-q")

    Write-Host ""
    Ok "TODO LISTO."
    Ok "Copia los partidos a $Base\videos y ejecuta 2_prueba_rapida.bat"
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "Pasa a Claude el fichero $Log" -ForegroundColor Red
} finally {
    Stop-Transcript | Out-Null
}
