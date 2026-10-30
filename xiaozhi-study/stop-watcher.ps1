$ErrorActionPreference='Stop'
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$pidFile=Join-Path $PSScriptRoot '.runtime\watcher-usb.pid'
if (Test-Path $pidFile) {
    $captureId=[int](Get-Content $pidFile)
    $capture=Get-CimInstance Win32_Process -Filter "ProcessId=$captureId"
    if ($capture -and $capture.ExecutablePath -eq $python -and $capture.CommandLine -match 'watcher_usb.py') { & taskkill.exe /PID $captureId /T /F | Out-Null }
}
Write-Host 'Watcher USB capture stopped.'
