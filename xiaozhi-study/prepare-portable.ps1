$ErrorActionPreference = 'Stop'
$base = Join-Path $PSScriptRoot '.runtime/python'
if (Test-Path (Join-Path $base 'python.exe')) {
    if ($PSScriptRoot -match '[^\x00-\x7F]') { throw 'Please extract to an ASCII-only path, for example C:\Xiaozhi\xiaozhi-study. MediaPipe cannot load models from non-ASCII paths.' }
    $cfg = "home = $base`ninclude-system-site-packages = false`nversion = 3.11.15`nexecutable = $base\python.exe`n"
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot '.venv/pyvenv.cfg'), $cfg)
    & (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'bootstrap-runtime.py')
    if ($LASTEXITCODE -ne 0) { throw 'Portable environment initialization failed.' }
}
