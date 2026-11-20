# Aplicacion nueva (P0.5e, 15-11): la interfaz nueva en una ventana del PC. Su gestion va a la cola de la nube: sube el
# video al volumen de Modal y deja alli el clic, la aprobacion, la pausa... como peticiones. El PC no analiza nada.
# Usa la clave de Modal que guardo 5_conectar_nube.bat; sin ella la ventana se abre igual y cada boton lo dice.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Log = "$Base\output\aplicacion_nueva.log"
New-Item -ItemType Directory -Force -Path "$Base\output" | Out-Null
Start-Transcript -Path $Log | Out-Null
try {
    Comprobar-Instalacion
    Actualizar-Codigo
    Set-Location $RepoDir
    Paso "Aplicacion nueva: la ventana, con la gestion conectada a la nube (cierra la ventana para terminar)"
    Ejecutar uv @("run", "--extra", "app", "--with", "modal>=1.0,<2", "python", "scripts/aplicacion_nueva.py")
    Ok "HECHO. Ventana cerrada."
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
} finally {
    Resumen-Tiempo
    Stop-Transcript | Out-Null
    Subir-Registros
}
