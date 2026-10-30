$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot 'prepare-portable.ps1')
$runtime = Join-Path $PSScriptRoot '.runtime'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Python environment missing. See docs/local.md.' }
$cfg = Get-Content (Join-Path $runtime 'runtime.json') -Raw | ConvertFrom-Json
$probe = [System.Net.Sockets.TcpClient]::new()
$dbReady = $false
try { $probe.Connect('127.0.0.1', [int]$cfg.mysql_port); $dbReady = $true } catch {} finally { $probe.Dispose() }
if (-not $dbReady) {
    & $python (Join-Path $runtime 'start_mysql.py')
    if ($LASTEXITCODE -ne 0) { throw 'MySQL launch failed.' }
}
$env:PYTHONIOENCODING = 'utf-8'
& $python (Join-Path $runtime 'check_db.py')
if ($LASTEXITCODE -ne 0) { throw 'MySQL did not start. Check .runtime/mysql-error.log.' }
if (Test-Path (Join-Path $runtime 'backend.pid')) {
    $savedId = [int](Get-Content (Join-Path $runtime 'backend.pid'))
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId=$savedId"
    if ($existing -and $existing.ExecutablePath -eq $python -and $existing.CommandLine -match 'main.py') {
        Write-Host 'Original project is already running.'
        exit
    }
}
$appProcess = Start-Process -FilePath $python -ArgumentList '-u', ('"' + (Join-Path $PSScriptRoot 'main.py') + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'backend.log') -RedirectStandardError (Join-Path $runtime 'backend-error.log')
$appProcess.Id | Set-Content (Join-Path $runtime 'backend.pid')
Write-Host 'Desktop project is starting at http://127.0.0.1:8000'
