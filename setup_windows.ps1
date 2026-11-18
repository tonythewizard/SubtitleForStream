#requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Installa Python 3.12 x64 da python.org (incluso il Python Launcher py).'
}
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Impossibile creare ambiente Python 3.12.' }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip wheel
if ($LASTEXITCODE -ne 0) { throw 'Impossibile aggiornare pip.' }
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Installazione requisiti fallita.' }
# Official upstream CPU wheels; avoid accidental large C++ compiler build.
& $python -m pip install 'llama-cpp-python' --extra-index-url 'https://abetlen.github.io/llama-cpp-python/whl/cpu' --only-binary 'llama-cpp-python'
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Qwen AI non disponibile: i filtri rapidi e Whisper funzionano comunque. Consulta README.'
}
Write-Host 'Pronto. Apri run_windows.bat' -ForegroundColor Green
