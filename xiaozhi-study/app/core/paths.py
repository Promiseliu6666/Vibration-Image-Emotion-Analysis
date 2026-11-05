"""Keep source assets local while allowing explicit reuse of existing local data."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _local_directory(name, default):
    configured = os.environ.get(name, '').strip()
    if not configured:
        return default
    directory = Path(configured).expanduser()
    if not directory.is_absolute():
        directory = PROJECT_ROOT / directory
    return directory.resolve()

RUNTIME_DIR = _local_directory('XIAOZHI_RUNTIME_DIR', PROJECT_ROOT / '.runtime')
FRAMES_DIR = _local_directory('XIAOZHI_FRAMES_DIR', PROJECT_ROOT / 'frames')
MODELS_DIR = _local_directory('XIAOZHI_MODELS_DIR', PROJECT_ROOT / 'models')
STATIC_DIR = PROJECT_ROOT / 'static'
DOCS_DIR = PROJECT_ROOT / 'docs'
