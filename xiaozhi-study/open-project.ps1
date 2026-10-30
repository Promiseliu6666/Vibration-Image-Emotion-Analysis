$ErrorActionPreference = 'Stop'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Backend startup failed' }
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/static/login.html?v=7' -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}
if (-not $ready) { throw 'Backend is not ready. Check .runtime/backend-error.log.' }
Start-Process 'http://127.0.0.1:8000/static/login.html?v=7'
