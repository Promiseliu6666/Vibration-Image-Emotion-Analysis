"""Stop the local processes owned by this repository."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket

import psutil

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'ruoyi-fastapi-backend'
FRONTEND = ROOT / 'ruoyi-fastapi-frontend'
XIAOZHI = ROOT / 'xiaozhi-study'
FATIGUE = ROOT / 'fatigue_model_bundle'
APP_PORTS = (5173, 9099, 8000, 9101)
PYTHON_NAMES = {'python.exe', 'python', 'pythonw.exe'}
PYTHON_FLAGS = {'-u', '-B', '-E', '-s', '-S', '-I'}


def _desktop_portal():
    parent = ROOT.parent
    if (parent / 'start_interactive_rest.py').is_file():
        return parent / 'employee-portal'
    return None


def _script(arguments, flags=()):
    for argument in arguments[1:]:
        if argument in flags:
            continue
        return None if argument.startswith('-') else Path(argument)
    return None


def _is_app_process(process):
    try:
        name = process.name().casefold()
        cwd = Path(process.cwd()).resolve()
        arguments = process.cmdline()
        if name in PYTHON_NAMES:
            sources = {
                BACKEND: ('app.py',),
                XIAOZHI: ('main.py', 'watcher_usb.py'),
                FATIGUE: ('platform_service.py',),
            }
            portal = _desktop_portal()
            if portal is not None:
                sources[portal] = ('server.py',)
            paths = sources.get(cwd, ())
            script = _script(arguments, PYTHON_FLAGS)
        elif name in {'node', 'node.exe'} and cwd == FRONTEND:
            paths = ('node_modules/vite/bin/vite.js', 'scripts/preview-interactive.mjs')
            script = _script(arguments)
        else:
            return False
        return script is not None and (cwd / script).resolve() in {
            (cwd / expected).resolve() for expected in paths
        }
    except (OSError, psutil.Error):
        return False


def _is_database_process(process):
    try:
        executable = Path(process.exe()).resolve()
        cwd = Path(process.cwd()).resolve()
    except (OSError, psutil.Error):
        return False
    # Only bundled runtimes are owned by this checkout. The optional desktop
    # launcher may also use an existing database outside the repository.
    owned = {
        ROOT / '.runtime/mariadb/bin/mariadbd.exe': ROOT,
        ROOT / '.runtime/garnet/net10.0/GarnetServer.exe': ROOT,
        XIAOZHI / '.runtime/mysql/bin/mysqld.exe': XIAOZHI / '.runtime/mysql',
    }
    return any(executable == path.resolve() and cwd == folder.resolve() for path, folder in owned.items())


def _stop_processes(label, processes, dry_run):
    print(label)
    stopped = []
    failed = []
    for process in processes:
        try:
            print(f'  - PID {process.pid}  {process.name()}')
            if not dry_run:
                process.terminate()
                stopped.append(process)
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            failed.append(process.pid)
    if stopped:
        _, alive = psutil.wait_procs(stopped, timeout=8)
        failed.extend(process.pid for process in alive)
    if failed:
        print('仍在运行的进程：' + ', '.join(map(str, failed)))
    return not failed


def _port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.4):
            return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description='停止本项目启动的服务')
    parser.add_argument(
        'mode', nargs='?', choices=('app', 'all'), default='app',
        help='app 只关闭应用服务；all 同时关闭项目目录内的数据库和缓存',
    )
    parser.add_argument('--dry-run', action='store_true', help='只显示将关闭的进程')
    args = parser.parse_args()

    candidates = [process for process in psutil.process_iter() if process.pid != os.getpid()]
    apps = [process for process in candidates if _is_app_process(process)]
    databases = (
        [process for process in candidates if _is_database_process(process)]
        if args.mode == 'all' else []
    )

    stopped = _stop_processes('应用服务：', apps, args.dry_run)
    if args.mode == 'all' and stopped:
        stopped = _stop_processes('项目数据库和缓存：', databases, args.dry_run)
    if args.dry_run:
        return 0

    ports = (*APP_PORTS, 8800) if _desktop_portal() else APP_PORTS
    remaining = [port for port in ports if _port_open(port)]
    if remaining:
        print('仍有端口被占用（可能由其他程序使用）：' + ', '.join(map(str, remaining)))
    return 0 if stopped and not remaining else 1


if __name__ == '__main__':
    raise SystemExit(main())
