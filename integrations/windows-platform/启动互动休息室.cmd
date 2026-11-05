@echo off
setlocal
chcp 65001 >nul
set "REST_OUTER=%~dp0"
set "REST_PYTHON=%REST_OUTER%Vibration-Image-Emotion-Analysis-main\ruoyi-fastapi-backend\.venv\Scripts\python.exe"
if not exist "%REST_PYTHON%" (
  echo Backend Python environment was not found:
  echo %REST_PYTHON%
  echo Place this launcher in the outer desktop project directory.
  pause
  exit /b 1
)
"%REST_PYTHON%" "%REST_OUTER%start_interactive_rest.py"
if errorlevel 1 (
  echo Startup did not complete. Keep this window for the diagnostic message above.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:5173/xiaozhi/rest"
echo Interactive rest room is ready. Sign in with the original system account if prompted.
pause
exit /b 0
