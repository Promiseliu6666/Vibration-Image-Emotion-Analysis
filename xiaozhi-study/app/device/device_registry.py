"""Remember explicit removals so incoming frames cannot recreate a device."""
import json
from pathlib import Path
from threading import RLock

from app.core.paths import RUNTIME_DIR

lock = RLock()
_path = RUNTIME_DIR / 'removed-devices.json'

def _read():
    if not _path.exists(): return set()
    return set(json.loads(_path.read_text(encoding='utf-8')))

def blocked(device):
    with lock: return device in _read()

def set_blocked(device, value):
    with lock:
        items = _read()
        if value: items.add(device)
        else: items.discard(device)
        _path.parent.mkdir(exist_ok=True)
        temp = _path.with_suffix('.tmp')
        temp.write_text(json.dumps(sorted(items)), encoding='utf-8')
        temp.replace(_path)
