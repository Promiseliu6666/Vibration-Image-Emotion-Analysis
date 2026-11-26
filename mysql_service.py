"""Recover the existing local Windows MySQL service before starting the app."""

import base64
import os
import re
import socket
import subprocess
import time


def _listening(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _encoded(script):
    return base64.b64encode(script.encode('utf-16le')).decode('ascii')


def _powershell(script, timeout):
    return subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', _encoded(script)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )


def _start_command(service_name):
    return """
$ErrorActionPreference = 'Stop'
try {
    Start-Service -Name '%s' -ErrorAction Stop
    exit 0
} catch {
    $failure = $_.Exception
    while ($null -ne $failure) {
        if (($failure -is [System.ComponentModel.Win32Exception] -and $failure.NativeErrorCode -eq 5) -or
            $failure -is [System.UnauthorizedAccessException]) { exit 5 }
        $failure = $failure.InnerException
    }
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
""" % service_name


def ensure_mysql_service(host, port, service_name='mysql', timeout=45):
    """Start only the named service for local port 3306; retain other deployments.

    An existing listener is reused. Ordinary service permissions are tried first;
    only access denied requests Windows UAC for the service-start operation.
    """
    if os.name != 'nt' or host.strip().lower() not in {'127.0.0.1', 'localhost', '::1'} or port != 3306:
        return
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', service_name):
        raise ValueError('MYSQL_SERVICE_NAME must be an exact Windows service name without wildcards.')
    if _listening(host, port):
        return
    deadline = time.monotonic() + timeout

    def run(script):
        return _powershell(script, max(0.1, deadline - time.monotonic()))

    try:
        status = run("""
try {
    $service = Get-Service -Name '%s' -ErrorAction Stop
    [Console]::Out.Write($service.Status.ToString())
    exit 0
} catch { exit 1 }
""" % service_name)
        if status.returncode:
            raise RuntimeError(
                f"Windows MySQL service '{service_name}' was not found or cannot be queried. "
                'Check Get-Service mysql* and set MYSQL_SERVICE_NAME in the backend .env.dev.'
            )
        state = status.stdout.strip()
        if state == 'Stopped':
            print(f"MySQL service '{service_name}' is stopped; starting it.", flush=True)
            start_script = _start_command(service_name)
            started = run(start_script)
            if started.returncode == 5:
                print('Windows administrator permission is required to start MySQL. Allow the UAC prompt.', flush=True)
                started = run("""
try {
    $process = Start-Process -FilePath powershell.exe -Verb RunAs -WindowStyle Hidden -Wait -PassThru `
        -ArgumentList @('-NoProfile', '-NonInteractive', '-EncodedCommand', '%s') -ErrorAction Stop
    exit $process.ExitCode
} catch {
    if ($_.Exception.NativeErrorCode -eq 1223) { exit 1223 }
    exit 1
}
""" % _encoded(start_script))
                if started.returncode == 1223:
                    raise RuntimeError(
                        f"MySQL startup was cancelled at the Windows permission prompt. "
                        f"Allow the prompt next time, or run Start-Service '{service_name}' in administrator PowerShell."
                    )
            if started.returncode:
                raise RuntimeError(
                    f"Windows could not start MySQL service '{service_name}'. "
                    f"Run Start-Service '{service_name}' in administrator PowerShell and check the MySQL error log."
                )
        elif state not in {'Running', 'StartPending'}:
            raise RuntimeError(
                f"MySQL service '{service_name}' is {state}. "
                f"Check Get-Service '{service_name}' in administrator PowerShell before retrying."
            )
        while not _listening(host, port):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    f"MySQL service '{service_name}' did not become ready on {host}:{port}. "
                    'Check its error log and verify DB_PORT matches the service port.'
                )
            time.sleep(min(0.5, remaining))
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Timed out starting MySQL service '{service_name}'. "
            'Complete the Windows permission prompt and retry; check the MySQL error log if it still fails.'
        ) from exc
