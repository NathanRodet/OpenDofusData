# Makes wpcap.lib (the import library of Npcap) from the wpcap.dll that Npcap installed, with the Visual Studio tools.
# Needed once to build odd-capture-worker without downloading the Npcap SDK. Run in PowerShell:
#   .\scripts\make-wpcap-lib.ps1
# The result goes to src-tauri\crates\odd-capture-worker\npcap-lib (ignored by git), where the build script finds it.
$ErrorActionPreference = "Stop"
$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
$dll = "C:\Windows\System32\wpcap.dll"
if (-not (Test-Path $dll)) { $dll = "C:\Windows\System32\Npcap\wpcap.dll" }
if (-not (Test-Path $dll)) { throw "Npcap is not installed (wpcap.dll not found). Install it from https://npcap.com/" }
if (-not (Test-Path $vcvars)) { throw "Visual Studio Build Tools not found at $vcvars" }

$target = Join-Path $PSScriptRoot "..\src-tauri\crates\odd-capture-worker\npcap-lib"
New-Item -ItemType Directory -Force -Path $target | Out-Null
$exports = cmd /c "`"$vcvars`" >nul 2>&1 && dumpbin /exports `"$dll`""
$names = $exports | Select-String -Pattern '^\s+\d+\s+[0-9A-F]+\s+[0-9A-F]{8}\s+(\S+)' | ForEach-Object { $_.Matches[0].Groups[1].Value }
if (-not $names) { throw "no export found in $dll" }
$definition = Join-Path $target "wpcap.def"
Set-Content -Path $definition -Value (@("LIBRARY wpcap") + @("EXPORTS") + $names) -Encoding ascii
cmd /c "`"$vcvars`" >nul 2>&1 && lib /nologo /def:`"$definition`" /machine:x64 /out:`"$(Join-Path $target 'wpcap.lib')`""
if ($LASTEXITCODE -ne 0) { throw "lib.exe failed" }
Write-Host "wpcap.lib made in $target ($($names.Count) functions)"
