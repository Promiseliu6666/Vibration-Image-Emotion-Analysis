@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-watcher.ps1"
if errorlevel 1 pause
