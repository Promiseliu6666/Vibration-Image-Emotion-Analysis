"""Nonblocking local fatigue process supervision; never stops reused services."""
import asyncio
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.request import build_opener, ProxyHandler
from urllib.parse import urlparse
from .camera_bridge_config import ROOT, get_camera_bridge_key

log = logging.getLogger(__name__)

class FatigueServiceSupervisor:
    def __init__(self, root=None):
        self.root = Path(root) if root else ROOT
        self.url = os.getenv('FATIGUE_SERVICE_URL', 'http://127.0.0.1:9101').rstrip('/')
        self._process = None
        self._state = 'pending'
        self._detail = ''
        self._stop = threading.Event()
        self._task = None
        self._guard = threading.Lock()

    def status(self):
        state = self._state
        if self._process is not None and self._process.poll() is not None and state == 'ready':
            state = 'failed'
        return {'state': state, 'url': self.url, 'detail': self._detail,
                'owned': self._process is not None, 'ready': state in ('ready', 'reused')}

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(asyncio.to_thread(self._start))
        return self._task

    def _healthy(self):
        try:
            with build_opener(ProxyHandler({})).open(self.url + '/health', timeout=1) as response:
                data = json.load(response)
                return data.get('ok') is True and data.get('service') == 'fatigue'
        except (OSError, ValueError):
            return False

    def _start(self):
        if os.getenv('FATIGUE_SERVICE_AUTOSTART', 'true').lower() in ('false', '0', 'no'):
            self._state = 'disabled'
            return
        parsed = urlparse(self.url)
        if parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.port != 9101:
            self._state = 'external'
            self._detail = 'External fatigue service is managed separately'
            return
        if self._healthy():
            self._state = 'reused'
            return
        # An OS-owned lock prevents duplicate children during overlapping reloads.
        lock = socket.socket()
        try:
            if os.name == 'nt':
                lock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                lock.bind(('127.0.0.1', 19101))
            except OSError:
                self._state = 'waiting'
                self._wait_ready()
                return
            if self._healthy():
                self._state = 'reused'
                return
            python = Path(os.getenv('FATIGUE_SERVICE_PYTHON') or os.getenv('FATIGUE_PYTHON') or str(self.root / '.runtime/fatigue-venv/Scripts/python.exe'))
            if not python.is_file():
                raise RuntimeError(f'Fatigue Python environment missing: {python}')
            runtime = self.root / '.runtime'
            runtime.mkdir(exist_ok=True)
            env = dict(os.environ, CAMERA_BRIDGE_KEY=get_camera_bridge_key(self.root), PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
            with self._guard:
                if self._stop.is_set():
                    return
                with (runtime / 'fatigue-service.log').open('ab') as output:
                    self._process = subprocess.Popen([str(python), str(self.root / 'start_fatigue.py')],
                        cwd=str(self.root), env=env, stdout=output, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self._state = 'starting'
            self._wait_ready()
            # Keep the launch lock for the lifetime of our child.
            while not self._stop.wait(1) and self._process.poll() is None:
                pass
        except Exception as exc:
            self._state, self._detail = 'failed', str(exc)
            log.exception('Fatigue service startup failed')
        finally:
            lock.close()

    def _wait_ready(self):
        deadline = time.monotonic() + 120
        while not self._stop.is_set() and time.monotonic() < deadline:
            if self._healthy():
                self._state = 'ready' if self._process else 'reused'
                return
            if self._process and self._process.poll() is not None:
                break
            self._stop.wait(1)
        if not self._stop.is_set():
            self._state, self._detail = 'failed', 'Fatigue service did not become ready; see .runtime/fatigue-service.log'

    def stop(self):
        self._stop.set()
        with self._guard:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=3)
