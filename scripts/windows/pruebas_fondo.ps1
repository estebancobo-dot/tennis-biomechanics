# Las pruebas automaticas del codigo en este PC, en segundo plano y por debajo de lo normal (03-11): cada codigo
# nuevo se comprueba en la maquina real (Windows, iGPU, rutas), no solo en la nube. Lo lanza ciclo_automatico.ps1;
# el resultado queda en output\pruebas.log (se sube con los registros) y la auditoria lo lee. Una sola a la vez;
# si tarda mas de 40 min se corta y se dice.
. "$PSScriptRoot\comun.ps1"
try { (Get-Process -Id $PID).PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal } catch {}
$m = New-Object System.Threading.Mutex($false, "Global\tenis-pruebas")
if (-not $m.WaitOne(0)) { exit 0 }
$ErrorActionPreference = "Continue"
Refrescar-Path
$log = "$Base\output\pruebas.log"
$tmp = "$Base\output\pruebas_en_curso.txt"
$commit = "$(git -C $RepoDir rev-parse --short HEAD 2>$null)".Trim()
$t0 = Get-Date
# 11-11 (R1 de la revision de la Base): las pruebas apuntan que comprobaciones de la auditoria hacen fallar; la auditoria
# compara (tennisbio.check_coverage, "Comprobaciones que saben fallar")
$rec = "$Base\output\comprobaciones_pruebas"
Remove-Item "$rec\rec_*.json" -Force -ErrorAction SilentlyContinue
$env:TENNISBIO_REC_CHECKS = $rec
# pruebas.xml: el resultado de cada prueba con su nombre, para que la auditoria enlace cada peticion con las suyas
$p = Start-Process uv -ArgumentList @("run", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml", "`"$Base\output\pruebas.xml`"") -WorkingDirectory $RepoDir `
    -NoNewWindow -PassThru -RedirectStandardOutput $tmp -RedirectStandardError "$tmp.err"
$null = $p.Handle                     # without it Windows PowerShell gives no ExitCode for a -PassThru process
try { $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal } catch {}
$fin = $p.WaitForExit(40 * 60 * 1000)
if (-not $fin) { & taskkill.exe /T /F /PID $p.Id 2>&1 | Out-Null }
$codigo = if ($fin) { $p.ExitCode } else { "cortado a los 40 min" }
$cab = @("commit: $commit", "inicio: $($t0.ToString('s'))", "fin: $(Get-Date -Format s)", "codigo: $codigo")
$cuerpo = @(Get-Content $tmp -ErrorAction SilentlyContinue) + @(Get-Content "$tmp.err" -ErrorAction SilentlyContinue | Select-Object -Last 40)
($cab + $cuerpo) | Out-File -FilePath $log -Encoding utf8
Remove-Item $tmp, "$tmp.err" -Force -ErrorAction SilentlyContinue
$m.ReleaseMutex()
