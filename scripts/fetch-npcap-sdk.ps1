# Gets wpcap.lib from the Npcap SDK (a build-time download, not redistributed) for machines without Npcap, like the
# build servers. The archive is checked against a pinned SHA-256. Run in PowerShell:
#   .\scripts\fetch-npcap-sdk.ps1
$ErrorActionPreference = "Stop"
$version = "1.17"
$expected = "ab7e1a6cb8d07427e0071ec11be380bd9d2bb19ae6ab3f5ede0698c301638258"
$archive = Join-Path ([IO.Path]::GetTempPath()) "npcap-sdk-$version.zip"
Invoke-WebRequest -Uri "https://npcap.com/dist/npcap-sdk-$version.zip" -OutFile $archive
$actual = (Get-FileHash -Algorithm SHA256 $archive).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "the Npcap SDK does not match its pinned SHA-256 ($actual)" }

$target = Join-Path $PSScriptRoot "..\src-tauri\crates\odd-capture-worker\npcap-lib"
$extracted = Join-Path ([IO.Path]::GetTempPath()) "npcap-sdk-$version"
if (Test-Path $extracted) { Remove-Item -Recurse -Force $extracted }
Expand-Archive -Path $archive -DestinationPath $extracted
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item (Join-Path $extracted "Lib\x64\wpcap.lib") (Join-Path $target "wpcap.lib") -Force
Write-Host "wpcap.lib copied to $target"
