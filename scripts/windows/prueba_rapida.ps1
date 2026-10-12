# Prueba rapida (40-70 min): velocidad del equipo + 4 minutos de un partido de principio a fin,
# con su informe + validacion automatica con puntos anotados de partidos publicos (F3Set).
# Usa el primer video de C:\tenis\videos.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Log = "$Base\output\prueba_rapida.log"
New-Item -ItemType Directory -Force -Path "$Base\output" | Out-Null
Start-Transcript -Path $Log | Out-Null
try {
    Sin-Suspender
    Comprobar-Instalacion
    Actualizar-Codigo
    Set-Location $RepoDir
    $video = Get-ChildItem "$Base\videos" -File -ErrorAction SilentlyContinue |
             Where-Object { $_.Extension -match '^\.(mp4|mkv|ts|mov|avi|m4v|webm)$' } |
             Sort-Object Length -Descending | Select-Object -First 1
    if (-not $video) { throw "No hay videos en $Base\videos. Copia al menos un partido." }
    Ok "Video: $($video.FullName)"

    Paso "1/4 Comprobacion del entorno"
    Ejecutar uv @("run", "python", "scripts/check_env.py", $video.FullName)

    Paso "2/4 Velocidad de este equipo (5 min)"
    Ejecutar uv @("run", "python", "scripts/benchmark.py", $video.FullName)

    Paso "3/4 Cuatro minutos de partido, todas las etapas e informe (15-30 min)"
    Ejecutar uv @("run", "python", "scripts/smoke_test.py", $video.FullName, "--minutes", "4")

    Paso "4/4 Validacion automatica: 30 puntos anotados de partidos de Rybakina (F3Set; 20-40 min)"
    try {
        Ejecutar uv @("run", "python", "scripts/validate_f3set.py", "--root", "$Base\datasets", "--clips", "30")
    } catch {
        Write-Host "La validacion no se pudo completar (descarga de YouTube?). No impide usar el programa." -ForegroundColor Yellow
    }

    $informe = "$Base\output\_smoke\informe\index.html"
    if (Test-Path $informe) { Start-Process $informe }
    Write-Host ""
    Ok "PRUEBA TERMINADA. El informe se ha abierto en el navegador."
    Ok "El registro se envia a Claude automaticamente."
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "El registro ($Log) se envia a Claude automaticamente." -ForegroundColor Red
} finally {
    Stop-Transcript | Out-Null
    Subir-Registros
}
