# Builds the capture worker (the only program linked to Npcap) and puts it where Tauri bundles it next to the
# application. Run by `npm run worker`, which `tauri dev` and `tauri build` call first.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$workspace = Join-Path $root "src-tauri"
$importLibrary = Join-Path $workspace "crates\odd-capture-worker\npcap-lib\wpcap.lib"
$triple = "x86_64-pc-windows-msvc"
if (-not (Test-Path $importLibrary)) { & (Join-Path $PSScriptRoot "make-wpcap-lib.ps1") }

# Windows PowerShell 5.1 treats the progress cargo writes on its error output as fatal errors: only the exit code counts.
$ErrorActionPreference = "Continue"
Push-Location $workspace
try { cargo build --release -p odd-capture-worker; $exitCode = $LASTEXITCODE } finally { Pop-Location }
$ErrorActionPreference = "Stop"
if ($exitCode -ne 0) { throw "cargo build failed for the capture worker" }

$targetRoot = if ($env:CARGO_TARGET_DIR) { $env:CARGO_TARGET_DIR } else { Join-Path $workspace "target" }
$built = Join-Path $targetRoot "release\odd-capture-worker.exe"
$binaries = Join-Path $workspace "binaries"
New-Item -ItemType Directory -Force -Path $binaries | Out-Null
Copy-Item $built (Join-Path $binaries "odd-capture-worker-$triple.exe") -Force
Write-Host "capture worker ready in $binaries"
