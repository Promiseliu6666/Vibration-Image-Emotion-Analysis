"""Physical USB identity: never use a COM number or display name as identity."""
import hashlib
import json
import re
from pathlib import Path
from serial.tools import list_ports

from app.core.paths import PROJECT_ROOT, RUNTIME_DIR

ROOT = PROJECT_ROOT
STATE = RUNTIME_DIR / 'watcher-usb-state.json'

def camera_ports():
    return [p for p in list_ports.comports() if p.vid == 0x1A86 and p.pid == 0x55D2
            and ('MI_00' in p.hwid.upper() or 'SERIAL-A' in p.description.upper())]

def port_info(port):
    matches = [p for p in camera_ports() if p.device == port]
    if len(matches) != 1:
        raise ValueError('所选 USB 摄像头已断开，请重新检测。')
    return matches[0]

def normalize(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{4,128}', value.strip()):
        raise ValueError('设备没有提供有效的硬件标识，已阻止使用旧设备编号采集。')
    value = value.strip().upper()
    if value in ('NONE', 'NULL', 'UNKNOWN', 'DEFAULT') or set(value) <= {'0'}:
        raise ValueError('设备硬件标识无效，无法区分物理设备。')
    return value

def identify(usb_serial, camera_id):
    usb_serial, camera_id = normalize(usb_serial), normalize(camera_id)
    fingerprint = hashlib.sha256(('watcher-usb-v1\0'+usb_serial+'\0'+camera_id).encode()).hexdigest()
    # Preserve the existing record only for the original, verified physical unit.
    # This exact pair was read from the user's original hardware, not from its COM port.
    device_id = ('watcher-DCB4D9388EAC' if (usb_serial,camera_id)==('5B14267334','360779F5')
                 else 'watcher-usb-'+fingerprint[:24])
    return dict(device_id=device_id, fingerprint=fingerprint, usb_serial=usb_serial,
                camera_id=camera_id, identity_source='usb_serial+sscma_id')

def state_path(serial=None):
    if not serial:return STATE
    return RUNTIME_DIR/'usb-states'/(hashlib.sha256(normalize(serial).encode()).hexdigest()[:24]+'.json')

def write_state(value):
    import os
    import time
    target=state_path(value.get('usb_serial'))
    target.parent.mkdir(exist_ok=True)
    temp = target.with_suffix(f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    for attempt in range(4):
        try:
            temp.replace(target)
            return True
        except PermissionError:
            if attempt < 3:time.sleep(.005 * (attempt+1))
    # A brief Windows reader/antivirus lock must never disconnect the camera.
    try:temp.unlink(missing_ok=True)
    except OSError:pass
    return False


def read_state(serial=None):
    try:
        return json.loads(state_path(serial).read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {}
