# Prueba rapida (40-70 min): velocidad del equipo + 4 minutos de un partido de principio a fin,
# con su informe + validacion automatica con puntos anotados de partidos publicos (F3Set).
# Usa el primer video de C:\tenis\videos. Con -Minutos 35 es la prueba media (2b_prueba_media.bat):
# suficientes golpes para que el informe describa su derecha y cada situacion.
# -Superficie (dura, tierra batida, hierba): solo si el video no esta en config\matches.yaml y su nombre
# no dice el torneo (si no, la superficie sale de ahi sola).
param([int]$Minutos = 4, [string]$Salida = "_smoke", [string]$Superficie = "")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Log = if ($Salida -ne "_smoke") { "$Base\output\prueba$Salida.log" } elseif ($Minutos -gt 4) { "$Base\output\prueba_media.log" } else { "$Base\output\prueba_rapida.log" }
New-Item -ItemType Directory -Force -Path "$Base\output" | Out-Null
Start-Transcript -Path $Log | Out-Null
try {
    Sin-Suspender
    Comprobar-Instalacion
    Actualizar-Codigo
    $avisos = Iniciar-Avisos
    Set-Location $RepoDir
    $video = Get-ChildItem "$Base\videos" -File -ErrorAction SilentlyContinue |
             Where-Object { $_.Extension -match '^\.(mp4|mkv|ts|mov|avi|m4v|webm)$' } |
             Sort-Object Length -Descending | Select-Object -First 1
    if (-not $video) { throw "No hay videos en $Base\videos. Copia al menos un partido." }
    Ok "Video: $($video.FullName)"

    Paso "1/4 Comprobacion del entorno"
    Ejecutar uv @("run", "python", "scripts/check_env.py", $video.FullName)

    # la velocidad del equipo y la validacion con F3Set solo se miden la primera vez (ya enviadas a
    # Claude); para repetirlas, borrar output\benchmark o datasets\reports
    Paso "2/4 Velocidad de este equipo (5 min, solo la primera vez)"
    if (Test-Path "$Base\output\benchmark\results.json") { Ok "ya medida" }
    else { Ejecutar uv @("run", "python", "scripts/benchmark.py", $video.FullName) }

    # vista lateral: videos de entrenamiento de la jugadora en YouTube (apartado aparte y marcado del
    # informe, nunca mezclado con los partidos). Incremental: cada video se baja y analiza una vez;
    # la prueba media amplia a mas videos y mas segundos de cada uno.
    $pv = if ($Minutos -gt 4) { @("--max-videos", "8", "--max-seconds", "300") } else { @("--max-videos", "2", "--max-seconds", "90") }
    Paso "Vista lateral: videos de entrenamiento de la jugadora (YouTube; solo lo que falte)"
    try { Ejecutar uv (@("run", "python", "scripts/practice_videos.py", "--out", "$Base\output\entrenamiento") + $pv) }
    catch { Write-Host "No se pudieron bajar o analizar (no impide usar el programa)." -ForegroundColor Yellow }

    Paso ("3/4 {0} minutos de partido, todas las etapas e informe ({1})" -f $Minutos, $(if ($Minutos -gt 4) { "unos 60 min" } else { "15-30 min" }))
    $sup = if ($Superficie) { @("--surface", $Superficie) } else { @() }
    Ejecutar uv (@("run", "python", "scripts/smoke_test.py", $video.FullName, "--minutes", "$Minutos", "--out-name", $Salida) + $sup)

    Paso "4/4 Validacion automatica: puntos anotados de partidos de Rybakina (F3Set; 20-40 min, solo la primera vez)"
    if (Test-Path "$Base\datasets\reports\f3set_validation.json") { Ok "ya hecha" }
    else {
        try {
            Ejecutar uv @("run", "python", "scripts/validate_f3set.py", "--root", "$Base\datasets", "--clips", "30")
        } catch {
            Write-Host "La validacion no se pudo completar (descarga de YouTube?). No impide usar el programa." -ForegroundColor Yellow
        }
    }

    # una sola vez: videos de analisis de entrenadores (solo texto e imagenes pequenas) para que Claude
    # aprenda como analizan y explican una derecha; nunca se usan como datos de la jugadora
    Paso "Extra: videos de analisis de entrenadores en YouTube (10-20 min, solo la primera vez)"
    if (Test-Path "$Base\output\investigacion\indice.json") { Ok "ya hecho" }
    else {
        try { Ejecutar uv @("run", "python", "scripts/youtube_research.py", "--out", "$Base\output\investigacion") }
        catch { Write-Host "No se pudieron bajar (no impide usar el programa)." -ForegroundColor Yellow }
    }

    $informe = "$Base\output\$Salida\informe\index.html"
    if (Test-Path $informe) { Start-Process $informe }
    Write-Host ""
    Ok "PRUEBA TERMINADA. El informe se ha abierto en el navegador."
    Ok "El registro se envia a Claude automaticamente."
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "El registro ($Log) se envia a Claude automaticamente." -ForegroundColor Red
} finally {
    Resumen-Tiempo
    if ($avisos) { Stop-Job $avisos -ErrorAction SilentlyContinue; Remove-Job $avisos -Force -ErrorAction SilentlyContinue }
    Stop-Transcript | Out-Null
    Subir-Registros
}
