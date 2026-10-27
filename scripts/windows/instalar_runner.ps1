# Conecta este PC con GitHub Actions (27-10): el PC pasa a ser el ejecutor del repositorio y cada peticion de
# Claude empieza al momento, con su registro en la pestana Actions. Una sola vez: pide el codigo que da GitHub
# (Settings > Actions > Runners > New self-hosted runner), lo configura y lo deja arrancando con la sesion.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Version = "2.322.0"
$Dir = "$Base\actions-runner"
$Url = "https://github.com/estebancobo-dot/tennis-biomechanics"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
if (-not (Test-Path "$Dir\config.cmd")) {
    Paso "Descargando el ejecutor de GitHub Actions $Version"
    $zip = "$Dir\runner.zip"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/actions/runner/releases/download/v$Version/actions-runner-win-x64-$Version.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $Dir -Force
    Remove-Item $zip -Force
}
Paso "Codigo de GitHub"
Write-Host "Se abre la pagina de GitHub. En el recuadro 'Configure', copia el codigo que va despues de --token" -ForegroundColor Cyan
Write-Host "(una tira de letras y numeros) y pegalo aqui." -ForegroundColor Cyan
Start-Process "$Url/settings/actions/runners/new?arch=x64&os=win"
$token = (Read-Host "Codigo").Trim()
if (-not $token) { throw "Sin codigo: vuelve a hacer doble clic cuando lo tengas." }
Paso "Configurando el ejecutor"
Push-Location $Dir
try {
    & .\config.cmd --unattended --url $Url --token $token --name "tenis-pc" --labels "tenis-pc" --work "_work" --replace
    if ($LASTEXITCODE -ne 0) { throw "GitHub no acepto el codigo (caduca en 1 hora): pide otro y vuelve a probar." }
} finally { Pop-Location }
# arranca con la sesion, sin ventana (como el ciclo automatico), y ahora mismo
$inicio = [Environment]::GetFolderPath("Startup")
"CreateObject(`"WScript.Shell`").Run `"`"`"$Dir\run.cmd`"`"`", 0, False" | Set-Content (Join-Path $inicio "tenis-github.vbs") -Encoding ASCII
$vivo = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "Runner.Listener" }
if (-not $vivo) { Start-Process wscript.exe -ArgumentList @("//B", "`"$(Join-Path $inicio 'tenis-github.vbs')`"") }
"$(Get-Date -Format s) ejecutor de GitHub Actions configurado ($Version)" | Add-Content "$Base\output\ciclo_arranque.txt"
Ok "Listo: el PC esta conectado con GitHub Actions y arranca solo al encender. No hace falta nada mas."
