# Solo el informe (1-2 min): rehace la web, el PDF y la auditoria con lo ya analizado en la prueba
# rapida o media, sin volver a analizar video. Para ver cada cambio de la web.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Log = "$Base\output\solo_informe.log"
New-Item -ItemType Directory -Force -Path "$Base\output" | Out-Null
Start-Transcript -Path $Log | Out-Null
try {
    Comprobar-Instalacion
    Actualizar-Codigo
    Set-Location $RepoDir
    Paso "Informe, PDF y auditoria con lo ya analizado (sin analizar video)"
    Ejecutar uv @("run", "python", "scripts/rebuild_report.py")
    $informe = "$Base\output\_smoke\informe\index.html"
    if (Test-Path $informe) { Start-Process $informe }
    Ok "HECHO. El informe se ha abierto en el navegador."
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
} finally {
    Resumen-Tiempo
    Stop-Transcript | Out-Null
    Subir-Registros
}
