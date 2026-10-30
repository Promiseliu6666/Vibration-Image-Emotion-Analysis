"""Ephemeral camera health, separate from persisted learning sessions."""
from collections import OrderedDict
from threading import RLock
import time

_lock = RLock()
_devices = OrderedDict()
LIMIT = 64
TTL = 15

def _entry(device):
    if device not in _devices:
        _devices[device] = {'received': 0, 'processed': 0, 'dropped': 0}
    _devices.move_to_end(device)
    while len(_devices) > LIMIT:
        _devices.popitem(last=False)
    return _devices[device]

def received(device, jpeg, accepted=True, link=None, captured_at=None):
    """记下这一帧；link 标明它是从哪条链路来的（'usb' 本地上传 / 'wifi' 设备密钥上传）。"""
    with _lock:
        item = _entry(device)
        item.update(last_received=time.time() if captured_at is None else captured_at, preview=jpeg)
        if link:
            item['link'] = link
        item['received'] += 1
        if not accepted:
            item['dropped'] += 1

def analyzed(device, result):
    with _lock:
        item = _entry(device)
        item.update(last_analyzed=time.time(), analysis_preview=result.get('preview_jpeg'), error=None, result={key: result.get(key) for key in (
            'record', 'camera_rotation', 'person_present', 'learning_state', 'action_state', 'fatigue_level', 'distraction_level', 'difficulty_indicator', 'request_id', 'phone_alert', 'eye_alert', 'screen_sync', 'vibraimage', 'frame_id', 'captured_at', 'evidence')})
        previews = item.setdefault('analysis_previews', OrderedDict())
        if result.get('frame_id') and result.get('preview_jpeg'):
            previews[result['frame_id']] = result['preview_jpeg']
            while len(previews)>8: previews.popitem(last=False)
        item['processed'] += 1

def failed(device):
    with _lock:
        _entry(device)['error'] = '本帧分析未完成，请查看服务日志或重试采集。'

def status(device, now=None):
    now = time.time() if now is None else now
    with _lock:
        item = {k: v for k, v in _devices.get(device, {}).items() if k not in ('preview','analysis_preview','analysis_previews')}
    captured = (item.get('result') or {}).get('captured_at')
    item['analysis_age_seconds'] = round(max(0, now-captured), 2) if captured else None
    item['analysis_latency_seconds'] = round(max(0, item.get('last_analyzed', now)-captured), 2) if captured else None
    age = now - item.get('last_received', 0)
    item['online'] = bool(item.get('last_received')) and age < TTL
    item['analysis_fresh'] = bool(item.get('last_analyzed')) and now - ((item.get('result') or {}).get('captured_at') or item.get('last_analyzed', 0)) < TTL
    if not item['online']:
        item['state'] = 'offline'
        item['result'] = None
    elif item.get('error'):
        item['state'] = 'error'
    elif not item['analysis_fresh']:
        item['state'] = 'processing'
        item['result'] = None
    elif not (item.get('result') or {}).get('person_present'):
        item['state'] = 'waiting_person'
    else:
        item['state'] = 'monitoring'
    return item

def preview(device, analyzed=False, frame_id=None):
    with _lock:
        item = _devices.get(device, {})
        if time.time() - item.get('last_received', 0) >= TTL:
            return None
        if analyzed and time.time()-item.get('last_analyzed',0)>=TTL: return None
        if analyzed and frame_id: return item.get('analysis_previews',{}).get(frame_id)
        return item.get('analysis_preview' if analyzed else 'preview')

def forget(device):
    with _lock:
        _devices.pop(device, None)


def alert_updated(device, alert):
    with _lock:
        result = _devices.get(device, {}).get("result")
        if result is not None:
            result["phone_alert"] = alert
