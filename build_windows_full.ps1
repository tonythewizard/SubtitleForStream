#requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Esegui prima setup_windows.ps1.' }
& $python preload_models.py
if ($LASTEXITCODE -ne 0) { throw 'Download modelli fallito.' }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'build_windows.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Build completa fallita.' }
Write-Host 'Build con i modelli integrati nella cartella dist\SubtitleForStream completata.' -ForegroundColor Green
