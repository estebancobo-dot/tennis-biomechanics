# Analisis completo: todos los videos de C:\tenis\videos, todas las etapas y los informes
# (derecha, reves, saque). Se puede interrumpir y relanzar: continua donde lo dejo.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Log = "$Base\output\analisis_completo.log"
New-Item -ItemType Directory -Force -Path "$Base\output" | Out-Null
Start-Transcript -Path $Log -Append | Out-Null
try {
    Sin-Suspender
    Comprobar-Instalacion
    Set-Location $RepoDir
    $inicio = Get-Date

    Paso "1/3 Catalogo de partidos (se anaden solos los videos nuevos)"
    Ejecutar uv @("run", "python", "scripts/auto_catalog.py", "--player", "rybakina")

    Paso "2/3 Analisis de los partidos (horas; se puede cortar y relanzar)"
    Ejecutar uv @("run", "tennisbio", "run", "--all")
    Ejecutar uv @("run", "tennisbio", "status")

    Paso "3/3 Informes"
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "forehand", "--out", "$Base\output\informe_derecha")
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "backhand", "--out", "$Base\output\informe_reves")
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "overhead", "--out", "$Base\output\informe_saque")
    Start-Process "$Base\output\informe_derecha\index.html"

    $dur = (Get-Date) - $inicio
    Write-Host ""
    Ok ("TERMINADO en {0:hh\:mm}. Informes en $Base\output\informe_derecha, informe_reves, informe_saque" -f $dur)
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "Pasa a Claude el fichero $Log (relanzar este script continua donde se quedo)" -ForegroundColor Red
} finally {
    Stop-Transcript | Out-Null
}
