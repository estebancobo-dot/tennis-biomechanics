# Uso de recursos del PC mientras hay un analisis en marcha (26-10): cada 15 s, CPU (total, python, ffmpeg),
# RAM (usada, python), iGPU (por tipo de motor: 3D, Compute, VideoDecode) y disco, con la etapa y el partido de
# output\progreso.json. Escribe output\recursos\recursos_<fecha>.csv; termina sola cuando ya no hay analisis.
# La arranca el ciclo automatico (una sola a la vez). Clases CIM, no contadores: sus nombres no se traducen.
param([int]$Cada = 15)
$ErrorActionPreference = "SilentlyContinue"
. (Join-Path $PSScriptRoot "comun.ps1")
$Out = "$Base\output"
$dir = "$Out\recursos"
New-Item -ItemType Directory -Force $dir | Out-Null
$csv = Join-Path $dir ("recursos_" + (Get-Date -Format "yyyy-MM-dd_HHmm") + ".csv")
"hora,partido,etapa,cpu_total,cpu_python,cpu_ffmpeg,ram_usada_gb,ram_total_gb,ram_python_gb,gpu_3d,gpu_compute,gpu_decode,disco" |
    Set-Content $csv -Encoding ASCII
$nucleos = [int](Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
if ($nucleos -lt 1) { $nucleos = 1 }
$patron = "prueba_rapida|analisis_completo|recalcular_medidas|solo_informe|ciclo_automatico|instalar"

function Hay-Analisis {
    @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -match $patron }).Count -gt 0
}

function Num($v) { if ($null -eq $v) { return "" } ; return ([double]$v).ToString("0.0", [Globalization.CultureInfo]::InvariantCulture) }

while (Hay-Analisis) {
    $hora = Get-Date -Format s
    $partido, $etapa = "", ""
    try {
        $p = Get-Content "$Out\progreso.json" -Raw | ConvertFrom-Json
        $partido, $etapa = "$($p.partido)", "$($p.etapa)"
    } catch {}
    $cpu = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'").PercentProcessorTime
    $procs = @(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object { $_.Name -match '^(python|ffmpeg)(#\d+)?$' })
    $py = @($procs | Where-Object { $_.Name -like "python*" })
    $ff = @($procs | Where-Object { $_.Name -like "ffmpeg*" })
    $cpuPy = (($py | Measure-Object PercentProcessorTime -Sum).Sum) / $nucleos
    $cpuFf = (($ff | Measure-Object PercentProcessorTime -Sum).Sum) / $nucleos
    $ramPy = (($py | Measure-Object WorkingSetPrivate -Sum).Sum) / 1GB
    $os = Get-CimInstance Win32_OperatingSystem
    $ramTot = $os.TotalVisibleMemorySize / 1MB
    $ramUsada = ($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB
    $g3d, $gco, $gde = 0.0, 0.0, 0.0
    foreach ($e in @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine)) {
        $u = [double]$e.UtilizationPercentage
        if ($e.Name -match 'engtype_3D$') { $g3d += $u }
        elseif ($e.Name -match 'engtype_Compute') { $gco += $u }
        elseif ($e.Name -match 'engtype_VideoDecode') { $gde += $u }
    }
    $disco = (Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name='_Total'").PercentDiskTime
    $linea = @($hora, $partido, $etapa, (Num $cpu), (Num $cpuPy), (Num $cpuFf), (Num $ramUsada), (Num $ramTot), (Num $ramPy),
               (Num ([math]::Min(100, $g3d))), (Num ([math]::Min(100, $gco))), (Num ([math]::Min(100, $gde))), (Num ([math]::Min(100, $disco)))) -join ","
    $linea | Add-Content $csv -Encoding ASCII
    Start-Sleep -Seconds $Cada
}
