# Conecta este PC con GitHub Actions (27-10): el PC pasa a ser el ejecutor del repositorio y cada peticion de
# Claude empieza al momento, con su registro en la pestana Actions. Una sola vez: pide el codigo que da GitHub
# (Settings > Actions > Runners > New self-hosted runner), lo configura y lo deja arrancando con la sesion.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\comun.ps1"
$Dir = "$Base\actions-runner"
$Url = "https://github.com/estebancobo-dot/tennis-biomechanics"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
# siempre la version mas reciente (27-10: una version fija de hace meses ya no la acepta GitHub)
Paso "Buscando la ultima version del ejecutor de GitHub Actions"
$rel = Invoke-RestMethod -UseBasicParsing -Uri "https://api.github.com/repos/actions/runner/releases/latest" -Headers @{ "User-Agent" = "tenis-pc" }
$Version = "$($rel.tag_name)".TrimStart("v")
if (-not $Version) { throw "No se pudo saber la ultima version del ejecutor (sin red?). Vuelve a probar en un rato." }
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$hecha = Get-Content "$Dir\version_tenis.txt" -ErrorAction SilentlyContinue
if (-not (Test-Path "$Dir\config.cmd") -or "$hecha".Trim() -ne $Version) {
    Paso "Descargando el ejecutor de GitHub Actions $Version"
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "Runner\.(Listener|Worker)" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-ChildItem $Dir -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $zip = "$Base\actions-runner.zip"
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/actions/runner/releases/download/v$Version/actions-runner-win-x64-$Version.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $Dir -Force
    Remove-Item $zip -Force
    $Version | Set-Content "$Dir\version_tenis.txt"
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
    if ($LASTEXITCODE -ne 0) { throw "GitHub no acepto el codigo (mira el mensaje de arriba; el codigo caduca en 1 hora): vuelve a hacer doble clic." }
} finally { Pop-Location }
# arranca con la sesion, sin ventana (como el ciclo automatico), y ahora mismo
$inicio = [Environment]::GetFolderPath("Startup")
"CreateObject(`"WScript.Shell`").Run `"`"`"$Dir\run.cmd`"`"`", 0, False" | Set-Content (Join-Path $inicio "tenis-github.vbs") -Encoding ASCII
$vivo = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "Runner.Listener" }
if (-not $vivo) { Start-Process wscript.exe -ArgumentList @("//B", "`"$(Join-Path $inicio 'tenis-github.vbs')`"") }
"$(Get-Date -Format s) ejecutor de GitHub Actions configurado ($Version)" | Add-Content "$Base\output\ciclo_arranque.txt"
Ok "Listo: el PC esta conectado con GitHub Actions y arranca solo al encender. No hace falta nada mas."
