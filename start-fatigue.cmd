@echo off
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
if not exist ".runtime\fatigue-venv\Scripts\python.exe" (
  echo Fatigue environment missing: .runtime\fatigue-venv
  pause
  exit /b 1
)
".runtime\fatigue-venv\Scripts\python.exe" start_fatigue.py --host 127.0.0.1 --port 9101
pause
