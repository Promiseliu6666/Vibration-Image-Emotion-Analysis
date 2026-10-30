$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot 'stop-watcher.ps1')
$runtime = Join-Path $PSScriptRoot '.runtime'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path (Join-Path $runtime 'backend.pid')) {
    $appId = [int](Get-Content (Join-Path $runtime 'backend.pid'))
    $appInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$appId"
    if ($appInfo -and $appInfo.CommandLine -match 'main.py' -and $appInfo.ExecutablePath -eq $python) {
        & taskkill.exe /PID $appId /T /F | Out-Null
    }
}
& $python (Join-Path $runtime 'stop_mysql.py')
if ($LASTEXITCODE -ne 0) { throw 'Check MySQL shutdown status.' }
Write-Host 'Desktop project services stopped.'

