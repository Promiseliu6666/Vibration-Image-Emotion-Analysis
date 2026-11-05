"""Start the health platform and its available local companion services."""
from pathlib import Path
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

OUTER = Path(__file__).resolve().parent
ROOT = OUTER / 'Vibration-Image-Emotion-Analysis-main'
BACKEND = ROOT / 'ruoyi-fastapi-backend'
FRONTEND = ROOT / 'ruoyi-fastapi-frontend'
LOGS = ROOT / '.runtime/logs'
HOME_URL = 'http://127.0.0.1:5173/'
MAIN_API_PATHS = ('/integration/xiaozhi/launch', '/interaction/rest/catalog')
REST_URL = HOME_URL + 'xiaozhi/rest'
PORTAL = OUTER / 'employee-portal'
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_STARTED = {}


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.6):
            return True
    except OSError:
        return False


def configured_values(defaults):
    values = dict(defaults)
    config = BACKEND / '.env.dev'
    if not config.is_file():
        raise RuntimeError('Missing local configuration: ' + str(config))
    for line in config.read_text(encoding='utf-8-sig').splitlines():
        if line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if separator and key in values:
            values[key] = value.strip().split('#', 1)[0].strip().strip('\'"')
    return values


def configured_ports():
    values = configured_values({'DB_PORT': '3306', 'REDIS_PORT': '6379'})
    try:
        ports = {key: int(value) for key, value in values.items()}
    except ValueError as exc:
        raise RuntimeError('DB_PORT and REDIS_PORT must be valid port numbers.') from exc
    if any(not 1 <= value <= 65535 for value in ports.values()):
        raise RuntimeError('DB_PORT and REDIS_PORT must be between 1 and 65535.')
    return ports


def process_environment():
    environment = os.environ.copy()
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment['PYTHONUNBUFFERED'] = '1'
    dotnet = ROOT / '.runtime/dotnet'
    if dotnet.is_dir():
        environment['DOTNET_ROOT'] = str(dotnet)
    environment['PADDLE_PDX_CACHE_HOME'] = str(ROOT / '.runtime/paddlex')
    return environment


