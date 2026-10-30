import json
import os
from pathlib import Path
from threading import RLock

from app.core.paths import RUNTIME_DIR

PATH=RUNTIME_DIR/'site-settings.json'
lock=RLock()
DEFAULTS={'lan_enabled':False,'frame_retention_days':7,'save_all_frames':False}

def read():
    with lock:
        if PATH.exists():return {**DEFAULTS,**json.loads(PATH.read_text(encoding='utf-8'))}
        return dict(DEFAULTS)

def write(values):
    with lock:
        current=read();current.update(values);PATH.parent.mkdir(exist_ok=True)
        temp=PATH.with_suffix('.tmp');temp.write_text(json.dumps(current,ensure_ascii=False),encoding='utf-8');temp.replace(PATH)
        return current

def host():
    return os.getenv('API_HOST') or ('0.0.0.0' if read()['lan_enabled'] else '127.0.0.1')
