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
    Ejecutar uv @("run", "python", "scripts/auto_catalog.py")

    Paso "2/5 Analisis de los partidos (horas; se puede cortar y relanzar)"
    Ejecutar uv @("run", "tennisbio", "run", "--all")
    Ejecutar uv @("run", "tennisbio", "status")

    Paso "3/5 Informes"
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "forehand", "--out", "$Base\output\informe_derecha")
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "backhand", "--out", "$Base\output\informe_reves")
    Ejecutar uv @("run", "tennisbio", "report", "--stroke", "overhead", "--out", "$Base\output\informe_saque")

    # la auditoria antes que cualquier video (27-10: la exportacion del reves y luego la de la derecha se quedaron
    # paradas y dejaron sin auditoria la referencia de los 4 partidos)
    Paso "4/5 Comprobacion automatica de requisitos (capturas del informe incluidas; se envia a Claude)"
    Ejecutar uv @("run", "tennisbio", "audit", "--stroke", "forehand")
    Paso "5/5 Videos por golpe, montajes por conclusion y resumen PDF"
    # 27-10: si un golpe no avanza en 10 min se corta y se anota cual (exportar_*\en_curso.txt) y donde estaba
    # cada hilo (exportar_*\pila.txt); los demas pasos siguen
    foreach ($e in @(@("forehand", "exportar_derecha"), @("backhand", "exportar_reves"), @("overhead", "exportar_saque"))) {
        $dir = "$Base\output\$($e[1])"
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Remove-Item "$dir\en_curso.txt" -Force -ErrorAction SilentlyContinue
        $so, $se = "$dir\exportar.out.txt", "$dir\exportar.err.txt"
        $pr = Start-Process uv -ArgumentList @("run", "tennisbio", "export", "--stroke", $e[0], "--out", $dir) `
            -NoNewWindow -PassThru -RedirectStandardOutput $so -RedirectStandardError $se
        $ultimo = Get-Date
        while (-not $pr.HasExited) {
            Start-Sleep -Seconds 30
            $f = Get-Item "$dir\en_curso.txt" -ErrorAction SilentlyContinue
            if ($f -and $f.LastWriteTime -gt $ultimo) { $ultimo = $f.LastWriteTime }
            if (((Get-Date) - $ultimo).TotalMinutes -gt 10) {
                & taskkill.exe /T /F /PID $pr.Id 2>&1 | Out-Null
                Write-Host "AVISO: exportacion de $($e[0]) cortada: 10 min sin avanzar en $(Get-Content "$dir\en_curso.txt" -ErrorAction SilentlyContinue)" -ForegroundColor Yellow
                Get-Content "$dir\pila.txt" -ErrorAction SilentlyContinue | Select-Object -Last 60 | ForEach-Object { Write-Host $_ }
                break
            }
        }
        Get-Content $so, $se -ErrorAction SilentlyContinue | Select-Object -Last 15 | ForEach-Object { Write-Host $_ }
    }
    Start-Process "$Base\output\informe_derecha\index.html"

    $dur = (Get-Date) - $inicio
    Write-Host ""
    Ok ("TERMINADO en {0:hh\:mm}. Informes en $Base\output\informe_*; videos, montajes y resumen.pdf en $Base\output\exportar_*" -f $dur)
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host "El registro se envia a Claude automaticamente. Relanzar este script continua donde se quedo." -ForegroundColor Red
} finally {
    Resumen-Tiempo
    if ($avisos) { Stop-Job $avisos -ErrorAction SilentlyContinue; Remove-Job $avisos -Force -ErrorAction SilentlyContinue }
    Stop-Transcript | Out-Null
    Subir-Registros
}
