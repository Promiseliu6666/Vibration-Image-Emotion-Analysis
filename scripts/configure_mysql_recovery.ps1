[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_.-]+$')]
    [string]$ServiceName = 'mysql'
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an administrator PowerShell window.'
}

$service = Get-Service -Name $ServiceName -ErrorAction Stop
Set-Service -Name $service.Name -StartupType Automatic

# Recover from crashes after sleep/resume, even when Windows itself stays up.
& "$env:SystemRoot\System32\sc.exe" failure $service.Name 'reset=' '86400' `
    'actions=' 'restart/5000/restart/15000/restart/60000'
if ($LASTEXITCODE -ne 0) {
    throw 'Could not configure MySQL service recovery actions.'
}
& "$env:SystemRoot\System32\sc.exe" failureflag $service.Name '1'
if ($LASTEXITCODE -ne 0) {
    throw 'Could not enable recovery for MySQL service failures.'
}

Start-Service -Name $service.Name
Get-Service -Name $service.Name | Select-Object Name, Status, StartType
& "$env:SystemRoot\System32\sc.exe" qfailure $service.Name
