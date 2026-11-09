param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "test", "clean", "run", "help")]
    [string]$Command = "help",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunArguments = @()
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Assert-VenvExists {
    if (-not (Test-Path $VenvPython)) {
        throw "Venv introuvable. Lance d'abord: .\dev.ps1 setup"
    }
}

function Invoke-Setup {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Création du venv..."
        python -m venv $VenvDir
    }
    Write-Host "Installation des dépendances..."
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
    Write-Host "Prêt. Active le venv avec: .\.venv\Scripts\Activate.ps1"
}

function Invoke-Test {
    Assert-VenvExists
    & $VenvPython -m pytest $ProjectRoot
}

function Invoke-Run {
    Assert-VenvExists
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    & $VenvPython -m dofus_prices @RunArguments
    exit $LASTEXITCODE
}

function Invoke-Clean {
    if (Test-Path $VenvDir) {
        Remove-Item -Recurse -Force $VenvDir
        Write-Host "Venv supprimé."
    }
    Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Include "__pycache__", ".pytest_cache" |
        Remove-Item -Recurse -Force
}

function Show-Help {
    Write-Host "Usage: .\dev.ps1 <commande>"
    Write-Host "  setup  Crée le venv et installe requirements.txt"
    Write-Host "  test   Lance pytest dans le venv"
    Write-Host "  clean  Supprime le venv et les caches"
    Write-Host "  run    Lance dofus_prices (ex: .\dev.ps1 run discover --interface Ethernet)"
}

switch ($Command) {
    "setup" { Invoke-Setup }
    "test"  { Invoke-Test }
    "clean" { Invoke-Clean }
    "run"   { Invoke-Run }
    "help"  { Show-Help }
}
