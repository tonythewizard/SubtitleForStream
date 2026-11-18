@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Esegui prima setup_windows.ps1 da PowerShell.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" launch.py
if errorlevel 1 pause
