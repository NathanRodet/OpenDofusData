param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "test", "run", "new-secret", "help")]
    [string]$Command = "help",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArguments = @()
)

$ErrorActionPreference = "Stop"
$ServerRoot = $PSScriptRoot
$VenvDir = Join-Path $ServerRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Assert-VenvExists {
    if (-not (Test-Path $VenvPython)) {
        throw "Venv introuvable. Lance d'abord: .\dev.ps1 setup"
    }
}

function Invoke-Setup {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Création du venv du serveur..."
        python -m venv $VenvDir
    }
    # requirements-dev.lock pins the runtime and test packages with their hashes (requirements.lock pins the runtime ones only).
    & $VenvPython -m pip install --require-hashes -r (Join-Path $ServerRoot "requirements-dev.lock")
    Write-Host "Prêt. Génère un secret avec: .\dev.ps1 new-secret"
}

function Import-DotEnv {
    $EnvFile = Join-Path $ServerRoot ".env"
    if (-not (Test-Path $EnvFile)) { return }
    foreach ($Line in Get-Content $EnvFile -Encoding UTF8) {
        if ($Line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim('"', "'")
        }
    }
}

function Invoke-Server {
    param([string[]]$ModuleArguments)
    Assert-VenvExists
    $env:PYTHONPATH = $ServerRoot
    & $VenvPython @ModuleArguments
    exit $LASTEXITCODE
}

function Show-Help {
    Write-Host "Usage: .\dev.ps1 <commande>"
    Write-Host "  setup       Crée le venv et installe requirements-dev.lock (versions et hashes verrouillés, outils de test compris)"
    Write-Host "  test        Lance pytest dans le venv du serveur"
    Write-Host "  run         Lance le serveur sur 127.0.0.1:8000 (lit .env: KEY_SECRET, KEYSERVER_DB)"
    Write-Host "  new-secret  Génère le secret maître (KEY_SECRET pour le serveur, ADMIN_SECRET pour l'administrateur)"
}

switch ($Command) {
    "setup"      { Invoke-Setup }
    "test"       { Assert-VenvExists; Push-Location $ServerRoot; & $VenvPython -m pytest @ExtraArguments; Pop-Location }
    "run"        {
        Import-DotEnv
        if (-not $env:KEYSERVER_ALLOWED_HOSTS) { $env:KEYSERVER_ALLOWED_HOSTS = "127.0.0.1,localhost" }
        Invoke-Server (@("-m", "uvicorn", "keyserver.app:build_app", "--factory", "--host", "127.0.0.1",
                         "--port", "8000", "--no-access-log", "--no-server-header") + $ExtraArguments)
    }
    "new-secret" { Invoke-Server @("-m", "keyserver", "new-secret") }
    "help"       { Show-Help }
}
