# Recalcular medidas (unos minutos): vuelve a medir los golpes ya analizados en la prueba rapida o
# media con el codigo nuevo, sin cortar otro trozo ni repetir la pasada barata, y reutilizando la
# pose, la bola y la raqueta guardadas de cada ventana. Despues rehace la web, el PDF y la auditoria.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Log = "$Base\output\recalcular_medidas.log"
New-Item -ItemType Directory -Force -Path "$Base\output" | Out-Null
Start-Transcript -Path $Log | Out-Null
try {
    Sin-Suspender
    Comprobar-Instalacion
    Actualizar-Codigo
    Set-Location $RepoDir
    Paso "Medidas de los golpes ya analizados con el codigo nuevo, e informe, PDF y auditoria"
    Ejecutar uv @("run", "python", "scripts/recompute_measures.py")
    $informe = "$Base\output\_smoke\informe\index.html"
    if (Test-Path $informe) { Start-Process $informe }
    Ok "HECHO. El informe se ha abierto en el navegador."
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "El registro ($Log) se envia a Claude automaticamente." -ForegroundColor Red
} finally {
    Resumen-Tiempo
    Stop-Transcript | Out-Null
    Subir-Registros
}
