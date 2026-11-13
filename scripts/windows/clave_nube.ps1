# N0 (13-11, peticion #273): guarda UNA VEZ en este PC la clave de Modal (la nube de la prueba) para que la cola
# suba los modelos y las compilaciones de F3Set (scripts/subir_nube.py). La clave se guarda en C:\tenis\secretos,
# nunca en el repositorio. Pide dos datos: el Token ID y el Token Secret de modal.com/settings/tokens.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$dir = Join-Path $Base "secretos"
New-Item -ItemType Directory -Force $dir | Out-Null
Write-Host ""
Write-Host "Clave de Modal para la prueba de la nube (se guarda solo en este PC)" -ForegroundColor Cyan
Write-Host "La copias de la pagina modal.com/settings/tokens al crear el token (New Token)."
Write-Host ""
$id = (Read-Host "Pega el Token ID (empieza por ak-)").Trim()
$sec = Read-Host "Pega el Token Secret (empieza por as-)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr).Trim() }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if (-not $id.StartsWith("ak-") -or -not $plain.StartsWith("as-")) {
    Write-Host "No parece una clave de Modal (el ID empieza por ak- y el secreto por as-). No se guarda nada." -ForegroundColor Red
    exit 1
}
$f = Join-Path $dir "modal.env"
Set-Content -Path $f -Value @("MODAL_TOKEN_ID=$id", "MODAL_TOKEN_SECRET=$plain") -Encoding ASCII
Write-Host "Guardada en $f. Comprobando que Modal la acepta..."
$ErrorActionPreference = "Continue"      # uv escribe su progreso por stderr: no es un error
$env:MODAL_TOKEN_ID = $id
$env:MODAL_TOKEN_SECRET = $plain
& uv tool run --from "modal>=1.0,<2" modal volume list 2>&1 | Out-Host
$ok = ($LASTEXITCODE -eq 0)
if ($ok) {
    Write-Host "Clave correcta. Ya no hay que hacer nada mas en este PC." -ForegroundColor Green
} else {
    Write-Host "Modal no acepta la clave: vuelve a crear el token y repite este doble clic." -ForegroundColor Red
}
# una marca para Claude en pc-logs (sin la clave): asi pone la subida en la cola sin que el usuario tenga que avisar
try {
    $cd = Join-Path $Base "output\capturas_diag"
    New-Item -ItemType Directory -Force $cd | Out-Null
    $marca = @{ fecha = (Get-Date -Format s); aceptada = $ok } | ConvertTo-Json
    Set-Content -Path (Join-Path $cd "nube_clave.json") -Value $marca -Encoding ASCII
} catch { Write-Host "No se pudo dejar la marca para Claude: $_" -ForegroundColor Yellow }
