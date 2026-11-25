"""Shared camera credential initialization without inventing a watcher runtime."""
import os
from pathlib import Path
import secrets
import tempfile

ROOT = Path(__file__).resolve().parents[2]

def _read(path):
    value = path.read_text(encoding='utf-8').strip()
    if not value:
        raise ValueError(f'Camera bridge key is empty: {path}')
    return value

def _publish(path, key):
    """Publish complete content with an atomic, no-overwrite hard link."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.camera-key-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            output.write(key)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        return _read(path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def get_camera_bridge_key(root=None):
    explicit = os.getenv('CAMERA_BRIDGE_KEY', '').strip()
    if explicit:
        return explicit
    root = Path(root) if root is not None else ROOT
    local = root / '.runtime' / 'camera-bridge-secret.txt'
    watcher_root = root / 'xiaozhi-study'
    configured = os.getenv('XIAOZHI_RUNTIME_DIR', '').strip()
    watcher_runtime = Path(configured).expanduser() if configured else watcher_root / '.runtime'
    if not watcher_runtime.is_absolute():
        watcher_runtime = watcher_root / watcher_runtime
    watcher = watcher_runtime / 'camera-bridge-secret.txt'
    if watcher.is_file():
        key = _read(watcher)
    elif local.is_file():
        key = _read(local)
    else:
        key = _publish(local, secrets.token_urlsafe(32))
    if watcher_runtime.is_dir() and not watcher.exists():
        key = _publish(watcher, key)
    if not local.exists():
        _publish(local, key)
    return key
