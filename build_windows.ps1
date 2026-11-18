#requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Esegui setup_windows.ps1 prima di compilare.' }
& $python -c 'import PyInstaller'
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install 'pyinstaller>=6.10'
    if ($LASTEXITCODE -ne 0) { throw 'Impossibile installare PyInstaller.' }
}
& $python -m tools.build_icon
if ($LASTEXITCODE -ne 0) { throw 'Generazione icona fallita.' }
$pack = @('--noconfirm','--clean','--onedir','--windowed',
          '--name','SubtitleForStream',
          '--icon','assets/SubtitleForStream.ico',
          '--add-data','assets/SubtitleForStream-Mark.svg;assets',
          '--add-data','assets/SubtitleForStream-Spectrum.svg;assets',
          '--hidden-import','PySide6.QtSvg',
          '--collect-all','faster_whisper',
          '--collect-all','ctranslate2',
          '--collect-all','proctap',
          '--add-data','app/overlay.html;app',
          '--add-data','app/censor_presets;app/censor_presets',
          '--add-data','app/ui_strings.txt;app',
          '--add-data','VERSION;.',
          '--add-data','LICENSE;.',
          '--add-data','UPDATE_REPOSITORY;.',
          'launch.py')
& $python -c 'import llama_cpp'
if ($LASTEXITCODE -eq 0) {
    $pack = @('--collect-all','llama_cpp') + $pack
} else {
    Write-Warning 'La build non includerà Qwen: llama_cpp non installato.'
}
if (Test-Path 'bundled_models') {
    $pack = @('--add-data','bundled_models;bundled_models') + $pack
}
& $python -m PyInstaller @pack
if ($LASTEXITCODE -ne 0) { throw 'Build Windows fallita.' }
Write-Host 'Pronto: dist\SubtitleForStream\SubtitleForStream.exe' -ForegroundColor Green
Write-Host 'Modelli Whisper e Qwen scaricati automaticamente al primo utilizzo (con Internet).'
