$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Backend startup failed' }
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$runtime=Join-Path $PSScriptRoot '.runtime'
if (Test-Path (Join-Path $runtime 'watcher-usb.pid')) {
    $captureId=[int](Get-Content (Join-Path $runtime 'watcher-usb.pid'))
    $capture=Get-CimInstance Win32_Process -Filter "ProcessId=$captureId"
    if ($capture -and $capture.ExecutablePath -eq $python -and $capture.CommandLine -match 'watcher_usb.py') { Write-Host 'Watcher USB capture is already running.'; exit }
}
$env:PYTHONIOENCODING='utf-8'
$capture=Start-Process -FilePath $python -ArgumentList '-u', ('"'+(Join-Path $PSScriptRoot 'watcher_usb.py')+'"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'watcher-usb.log') -RedirectStandardError (Join-Path $runtime 'watcher-usb-error.log')
$capture.Id | Set-Content (Join-Path $runtime 'watcher-usb.pid')
Write-Host 'Watcher USB capture started. Keep the data cable connected.'
