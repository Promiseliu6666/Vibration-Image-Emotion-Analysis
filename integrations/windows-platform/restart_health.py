"""Restart this platform's Python services using the shared desktop launcher."""

from pathlib import Path
import sys

import psutil

from local_services import xiaozhi_sources
from start_interactive_rest import BACKEND, HOME_URL, PORTAL, run


def python_script(arguments):
    for argument in arguments[1:]:
        if argument in ('-u', '-B', '-E', '-s', '-S', '-I'):
            continue
        if argument.startswith('-'):
            return None
        return Path(argument)
    return None


def belongs_to_platform(process, targets):
    name = process.info['name'] or ''
    if name.casefold() not in ('python.exe', 'pythonw.exe'):
        return False
    cwd = Path(process.cwd()).resolve()
    expected = targets.get(cwd)
    if expected is None:
        return False
    script = python_script(process.cmdline())
    return script is not None and (cwd / script).resolve() == expected


def stop_platform_services():
    targets = {
        BACKEND.resolve(): (BACKEND / 'app.py').resolve(),
        PORTAL.resolve(): (PORTAL / 'server.py').resolve(),
    }
    for source in xiaozhi_sources():
        targets[source.resolve()] = (source / 'main.py').resolve()
    stopped = []
    for process in psutil.process_iter(['name']):
        try:
            if not belongs_to_platform(process, targets):
                continue
        except (psutil.Error, OSError):
            continue
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError(f'Cannot restart local Python process {process.pid}.') from exc
        stopped.append(process)
    _, alive = psutil.wait_procs(stopped, timeout=8)
    if alive:
        pids = ', '.join(str(process.pid) for process in alive)
        raise RuntimeError(f'Local Python services are still stopping (PID {pids}).')


if __name__ == '__main__':
    try:
        stop_platform_services()
    except RuntimeError as exc:
        print(f'RESTART FAILED: {exc}', file=sys.stderr, flush=True)
        raise SystemExit(1)
    raise SystemExit(run(HOME_URL))
