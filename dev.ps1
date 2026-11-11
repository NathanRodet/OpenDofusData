param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "test", "clean", "capture", "run", "build", "help")]
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
    & $VenvPython -m pip install -e $ProjectRoot
    Write-Host "Prêt. Active le venv avec: .\.venv\Scripts\Activate.ps1"
}

function Invoke-Test {
    Assert-VenvExists
    & $VenvPython -m pytest $ProjectRoot
}

function Invoke-Program {
    param([string[]]$ProgramArguments)
    Assert-VenvExists
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    & $VenvPython -m opendofusdata @ProgramArguments
    exit $LASTEXITCODE
}

function Invoke-Run {
    Invoke-Program $RunArguments
}

function Invoke-Capture {
    Invoke-Program (@("run") + $RunArguments)
}

function Invoke-Build {
    Assert-VenvExists
    $DistDir = Join-Path $ProjectRoot "dist"
    $BuildDir = Join-Path $ProjectRoot "build"
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"  # PyInstaller logs to stderr, which PowerShell 5.1 treats as an error
    & $VenvPython -m PyInstaller --noconfirm --clean --onefile --windowed --name OpenDofusData `
        --paths (Join-Path $ProjectRoot "src") --collect-data customtkinter `
        --distpath $DistDir --workpath (Join-Path $BuildDir "work") --specpath $BuildDir `
        (Join-Path $ProjectRoot "packaging\launcher.py")
    $ErrorActionPreference = $PreviousPreference
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller a échoué." }
    $Exe = Join-Path $DistDir "OpenDofusData.exe"
    $Hash = (Get-FileHash -Algorithm SHA256 $Exe).Hash.ToLower()
    "$Hash  OpenDofusData.exe" | Set-Content -Encoding ascii "$Exe.sha256"
    Write-Host "Prêt: $Exe (SHA-256 dans OpenDofusData.exe.sha256)"
}

function Invoke-Clean {
    if (Test-Path $VenvDir) {
        Remove-Item -Recurse -Force $VenvDir
        Write-Host "Venv supprimé."
    }
    foreach ($Folder in @("build", "dist")) {
        $Path = Join-Path $ProjectRoot $Folder
        if (Test-Path $Path) { Remove-Item -Recurse -Force $Path }
    }
    Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Include "__pycache__", ".pytest_cache" |
        Remove-Item -Recurse -Force
}

function Show-Help {
    Write-Host "Usage: .\dev.ps1 <commande>"
    Write-Host "  setup  Crée le venv et installe requirements.txt"
    Write-Host "  test   Lance pytest dans le venv"
    Write-Host "  clean  Supprime le venv et les caches"
    Write-Host "  capture Lance la capture des prix (ex: .\dev.ps1 capture --server MonServeur)"
    Write-Host "  build  Construit dist\OpenDofusData.exe (PyInstaller) et sa somme SHA-256"
    Write-Host "  run    Lance opendofusdata (ex: .\dev.ps1 run discover --interface Ethernet)"
}

switch ($Command) {
    "setup" { Invoke-Setup }
    "test"  { Invoke-Test }
    "clean" { Invoke-Clean }
    "capture" { Invoke-Capture }
    "run"   { Invoke-Run }
    "build" { Invoke-Build }
    "help"  { Show-Help }
}
