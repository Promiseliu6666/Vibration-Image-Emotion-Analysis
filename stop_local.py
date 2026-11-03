"""Safely stop the application processes owned by this repository."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "ruoyi-fastapi-backend"
FRONTEND = ROOT / "ruoyi-fastapi-frontend"
XIAOZHI = ROOT / "xiaozhi-study"
FATIGUE = ROOT / "fatigue_model_bundle"
APP_PORTS = (5173, 9099, 8000, 9101)
STOPPABLE_HELPER_NAMES = {
    "python.exe",
    "python",
    "node.exe",
    "node",
    "esbuild.exe",
    "esbuild",
    "mysqld.exe",
    "mysqld",
    "mariadbd.exe",
    "mariadbd",
    "garnetserver.exe",
    "garnetserver",
    "redis-server.exe",
    "redis-server",
}


def _details(process: psutil.Process) -> tuple[str, str, str]:
    try:
        command = " ".join(process.cmdline()).lower()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        command = ""
    try:
        cwd = str(Path(process.cwd()).resolve()).lower()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        cwd = ""
    return process.name().lower(), command, cwd


def _is_below(path: str, parent: Path) -> bool:
    try:
        Path(path).relative_to(parent)
        return True
    except (ValueError, OSError):
        return False


def _is_app_process(process: psutil.Process) -> bool:
    name, command, cwd = _details(process)
    if name.startswith("python") and command:
        if (
            "app.py" in command
            and "--env=dev" in command
            and (_is_below(cwd, BACKEND) or str(BACKEND).lower() in command)
        ):
            return True
        if (
            "platform_service.py" in command
            and ("--port 9101" in command or _is_below(cwd, FATIGUE))
        ):
            return True
        if (
            ("main.py" in command or "watcher_usb.py" in command)
            and (_is_below(cwd, XIAOZHI) or str(XIAOZHI).lower() in command)
        ):
            return True
    if name in {"node.exe", "node"} and "vite" in command:
        if (
            "5173" in command
            and (_is_below(cwd, FRONTEND) or str(FRONTEND).lower() in command)
        ):
            return True
    return False


def _is_database_process(process: psutil.Process) -> bool:
    name, command, cwd = _details(process)
    if name not in {
        "mysqld.exe",
        "mysqld",
        "mariadbd.exe",
        "mariadbd",
        "garnetserver.exe",
        "garnetserver",
        "redis-server.exe",
        "redis-server",
    }:
        return False
    root_text = str(ROOT).lower()
    return root_text in command or _is_below(cwd, ROOT / ".runtime") or _is_below(
        cwd,
        XIAOZHI / ".runtime",
    )


def _expand_descendants(processes: list[psutil.Process]) -> list[psutil.Process]:
    selected = {process.pid: process for process in processes}
    changed = True
    while changed:
        changed = False
        for process in processes:
            try:
                children = process.children(recursive=False)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            for child in children:
                if (
                    child.pid not in selected
                    and child.name().lower() in STOPPABLE_HELPER_NAMES
                ):
                    selected[child.pid] = child
                    changed = True
    return list(selected.values())


def _stop_processes(label: str, processes: list[psutil.Process]) -> None:
    processes = [process for process in processes if process.pid != os.getpid()]
    if not processes:
        print(f"{label}：没有发现运行中的进程")
        return

    processes = _expand_descendants(processes)
    print(f"{label}：准备关闭 {len(processes)} 个进程")
    for process in processes:
        try:
            print(f"  - PID {process.pid}  {process.name()}")
            process.terminate()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

    _, alive = psutil.wait_procs(processes, timeout=5)
    for process in alive:
        try:
            process.kill()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    psutil.wait_procs(alive, timeout=3)


def _port_open(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="停止本项目启动的服务")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("app", "all"),
        default="app",
        help="app 只关闭应用服务；all 同时关闭项目自带数据库和缓存",
    )
    parser.add_argument("--dry-run", action="store_true", help="只显示将关闭的进程")
    args = parser.parse_args()

    app_processes = [p for p in psutil.process_iter() if _is_app_process(p)]
    database_processes = (
        [p for p in psutil.process_iter() if _is_database_process(p)]
        if args.mode == "all"
        else []
    )

    if args.dry_run:
        print("应用服务：")
        for process in _expand_descendants(app_processes):
            try:
                print(f"  - PID {process.pid}  {process.name()}  {' '.join(process.cmdline())}")
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
        if args.mode == "all":
            print("数据库/缓存：")
            for process in _expand_descendants(database_processes):
                try:
                    print(
                        f"  - PID {process.pid}  {process.name()}  "
                        f"{' '.join(process.cmdline())}"
                    )
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        return 0

    _stop_processes("应用服务", app_processes)
    if args.mode == "all":
        _stop_processes("项目数据库和缓存", database_processes)

    for _ in range(20):
        if not any(_port_open(port) for port in APP_PORTS):
            break
        time.sleep(0.25)

    remaining = [port for port in APP_PORTS if _port_open(port)]
    if remaining:
        print("以下端口仍被占用：" + ", ".join(map(str, remaining)))
        print("可能有其他程序占用了这些端口。")
        return 1
    print("前端、主后端、小智后台和疲劳服务均已关闭。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
