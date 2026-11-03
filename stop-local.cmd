@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYTHON=ruoyi-fastapi-backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
set "PYTHONIOENCODING=utf-8"

"%PYTHON%" stop_local.py %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo 服务关闭完成。
) else (
  echo 关闭服务时出现错误，请查看上方信息。
)
if not "%NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
