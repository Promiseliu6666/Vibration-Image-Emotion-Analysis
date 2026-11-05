"""Raw physical-device frames for the local vibration service; no webcam fallback."""
import hmac
import time
from collections.abc import Mapping
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from app.core.paths import RUNTIME_DIR
from app.core import live_state
from app.core.db import get_connection

router = APIRouter(prefix='/api/camera-source')
_EXCLUDED_PREFIXES = ('vibration-', 'sim-', 'test-', 'reproduction-', 'e2e-')


def check(request):
    if not request.client or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, '仅允许本机摄像头接入')
    key_file = RUNTIME_DIR / 'camera-bridge-secret.txt'
    try:
        expected = key_file.read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError) as exc:
        raise HTTPException(503, '小智摄像头共享配置缺失，请检查本机运行环境') from exc
    if not expected:
        raise HTTPException(503, '小智摄像头共享配置为空，请检查本机运行环境')
    if not hmac.compare_digest(request.headers.get('X-Camera-Bridge-Key', ''), expected):
        raise HTTPException(403, '摄像头接入认证失败')


def physical_device_id(value):
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and len(value) <= 128 and not any(ord(char) < 32 or ord(char) == 127 for char in value)
            and not value.casefold().startswith(_EXCLUDED_PREFIXES))


def devices():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT device_id,name FROM devices ORDER BY created_at DESC')
            rows = cursor.fetchall()
    finally:
        connection.close()
    result = []
    for row in rows:
        if not isinstance(row, Mapping) or not physical_device_id(row.get('device_id')):
            continue
        device_id = row['device_id']
        state = live_state.status(device_id)
        online = bool(state.get('online')) if isinstance(state, Mapping) else False
        result.append({**row, 'online': online})
    return result


@router.get('/devices')
def list_devices(request: Request):
    check(request)
    return {'devices': devices()}


@router.get('/frame')
def frame(request: Request, device_id: str = ''):
    check(request)
    rows = devices()
    if device_id:
        row = next((item for item in rows if item['device_id'] == device_id), None)
        if row is None:
            raise HTTPException(404, '小智摄像头不存在或不是物理设备')
    else:
        row = next((item for item in rows if item['online']), rows[0] if rows else None)
    if row is None:
        raise HTTPException(503, '尚未连接小智摄像头，请在设备管理中接入')
    state = live_state.status(row['device_id'])
    try:
        stamp = float(state.get('last_received', 0))
    except (ValueError, TypeError, AttributeError):
        stamp = 0
    jpeg = live_state.preview(row['device_id'])
    age = time.time() - stamp
    if not jpeg or stamp <= 0 or age > 5 or age < -5:
        raise HTTPException(503, '小智摄像头暂无新画面，请在小智设备管理中启动采集')
    return Response(jpeg, media_type='image/jpeg', headers={
        'Cache-Control': 'no-store', 'X-Captured-At': str(stamp),
        'X-Frame-Sequence': str(stamp), 'X-Device-Id': row['device_id']})
