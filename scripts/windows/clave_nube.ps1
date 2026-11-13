# N0 (13-11, peticion #273): guarda UNA VEZ en este PC la clave de Modal (la nube de la prueba) para que la cola
# suba los modelos y las compilaciones de F3Set (scripts/subir_nube.py). La clave se guarda en C:\tenis\secretos,
# nunca en el repositorio.
# 13-11 (tarde): el usuario pego un secreto sin su "as-" y el script lo rechazo sin decir por que. Ahora basta con pegar
# el comando entero que ensena Modal al crear el token (boton Copy): de ahi se sacan el ID y el secreto; si falta
# alguno se pide aparte; si algo no cuadra se dice como empieza y cuantos caracteres tiene (nunca la clave). La
# comprobacion de verdad es la de Modal: si la acepta, se guarda.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$dir = Join-Path $Base "secretos"
New-Item -ItemType Directory -Force $dir | Out-Null

function Sacar($texto, $prefijo) {
    $m = [regex]::Match("$texto", "$prefijo-[A-Za-z0-9]+")
    if ($m.Success) { return $m.Value }
    return ""
}
function Describir($texto) {
    $t = "$texto".Trim()
    if ($t.Length -eq 0) { return "no se pego nada" }
    $ini = $t.Substring(0, [Math]::Min(3, $t.Length))
    return "empieza por '$ini' y tiene $($t.Length) caracteres"
}
function Leer-Oculto($pregunta) {
    $s = Read-Host $pregunta -AsSecureString
    $p = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p) }
}

Write-Host ""
Write-Host "Clave de Modal para la prueba de la nube (se guarda solo en este PC)" -ForegroundColor Cyan
Write-Host "En modal.com/settings/tokens: + New token. En la ventana 'Token created' pulsa Copy (copia el comando entero)"
Write-Host "y pegalo aqui (boton derecho del raton en esta ventana pega) y pulsa Enter."
Write-Host ""
$entrada = (Read-Host "Pega el comando de Modal (o solo el Token ID, ak-...)").Trim()
$id = Sacar $entrada "ak"
$sec = Sacar $entrada "as"
if (-not $id) {
    Write-Host "No encuentro el Token ID (ak-...) en lo pegado: $(Describir $entrada)." -ForegroundColor Red
    exit 1
}
if (-not $sec) {
    $otro = Leer-Oculto "Pega el Token Secret (as-...; no se ve al pegarlo)"
    $sec = Sacar $otro "as"
    if (-not $sec) {
        Write-Host "No encuentro el secreto (as-...) en lo pegado: $(Describir $otro). Copia el comando entero con el boton Copy de Modal y repite." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Comprobando con Modal (ID $($id.Substring(0, [Math]::Min(6, $id.Length)))..., secreto de $($sec.Length) caracteres)..."
$ErrorActionPreference = "Continue"      # uv escribe su progreso por stderr: no es un error
$env:MODAL_TOKEN_ID = $id
$env:MODAL_TOKEN_SECRET = $sec
& uv tool run --from "modal>=1.0,<2" modal volume list 2>&1 | Out-Host
$ok = ($LASTEXITCODE -eq 0)
if ($ok) {
    $f = Join-Path $dir "modal.env"
    Set-Content -Path $f -Value @("MODAL_TOKEN_ID=$id", "MODAL_TOKEN_SECRET=$sec") -Encoding ASCII
    Write-Host "Clave correcta, guardada en $f. Ya no hay que hacer nada mas en este PC." -ForegroundColor Green
} else {
    Write-Host "Modal no acepta la clave: crea otro token, pulsa Copy y repite este doble clic. No se guarda nada." -ForegroundColor Red
}
# una marca para Claude en pc-logs (sin la clave): asi pone la subida en la cola sin que el usuario tenga que avisar
try {
    $cd = Join-Path $Base "output\capturas_diag"
    New-Item -ItemType Directory -Force $cd | Out-Null
    $marca = @{ fecha = (Get-Date -Format s); aceptada = $ok } | ConvertTo-Json
    Set-Content -Path (Join-Path $cd "nube_clave.json") -Value $marca -Encoding ASCII
} catch { Write-Host "No se pudo dejar la marca para Claude: $_" -ForegroundColor Yellow }
