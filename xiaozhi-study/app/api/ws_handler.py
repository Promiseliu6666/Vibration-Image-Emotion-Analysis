import asyncio
import base64
import json
import os
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Request
import cv2
import numpy as np
from app.core.config import FRAME_SAVE_DIR, QUEUE_MAXSIZE
from app.core.db import get_connection
from app.core.crypto_utils import decrypt_frame, try_decrypt

router = APIRouter()

from app.core.latest_frames import LatestFrames
frame_queue: asyncio.Queue = LatestFrames(maxsize=QUEUE_MAXSIZE)
output_queue: asyncio.Queue = None  # Set by main.py, analyzer writes results here

_analysis_received = {}
_device_ws = {}  # device_id -> WebSocket


async def _broadcast_results():
    """从 output_queue 读取分析结果，推送给对应设备"""
    while True:
        try:
            msg = await asyncio.wait_for(output_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        device_id = msg.pop("device_id", None)
        ws = _device_ws.get(device_id)
        if ws:
            try:
                if not ws.client or ws.client.host not in ('127.0.0.1','::1'):
                    from app.api.network_ingest import identity
                    try:
                        await asyncio.to_thread(identity,ws)
                    except Exception:
                        await ws.close(code=1008)
                        if _device_ws.get(device_id) is ws:
                            _device_ws.pop(device_id,None)
                        continue
                await ws.send_json(msg)
            except Exception:
                if _device_ws.get(device_id) is ws:
                    _device_ws.pop(device_id, None)


def _ensure_device(device_id):
    import re
    from app.device import device_registry
    from fastapi import HTTPException
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", device_id):
        raise HTTPException(422, "设备编号格式不正确")
    with device_registry.lock:
        if device_registry.blocked(device_id):
            raise HTTPException(409, "设备已移除，请在接入向导中重新连接")
        return _ensure_device_unlocked(device_id)

def _ensure_device_unlocked(device_id):
    """Auto-register unknown devices so they appear in dashboard without manual binding"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM devices WHERE device_id = %s", (device_id,))
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO devices (device_id, name, bind_code) VALUES (%s, %s, %s)",
                    (device_id, device_id, ""),
                )
                conn.commit()
    finally:
        conn.close()


def _process_frame(jpeg_bytes, device_id, timestamp=None, sscma_data=None, vad_data=None, request_id=None, link=None):
    """公共帧处理：存文件 + 入分析队列"""
    import re
    from app.core import live_state
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", device_id) or len(jpeg_bytes) > 4 * 1024 * 1024:
        return False
    # Preview frames do not need an OpenCV image; decode only sampled analysis frames.
    # Keep the exact original JPEG, including its resolution and compression quality.
    if not jpeg_bytes.startswith(b'\xff\xd8') or jpeg_bytes.rfind(b'\xff\xd9') < 2:
        return False
    received_at = __import__('time').monotonic()
    captured_at = __import__('time').time()
    if request_id is None and received_at - _analysis_received.get(device_id, float('-inf')) < 2:
        live_state.received(device_id, jpeg_bytes, link=link, captured_at=captured_at)
        return True
    frame_array = cv2.imdecode(np.frombuffer(jpeg_bytes, np.uint8), cv2.IMREAD_COLOR)
    if frame_array is None:
        return False
    live_state.received(device_id, jpeg_bytes, link=link, captured_at=captured_at)
    now = datetime.now()
    frame_id = __import__("uuid").uuid4().hex
    date_dir = os.path.join(FRAME_SAVE_DIR, now.strftime("%Y-%m-%d"))
    os.makedirs(date_dir, exist_ok=True)
    ts = timestamp or int(now.timestamp())
    safe_id = device_id.replace(":", "-")
    filename = f"{now.strftime('%H%M%S%f')}_{safe_id}.jpg"
    filepath = os.path.join(date_dir, filename)
    with open(filepath, "wb") as f:
        f.write(jpeg_bytes)

    payload = {
        "frame_id": frame_id,
        "captured_at": captured_at,
        "preview_jpeg": jpeg_bytes,
        "device_id": device_id,
        "request_id": request_id,
        "received_at": __import__("time").monotonic(),
        "timestamp": ts,
        "image": frame_array,
        "filepath": filepath,
    }
    if sscma_data:
        payload["sscma"] = sscma_data
    if vad_data:
        payload["vad"] = vad_data

    try:
        frame_queue.put_nowait(payload)
    except asyncio.QueueFull:
        os.remove(filepath)
        return False
    _analysis_received[device_id] = received_at
    if len(_analysis_received)>64:
        _analysis_received.pop(next(iter(_analysis_received)))
    return True

@router.websocket("/ws/device")
async def device_websocket(ws: WebSocket, device_id: str = Query(...)):
    remote_identity=None
    if not ws.client or ws.client.host not in ('127.0.0.1','::1'):
        from app.api.network_ingest import identity
        try:
            remote_identity=await asyncio.to_thread(identity,ws)
            if remote_identity['device_id']!=device_id:
                await ws.close(code=1008);return
        except Exception:
            await ws.close(code=1008);return
    await ws.accept()
    previous=_device_ws.get(device_id)
    if previous and previous is not ws:
        await previous.close(code=1012)
    _device_ws[device_id] = ws
    print(f"[WS] {device_id} connected")
    frame_count = 0

    try:
        while True:
            raw = await ws.receive_text()
            if remote_identity:
                try:
                    remote_identity=await asyncio.to_thread(identity,ws)
                except Exception:
                    await ws.close(code=1008);return
            msg = json.loads(raw)

            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"status": "ok", "type": "pong"}))
                continue

            frame_b64 = msg["image"]
            timestamp = msg.get("timestamp")
            device_id_msg = msg.get("device_id", device_id)
            sscma_data = msg.get("sscma")
            vad_data = msg.get("vad")
            if remote_identity and device_id_msg!=remote_identity['device_id']:
                await ws.close(code=1008);return
            _ensure_device(device_id_msg)
            raw_data = base64.b64decode(frame_b64)
            # Decrypt if the frame was encrypted on the ESP32
            if msg.get("encrypted"):
                jpeg_bytes = decrypt_frame(raw_data)
            else:
                jpeg_bytes = raw_data
            accepted = _process_frame(jpeg_bytes, device_id_msg, timestamp, sscma_data, vad_data, link=('usb' if not remote_identity else 'wifi'))
            if accepted and remote_identity:
                from app.core import access_control
                await asyncio.to_thread(access_control.seen,device_id_msg,True)
            await ws.send_text(json.dumps({"status": "ok" if accepted else "error"}))
            frame_count += 1
            if frame_count % 30 == 0:
                print(f"[WS] {device_id}: {frame_count} frames received")

    except WebSocketDisconnect:
        print(f"[WS] {device_id} disconnected normally ({frame_count} frames)")
    except OSError as e:
        print(f"[WS] {device_id} OSError (WiFi dropped?): {e}")
    except Exception as e:
        print(f"[WS] {device_id} unexpected error: {type(e).__name__}: {e}")
    finally:
        if _device_ws.get(device_id) is ws:
            _device_ws.pop(device_id, None)
        print(f"[WS] {device_id} cleaned up")


@router.post("/upload/frame")
async def upload_frame(request: Request, device_id: str = "watcher-01"):
    """小智 Watcher HTTP 上传端点 — 手动解析 multipart，兼容 chunked 传输"""
    if not request.client or request.client.host not in ('127.0.0.1','::1'):
        from app.api.network_ingest import upload
        return await upload(request)
    content_type = request.headers.get("content-type", "")
    raw_body = await request.body()

    # 从 Content-Type 提取 boundary
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
            break

    if not boundary:
        # 无 boundary，尝试直接当 JPEG 处理（自动检测是否加密）
        await asyncio.to_thread(_ensure_device, device_id)
        ok = _process_frame(try_decrypt(raw_body), device_id, link='usb')
        return {"status": "ok" if ok else "error"}

    # 手动解析 multipart: 用 boundary 切分，找到 file 字段的二进制内容
    boundary_bytes = boundary.encode("utf-8")
    delimiter = b"--" + boundary_bytes
    parts = raw_body.split(delimiter)

    jpeg_bytes = None
    is_encrypted = False
    for part_bytes in parts:
        if b"Content-Disposition" not in part_bytes:
            continue
        # 分离 header 和 body（以 \r\n\r\n 为界）
        header_end = part_bytes.find(b"\r\n\r\n")
        if header_end < 0:
            continue
        headers_block = part_bytes[:header_end].decode("utf-8", errors="ignore")
        body = part_bytes[header_end + 4:]

        # 去掉末尾的 \r\n（如果有）
        if body.endswith(b"\r\n"):
            body = body[:-2]

        if 'name="file"' in headers_block and body:
            jpeg_bytes = body
            # 检查 ESP32 固件设置的加密标志
            if "X-Encrypted: 1" in headers_block or "x-encrypted: 1" in headers_block.lower():
                is_encrypted = True
            break

    if not jpeg_bytes:
        return {"status": "error", "message": "no file part found"}

    await asyncio.to_thread(_ensure_device, device_id)
    if is_encrypted:
        jpeg_bytes = decrypt_frame(jpeg_bytes)
    ok = _process_frame(jpeg_bytes, device_id, link='usb')
    return {"status": "ok" if ok else "error"}