def launch(name, command, cwd, port, environment):
    if listening(port):
        print(f'{name}: port {port} already in use; existing service retained.', flush=True)
        return
    executable = Path(command[0])
    if not executable.is_file():
        raise RuntimeError(f'{name} executable is missing: {executable}')
    output = LOGS / f'interactive-rest-{name}.out.log'
    errors = LOGS / f'interactive-rest-{name}.err.log'
    with output.open('ab') as out, errors.open('ab') as err:
        process = subprocess.Popen(
            [str(argument) for argument in command],
            cwd=str(cwd),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    _STARTED[name] = (process, output, errors)
    print(f'{name}: starting on port {port}.', flush=True)


def check_process(name):
    item = _STARTED.get(name)
    if item is not None and item[0].poll() is not None:
        raise RuntimeError(
            f'{name} exited with code {item[0].returncode}. '
            f'Check logs: {item[1]} and {item[2]}'
        )


def wait_port(name, port, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check_process(name)
        if listening(port):
            return
        time.sleep(0.4)
    raise RuntimeError(
        f'{name} is not listening on 127.0.0.1:{port}. '
        f'Check the existing service or logs in {LOGS}'
    )


def http_ready(url, required_paths=(), service=None):
    try:
        # Do not send localhost readiness checks through a system proxy.
        with OPENER.open(url, timeout=2) as response:
            if not 200 <= response.status < 300:
                return False
            if not required_paths and service is None:
                return True
            document = json.load(response)
            if not isinstance(document, dict):
                return False
            if service is not None:
                return document.get('ok') is True and document.get('service') == service
            paths = document.get('paths')
            return isinstance(paths, dict) and all(path in paths for path in required_paths)
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        return False


def wait_http(name, url, timeout=120, required_paths=(), service=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check_process(name)
        if http_ready(url, required_paths, service):
            return
        time.sleep(0.5)
    raise RuntimeError(f'{name} did not become HTTP-ready. Check logs in {LOGS}')


def node_executable():
    located = shutil.which('node')
    if located:
        return Path(located)
    fallback = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if fallback.is_file():
        return fallback
    raise RuntimeError('Node.js was not found on PATH or at the existing local runtime path.')


def start_xiaozhi(environment, primary_db_port):
    from local_services import discover_xiaozhi

    url = 'http://127.0.0.1:8000/openapi.json'
    paths = ('/api/portal/exchange', '/api/camera-source/devices')
    if listening(8000):
        if not http_ready(url, paths):
            raise RuntimeError('Port 8000 is occupied by an HTTP service without Xiaozhi integration routes.')
        print('xiaozhi: compatible service is already running.', flush=True)
        return
    service = discover_xiaozhi()
    if service['port'] == primary_db_port:
        raise RuntimeError('Xiaozhi and the health platform must use separate local database ports.')
    companion_environment = {**environment, **service['environment']}
    launch('xiaozhi-mysql', [
        service['mysql'], '--no-defaults', '--basedir=.', '--datadir=../mysql-data',
        '--bind-address=127.0.0.1', f"--port={service['port']}", '--mysqlx=0', '--console',
    ], service['mysql_cwd'], service['port'], companion_environment)
    wait_port('xiaozhi-mysql', service['port'])
    launch('xiaozhi', [service['python'], '-u', 'main.py'], service['source'], 8000, companion_environment)
    wait_http('xiaozhi', url, timeout=45, required_paths=paths)
    if companion_environment.get('XIAOZHI_RESUME_USB', '1') != '0':
        optional_service('Xiaozhi USB capture', resume_xiaozhi_collectors, service, companion_environment)


def resume_xiaozhi_collectors(service, environment):
    code = (
        'from app.device.capture_control import resume_registered; '
        'result = resume_registered(); '
        'raise SystemExit(bool(result["errors"]))'
    )
    result = subprocess.run(
        [str(service['python']), '-B', '-c', code], cwd=service['source'], env=environment,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if result.returncode:
        raise RuntimeError('Some saved collectors could not resume. Check Xiaozhi device management.')



def start_fatigue(environment):
    from local_services import discover_fatigue_python

    config = configured_values({'FATIGUE_SERVICE_PORT': '9101', 'FATIGUE_SERVICE_PYTHON': ''})
    port = int(os.getenv('FATIGUE_SERVICE_PORT') or config['FATIGUE_SERVICE_PORT'])
    if not 1 <= port <= 65535:
        raise ValueError('FATIGUE_SERVICE_PORT must be between 1 and 65535.')
    url = f'http://127.0.0.1:{port}/health'
    if listening(port):
        if not http_ready(url, service='fatigue'):
            raise RuntimeError(f'Port {port} is occupied and FatigueSense did not pass its health check.')
        print('fatigue: service is already running.', flush=True)
        return
    python = discover_fatigue_python(os.getenv('FATIGUE_SERVICE_PYTHON') or config['FATIGUE_SERVICE_PYTHON'])
    if not python:
        raise RuntimeError('Fatigue Python is missing. Configure FATIGUE_SERVICE_PYTHON to enable this service.')
    probe = "from importlib.util import find_spec; import sys; sys.exit(not all(find_spec(n) for n in sys.argv[1:]))"
    result = subprocess.run(
        [str(python), '-c', probe, 'torch', 'torchvision', 'ultralytics', 'mediapipe', 'cv2'],
        cwd=ROOT / 'fatigue_model_bundle', env=environment, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if result.returncode:
        raise RuntimeError('Fatigue Python is missing one or more model dependencies.')
    launch('fatigue', [python, 'platform_service.py', '--host', '127.0.0.1', '--port', str(port)],
           ROOT / 'fatigue_model_bundle', port, environment)
    wait_http('fatigue', url, timeout=35, service='fatigue')


def optional_service(name, starter, *args):
    try:
        starter(*args)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f'WARNING: {name} unavailable. {exc}', file=sys.stderr, flush=True)


def start_compatibility_redirect(environment):
    python = BACKEND / '.venv/Scripts/python.exe'
    launch('portal', [python, '-u', 'server.py'], PORTAL, 8800, environment)
    wait_port('portal', 8800, timeout=15)
    connection = http.client.HTTPConnection('127.0.0.1', 8800, timeout=2)
    try:
        connection.request('GET', '/')
        response = connection.getresponse()
        if response.status != 307 or response.getheader('Location') != HOME_URL:
            raise RuntimeError('Port 8800 did not return the health platform redirect.')
    finally:
        connection.close()


def main(url=REST_URL):
    _STARTED.clear()
    if not BACKEND.is_dir() or not FRONTEND.is_dir():
        raise RuntimeError(
            'Place start_interactive_rest.py in the outer project directory, '
            'beside the Vibration-Image-Emotion-Analysis-main repository folder.'
        )
    LOGS.mkdir(parents=True, exist_ok=True)
    ports = configured_ports()
    environment = process_environment()
    db_port = ports['DB_PORT']
    redis_port = ports['REDIS_PORT']

    if not listening(db_port) and db_port == 13306:
        mysql = ROOT / '.runtime/mariadb/bin/mariadbd.exe'
        mysql_config = ROOT / '.runtime/data/my.ini'
        if not mysql.is_file() or not mysql_config.is_file():
            raise RuntimeError('Existing portable MySQL runtime/configuration is missing. No database was created.')
        launch('mysql', [mysql, '--defaults-file=' + str(mysql_config),
                        '--bind-address=127.0.0.1', '--port=13306'], ROOT, db_port, environment)
    wait_port('mysql', db_port)

    if not listening(redis_port) and redis_port == 16379:
        cache = ROOT / '.runtime/garnet/net10.0/GarnetServer.exe'
        if not cache.is_file():
            raise RuntimeError('Existing portable cache runtime is missing. Start the configured cache service.')
        launch('cache', [cache, '--port', '16379', '--bind', '127.0.0.1'], ROOT, redis_port, environment)
    wait_port('cache', redis_port)

    if not listening(9099):
        python = BACKEND / '.venv/Scripts/python.exe'
        launch('backend', [python, '-u', 'app.py', '--env=dev'], BACKEND, 9099, environment)
    else:
        print('backend: port 9099 already in use; existing service retained.', flush=True)
    wait_http('backend', 'http://127.0.0.1:9099/openapi.json',
              required_paths=MAIN_API_PATHS)

    if not listening(5173):
        vite = FRONTEND / 'node_modules/vite/bin/vite.js'
        if not vite.is_file():
            raise RuntimeError('Frontend dependencies are missing; existing node_modules/vite is required.')
        frontend_environment = environment.copy()
        # The .cmd opens the browser only after both HTTP checks pass.
        frontend_environment['BROWSER'] = 'none'
        preview = FRONTEND / 'scripts/preview-interactive.mjs'
        if (FRONTEND / 'dist/index.html').is_file() and preview.is_file():
            command = [node_executable(), preview]
        else:
            command = [node_executable(), vite, '--host', '127.0.0.1', '--port', '5173', '--strictPort']
        launch('frontend', command, FRONTEND, 5173, frontend_environment)
    else:
        print('frontend: port 5173 already in use; existing service retained.', flush=True)
    wait_http('frontend', HOME_URL)
    # Both the dev server and the desktop preview proxy this URL. A 200
    # from an unrelated site or Vite's HTML fallback is not readiness.
    wait_http('frontend', HOME_URL + 'dev-api/openapi.json', timeout=15,
              required_paths=MAIN_API_PATHS)
    optional_service('compatibility redirect', start_compatibility_redirect, environment)
    optional_service('Xiaozhi', start_xiaozhi, environment, db_port)
    optional_service('FatigueSense', start_fatigue, environment)
    print('READY: ' + url, flush=True)
    print('Logs: ' + str(LOGS), flush=True)
    return 0


def run(url=REST_URL):
    try:
        return main(url)
    except (Exception, KeyboardInterrupt) as exc:
        print('START FAILED: ' + str(exc), file=sys.stderr, flush=True)
        print('Logs: ' + str(LOGS), file=sys.stderr, flush=True)
        print('Existing services were not stopped. Successfully started services remain running.',
              file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(run())

