"""Discover existing companion runtimes without copying data or credentials."""

import json
import os
from pathlib import Path

OUTER = Path(__file__).resolve().parent
REPOSITORY = OUTER / 'Vibration-Image-Emotion-Analysis-main'
LEGACY_XIAOZHI = Path.home() / 'Desktop/student-monitor-show/student-monitor-show'


def configured_path(name, fallback):
    raw = os.getenv(name, '').strip()
    return Path(raw or fallback).expanduser().resolve()


def xiaozhi_sources():
    return (
        configured_path('XIAOZHI_SOURCE_DIR', REPOSITORY / 'xiaozhi-study'),
        configured_path('XIAOZHI_LEGACY_PROJECT_DIR', LEGACY_XIAOZHI),
    )


def discover_xiaozhi():
    source, legacy = xiaozhi_sources()
    if not (source / 'main.py').is_file():
        raise RuntimeError(f'Xiaozhi source is missing: {source}')
    source_runtime = source / '.runtime'
    default_runtime = source_runtime if (source_runtime / 'runtime.json').is_file() else legacy / '.runtime'
    runtime = configured_path('XIAOZHI_RUNTIME_DIR', default_runtime)
    config = runtime / 'runtime.json'
    if not config.is_file():
        raise RuntimeError(f'Xiaozhi local runtime configuration is missing: {config}')
    try:
        port = int(json.loads(config.read_text(encoding='utf-8-sig'))['mysql_port'])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError('Xiaozhi database port configuration is invalid.') from exc
    if not 1 <= port <= 65535:
        raise RuntimeError('Xiaozhi database port must be between 1 and 65535.')
    source_python = source / '.venv/Scripts/python.exe'
    default_python = source_python if source_python.is_file() else legacy / '.venv/Scripts/python.exe'
    python = configured_path('XIAOZHI_PYTHON', default_python)
    if not python.is_file():
        raise RuntimeError(f'Xiaozhi Python environment is missing: {python}')
    data_root = legacy if runtime == legacy / '.runtime' else source
    mysql_root = runtime / 'mysql'
    return {
        'source': source,
        'python': python,
        'mysql': mysql_root / 'bin/mysqld.exe',
        'mysql_cwd': mysql_root,
        'port': port,
        'environment': {
            'API_HOST': '127.0.0.1',
            'API_PORT': '8000',
            'WS_PORT': '8000',
            'XIAOZHI_RUNTIME_DIR': str(runtime),
            'XIAOZHI_FRAMES_DIR': str(configured_path('XIAOZHI_FRAMES_DIR', data_root / 'frames')),
            'XIAOZHI_MODELS_DIR': str(configured_path('XIAOZHI_MODELS_DIR', data_root / 'models')),
            'XIAOZHI_ENV_FILE': str(configured_path('XIAOZHI_ENV_FILE', data_root / '.env')),
            'XIAOZHI_LEGACY_PROJECT_DIR': str(legacy),
        },
    }


def discover_fatigue_python(configured=None):
    if configured:
        python = Path(configured).expanduser()
        if not python.is_file():
            raise RuntimeError(f'Configured Fatigue Python does not exist: {python}')
        return python.resolve()
    candidates = (
        REPOSITORY / '.runtime/fatigue-venv/Scripts/python.exe',
        Path(r'D:\Python\environments\fatigue-sense\python.exe'),
    )
    return next((python for python in candidates if python.is_file()), None)
