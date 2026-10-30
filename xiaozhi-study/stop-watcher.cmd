@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-watcher.ps1"
if errorlevel 1 pause
