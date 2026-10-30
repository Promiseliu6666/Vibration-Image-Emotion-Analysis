@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open-project.ps1"
if errorlevel 1 pause
