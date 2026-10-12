# Analisis completo: todos los videos de C:\tenis\videos, todas las etapas y los informes
# (derecha, reves, saque), los videos de cada golpe, los montajes y el resumen PDF. Se puede interrumpir y relanzar: continua donde lo dejo.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Log = "$Base\output\analisis_completo.log"
New-Item -ItemType Directory -Force -Path "$Base\output" | Out-Null
Start-Transcript -Path $Log -Append | Out-Null
try {
    Sin-Suspender
    Comprobar-Instalacion
    Actualizar-Codigo
    $avisos = Iniciar-Avisos
    Set-Location $RepoDir
    $inicio = Get-Date

    Paso "1/5 Catalogo de partidos (se anaden solos los videos nuevos)"
    Ejecutar uv @("run", "python", "scripts/auto_catalog.py", "--player", "rybakina")

    Paso "2/5 Analisis de los partidos (horas; se puede cortar y relanzar)"
    Ejecutar uv @("run", "tennisbio", "run", "--all")
    Ejecutar uv @("run", "tennisbio", "status")

    Paso "3/5 Informes"
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "forehand", "--out", "$Base\output\informe_derecha")
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "backhand", "--out", "$Base\output\informe_reves")
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "overhead", "--out", "$Base\output\informe_saque")

    Paso "4/5 Videos por golpe, montajes por conclusion y resumen PDF"
    Ejecutar uv @("run", "tennisbio", "export", "--stroke", "forehand", "--out", "$Base\output\exportar_derecha")
    Ejecutar uv @("run", "tennisbio", "export", "--stroke", "backhand", "--out", "$Base\output\exportar_reves")
    Ejecutar uv @("run", "tennisbio", "export", "--stroke", "overhead", "--out", "$Base\output\exportar_saque")
    Paso "5/5 Comprobacion automatica de requisitos (capturas del informe incluidas; se envia a Claude)"
    Ejecutar uv @("run", "tennisbio", "audit", "--stroke", "forehand")
    Start-Process "$Base\output\informe_derecha\index.html"

    $dur = (Get-Date) - $inicio
    Write-Host ""
    Ok ("TERMINADO en {0:hh\:mm}. Informes en $Base\output\informe_*; videos, montajes y resumen.pdf en $Base\output\exportar_*" -f $dur)
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "El registro se envia a Claude automaticamente. Relanzar este script continua donde se quedo." -ForegroundColor Red
} finally {
    if ($avisos) { Stop-Job $avisos -ErrorAction SilentlyContinue; Remove-Job $avisos -Force -ErrorAction SilentlyContinue }
    Stop-Transcript | Out-Null
    Subir-Registros
}
