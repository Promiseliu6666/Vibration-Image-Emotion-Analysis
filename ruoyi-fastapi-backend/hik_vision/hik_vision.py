# hik_vision/hik_vision.py
import cv2
import numpy as np
import os
import urllib.request
import time
import base64
import asyncio
import traceback
import subprocess
import hmac
from pathlib import Path

import httpx
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, Depends, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.ext.asyncio import AsyncSession

from hik_vision.Vibration_image_algorithm import VibraimageCore
from hik_vision.camera_contract import resolve_camera_selection, to_camera_id
from hik_vision.camera_algorithms import ALGORITHMS, camera_algorithm_store
from hik_vision.camera_bridge_config import get_camera_bridge_key
from pydantic import BaseModel, Field
from config.get_db import get_db
from exceptions.exception import AuthException
from module_admin.service.login_service import LoginService
from module_xuzhou.service.people_service import PeopleService
from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.entity.vo.analysis_vo import BinhuaAnalysisModel

from hik_vision.email_service import send_analysis_email

videoController = APIRouter(
    prefix='/video',
    include_in_schema=False
)

# ==================== 摄像头配置 ====================
RTSP_URL = ""  # Configure CAMERA_RTSP_URL in the local environment.
LOCAL_CAMERA_INDEX = int(os.getenv("LOCAL_CAMERA_INDEX", "0"))
SIMILARITY_THRESHOLD = 0.4

RTSP_URL = os.getenv("CAMERA_RTSP_URL", RTSP_URL)

# ==================== DNN 模型 ====================
MODEL_PROTO = "deploy.prototxt"
MODEL_WEIGHTS = "res10_300x300_ssd_iter_140000.caffemodel"

MODEL_PROTO_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
MODEL_WEIGHTS_URL = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"

if not os.path.exists(MODEL_PROTO):
    print("[DNN模型] 正在下载 deploy.prototxt ...")
    try:
        urllib.request.urlretrieve(MODEL_PROTO_URL, MODEL_PROTO)
        print("[DNN模型] 下载完成")
    except Exception as e:
        print(f"[DNN模型] 下载失败: {e}")

if not os.path.exists(MODEL_WEIGHTS):
    print("[DNN模型] 正在下载 weights ...")
    try:
        urllib.request.urlretrieve(MODEL_WEIGHTS_URL, MODEL_WEIGHTS)
        print("[DNN模型] 下载完成")
    except Exception as e:
        print(f"[DNN模型] 下载失败: {e}")

try:
    face_net = cv2.dnn.readNetFromCaffe(MODEL_PROTO, MODEL_WEIGHTS)
    print("[DNN模型] 加载成功")
except Exception as e:
    print(f"[DNN模型] 加载失败: {e}")

# ==================== 视频保存配置 ====================
VIDEO_SAVE_DIR = "videos"
os.makedirs(VIDEO_SAVE_DIR, exist_ok=True)

video_writers = {"local": None, "rtsp": None}
video_start_times = {"local": None, "rtsp": None}

RECORD_FPS = 20.0
RECORD_DURATION = 10.0
try:
    RAW_STREAM_FPS = max(1.0, float(os.getenv('RAW_STREAM_FPS', '12')))
except ValueError:
    RAW_STREAM_FPS = 12.0

# ==================== 优化参数 ====================
FACE_DETECT_INTERVAL = 6
RECOGNIZE_INTERVAL = 20
ANALYSIS_INTERVAL = 4
STABLE_FRAMES_REQUIRED = 15
TOLERANCE = 60
LOST_CHECK_INTERVAL = 20
RECOGNIZE_TIMEOUT = 3.0
RECOGNIZE_MIN_GAP_SECONDS = 2.5

# Limit concurrent face compare tasks to avoid blocking the whole event loop / worker.
face_compare_semaphore = asyncio.Semaphore(1)


def _open_native_camera(source: str):
    if source == 'xiaozhi' or source.startswith('xiaozhi:'):
        from hik_vision.xiaozhi_capture import XiaozhiCapture
        return XiaozhiCapture(source.partition(':')[2])
    if source == "local":
        print("[视频流] 使用本地摄像头")
        cap = cv2.VideoCapture(LOCAL_CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        start_time = time.time()
        while time.time() - start_time < 3:
            ret, _ = cap.read()
            if ret:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print("[视频流] 本地摄像头已就绪")
                return cap
            time.sleep(0.05)

        cap.release()
        raise HTTPException(status_code=500, detail="本地摄像头无法打开")

    elif source == "rtsp":
        if not RTSP_URL.strip():
            raise HTTPException(status_code=500, detail="RTSP地址未配置")
        print("[视频流] 使用RTSP摄像头")

        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|timeout;5000000'

        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        start_time = time.time()
        while time.time() - start_time < 5:
            ret, _ = cap.read()
            if ret:
                print("[视频流] RTSP摄像头已就绪")
                return cap
            time.sleep(0.05)

        cap.release()
        raise HTTPException(status_code=500, detail="RTSP摄像头连接失败")

    else:
        raise HTTPException(status_code=400, detail="无效的source参数")


from hik_vision.camera_hub import CameraHub
camera_hubs = {source: CameraHub(source, _open_native_camera) for source in ('local','rtsp')}
def get_camera_cap(source: str):
    if source not in camera_hubs:
        raise HTTPException(400, '无效的摄像头来源')
    return camera_hubs[source].subscribe()

global_caps = {"local": None, "rtsp": None}
active_clients = {"local": 0, "rtsp": 0}

latest_results = {
    "local": {f"e{i}": 0.0 for i in range(1, 15)},
    "rtsp": {f"e{i}": 0.0 for i in range(1, 15)}
}

stable_state = {
    "local": {
        "stable_count": 0, "prev_center": None, "prev_size": None,
        "locked_rect": None, "analyzing": False, "frame_count": 0,
        "matched_person": None, "feature_extracted": False,
        "match_similarity": 0.0,
        "last_detected_rect": None,
        "identified": False,
        "analysis_start_time": None,
        "analysis_duration": RECORD_DURATION,
        "analysis_completed": False,
        "person_id": "",
        "current_video_path": None,
        "video_frame_count": 0,
        "recognizing": False,
        "last_recognize_at": 0.0,
        "email_status": "idle",
        "email_message": "",
        "email_updated_at": None
    },
    "rtsp": {
        "stable_count": 0, "prev_center": None, "prev_size": None,
        "locked_rect": None, "analyzing": False, "frame_count": 0,
        "matched_person": None, "feature_extracted": False,
        "match_similarity": 0.0,
        "last_detected_rect": None,
        "identified": False,
        "analysis_start_time": None,
        "analysis_duration": RECORD_DURATION,
        "analysis_completed": False,
        "person_id": "",
        "current_video_path": None,
        "video_frame_count": 0,
        "recognizing": False,
        "last_recognize_at": 0.0,
        "email_status": "idle",
        "email_message": "",
        "email_updated_at": None
    }
}


import copy,re

def _camera_selection(camera_id='', source='local', device_id=''):
    try:
        return resolve_camera_selection(camera_id, source, device_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def resolve_camera_source(source, device_id=''):
    key = _camera_selection(source=source, device_id=device_id).camera_id
    if key not in stable_state:
        if len(stable_state)>64:raise HTTPException(429,'摄像头会话过多，请重启后台释放')
        stable_state[key]=copy.deepcopy(stable_state_template)
        global_caps[key]=None;active_clients[key]=0
        latest_results[key]={f'e{i}':0.0 for i in range(1,15)}
        video_writers[key]=None;video_start_times[key]=None
        camera_hubs[key]=CameraHub(key,_open_native_camera)
    return key
stable_state_template=copy.deepcopy(stable_state['local'])
resolve_camera_source('xiaozhi')

def _camera_bridge_key():
    try:
        return get_camera_bridge_key()
    except (OSError, ValueError, UnicodeError) as exc:
        raise HTTPException(503, '摄像头共享配置不可用') from exc


async def _fetch_xiaozhi_devices():
    key = _camera_bridge_key()
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
            response = await client.get(
                'http://127.0.0.1:8000/api/camera-source/devices',
                headers={'X-Camera-Bridge-Key': key},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, '小智摄像头服务不可用，请检查设备管理与后台服务') from exc
    if not isinstance(data, dict) or not isinstance(data.get('devices'), list):
        raise HTTPException(502, '小智摄像头设备列表格式不正确')
    return data['devices']


async def resolve_registered_camera_source(source, device_id='', *, camera_id=''):
    selection = _camera_selection(camera_id, source, device_id)
    if selection.camera_id not in stable_state:
        devices = await _fetch_xiaozhi_devices()
        if not any(
            isinstance(device, dict) and device.get('device_id') == selection.device_id
            for device in devices
        ):
            raise HTTPException(404, '小智摄像头未登记或不是物理设备')
        return resolve_camera_source(selection.source, selection.device_id)
    return selection.camera_id


async def _authenticate_video_request(request, query_db, allow_image_cookie=False):
    authorization = request.headers.get('Authorization')
    scheme, token = get_authorization_scheme_param(authorization)
    if not authorization and allow_image_cookie and request.headers.get('Sec-Fetch-Site') == 'same-origin':
        token = request.cookies.get('Admin-Token', '')
        scheme = 'bearer'
    if scheme.lower() != 'bearer' or not token.strip() or any(char.isspace() for char in token):
        raise HTTPException(401, '请先登录健康监测平台')
    try:
        return await LoginService.get_current_user(request=request, token=token, query_db=query_db)
    except AuthException as exc:
        raise HTTPException(401, '登录已失效，请重新登录健康监测平台') from exc


async def _require_video_user(request: Request, query_db: AsyncSession = Depends(get_db)):
    return await _authenticate_video_request(request, query_db)


async def _require_video_stream_user(request: Request, query_db: AsyncSession = Depends(get_db)):
    return await _authenticate_video_request(request, query_db, allow_image_cookie=True)

async def save_analysis_to_db(db: AsyncSession, source: str, state: dict, results: dict, video_path: str = None):
    try:
        person_id = state.get("person_id")
        person_name = state.get("matched_person") or "Unknown"

        happiness_index = results.get("e12", 0.0)

        if happiness_index >= 80:
            happiness_level = "高"
        elif happiness_index >= 60:
            happiness_level = "中"
        else:
            happiness_level = "低"

        if happiness_index >= 70:
            safety_risk = "低风险"
        elif happiness_index >= 40:
            safety_risk = "中风险"
        else:
            safety_risk = "高风险"

        analysis_model = BinhuaAnalysisModel(
            source=source,
            person_name=person_name,
            person_id=person_id,
            video_path=video_path,
            e1=results.get("e1", 0.0), e2=results.get("e2", 0.0), e3=results.get("e3", 0.0),
            e4=results.get("e4", 0.0), e5=results.get("e5", 0.0), e6=results.get("e6", 0.0),
            e7=results.get("e7", 0.0), e8=results.get("e8", 0.0), e9=results.get("e9", 0.0),
            e10=results.get("e10", 0.0), e11=results.get("e11", 0.0), e12=results.get("e12", 0.0),
            e13=results.get("e13", 0.0), e14=results.get("e14", 0.0),
            happiness_index=happiness_index,
            happiness_level=happiness_level,
            safety_risk=safety_risk
        )

        analysis_id = await BinhuaAnalysisDao.add_analysis_dao(db, analysis_model)
        await db.commit()
        print(f"[{source}] 分析结果保存成功，人员: {person_name} (ID: {person_id}), 视频: {video_path}")
        return analysis_id

    except Exception as e:
        print(f"[{source}] 保存失败: {e}")
        traceback.print_exc()
        return None


def reset_analysis_state(source: str):
    if source in stable_state:
        state = stable_state[source]
        state["session_generation"] = state.get("session_generation",0)+1
        state.update({
            "stable_count": 0, "prev_center": None, "prev_size": None,
            "locked_rect": None, "analyzing": False, "frame_count": 0,
            "matched_person": None, "feature_extracted": False,
            "match_similarity": 0.0,
            "last_detected_rect": None,
            "identified": False,
            "analysis_start_time": None,
            "analysis_completed": False,
            "person_id": "",
            "current_video_path": None,
            "video_frame_count": 0,
            "recognizing": False,
            "last_recognize_at": 0.0, "result_samples":0,"sample_frames":0,"stability_progress":0.,"stage":"searching","last_error":None,
            "email_status":"idle","email_message":"","email_updated_at":None
        })

        if video_writers.get(source) is not None:
            try:
                video_writers[source].release()
            except Exception as e:
                print(f"[{source}] release异常: {e}")
            video_writers[source] = None
        video_start_times[source] = None

        latest_results[source] = {f"e{i}": 0.0 for i in range(1, 15)}


def draw_face_recognition(frame: np.ndarray, name: str, similarity: float, rect: tuple, is_locked: bool = False,
                          remaining_time: float = None):
    if rect is None:
        return
    x, y, w, h = rect

    if is_locked:
        color = (255, 0, 0)
        thickness = 3
        label = "[Locked]"
        if remaining_time is not None:
            label = f"[Locked] | {remaining_time:.1f}s"
    else:
        color = (0, 255, 0)
        thickness = 2
        label = ""

    cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)

    if label.strip():
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(frame, (x, y - 25), (x + text_size[0] + 10, y), (0, 0, 255), cv2.FILLED)
        cv2.putText(frame, label, (x + 5, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


import threading
_face_detector_local=threading.local()

def detect_face(frame: np.ndarray):
    try:
        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        net=getattr(_face_detector_local,'net',None)
        if net is None:
            net=cv2.dnn.readNetFromCaffe(MODEL_PROTO,MODEL_WEIGHTS);_face_detector_local.net=net
        net.setInput(blob)
        detections = net.forward()

        best_rect = None
        max_confidence = 0.5

        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > max_confidence:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                startX = max(0, startX)
                startY = max(0, startY)
                endX = min(w, endX)
                endY = min(h, endY)
                rect = (startX, startY, endX - startX, endY - startY)
                max_confidence = confidence
                best_rect = rect
        return best_rect
    except Exception as e:
        print(f"[DNN人脸检测] 异常: {e}")
        return None


def encode_face_image(frame: np.ndarray, face_rect: tuple) -> str:
    """
    Crop and downscale face area before base64 encoding.
    """
    if face_rect is not None:
        x, y, w, h = face_rect
        pad_w = int(w * 0.25)
        pad_h = int(h * 0.25)
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(frame.shape[1], x + w + pad_w)
        y2 = min(frame.shape[0], y + h + pad_h)
        cropped = frame[y1:y2, x1:x2]
        if cropped.size > 0:
            frame = cropped

    h, w = frame.shape[:2]
    max_side = max(h, w)
    if max_side > 320:
        scale = 320.0 / max_side
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
    return base64.b64encode(buffer).decode('utf-8')


async def recognize_face(db: AsyncSession, frame: np.ndarray, face_rect: tuple, state: dict):
    try:
        current_image_base64 = await asyncio.to_thread(encode_face_image, frame, face_rect)

        async with face_compare_semaphore:
            compare_results = await asyncio.wait_for(
                PeopleService.face_compare_services(
                    db, current_image_base64, group_id=1, threshold=SIMILARITY_THRESHOLD
                ),
                timeout=RECOGNIZE_TIMEOUT
            )

        if compare_results and compare_results[0]:
            best_match = compare_results[0]
            name = best_match.get('name')
            similarity = best_match.get('similarity', 0.0)

            if name and name != "Unknown":
                try:
                    from module_xuzhou.entity.do.people_do import PeopleFace
                    from sqlalchemy import select
                    result = await db.execute(
                        select(PeopleFace)
                        .where(
                            PeopleFace.name == name,
                            PeopleFace.group_id == 1,
                            PeopleFace.is_deleted == False
                        )
                        .limit(1)
                    )
                    person = result.scalars().first()
                    if person:
                        state["person_id"] = person.id
                        state["matched_person"] = person.name
                        state["identified"] = True
                        state["match_similarity"] = similarity
                        print(f"[人脸识别] 成功匹配数据库具体人员: {person.name} (ID: {person.id})")
                        return person.name, similarity
                except Exception as e:
                    print(f"[人脸识别] 查询person_id异常: {e}")

        state["person_id"] = ""
        state["matched_person"] = "Unknown"
        state["identified"] = False
        return "Unknown", 0.0

    except Exception as e:
        print(f"[人脸识别] 异常: {e}")
        state["person_id"] = ""
        state["matched_person"] = "Unknown"
        state["identified"] = False
        return "Unknown", 0.0


@videoController.get("/feed/raw", dependencies=[Depends(_require_video_stream_user)])
async def generate_raw_video_stream(
        request: Request,
        camera_id: str = Query(default=''),
        source: str = Query(default='local'),
        device_id: str = Query(default='')
):
    """Stream the shared camera without happiness-analysis overlays."""
    source = await resolve_registered_camera_source(source, device_id, camera_id=camera_id)
    reader = get_camera_cap(source)

    async def generate():
        try:
            while not await request.is_disconnected():
                loop_started = time.monotonic()
                ret, frame = reader.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue
                _, buffer = await asyncio.to_thread(
                    cv2.imencode,
                    '.jpg',
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 78],
                )
                yield (
                    b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                    + buffer.tobytes()
                    + b'\r\n'
                )
                elapsed = time.monotonic() - loop_started
                await asyncio.sleep(max(0.01, 1.0 / RAW_STREAM_FPS - elapsed))
        finally:
            reader.release()

    return StreamingResponse(
        generate(),
        media_type='multipart/x-mixed-replace; boundary=frame',
    )


# ==================== 主视频流函数（已包含ffmpeg转码后删除AVI功能） ====================
@videoController.get("/feed/analysis", dependencies=[Depends(_require_video_stream_user)])
async def generate_video_stream(
        request: Request,
        camera_id: str = Query(default=''),
        source: str = Query(default='local'),
        device_id: str = Query(default=''),
        query_db: AsyncSession = Depends(get_db)
):
    source = await resolve_registered_camera_source(source, device_id, camera_id=camera_id)

    active_clients[source] += 1
    print(f"[{source}] 新客户端连接，当前活跃客户端数: {active_clients[source]}")

    cap = get_camera_cap(source)
    state = stable_state[source]
    analyzer = VibraimageCore()
    analyzer.halo_params["ACCUMULATE_FRAMES"] = 5

    async def generate():
        frame_count = 0
        last_frame_time = time.time()
        recognize_task = None
        from hik_vision.face_stability import FaceStabilityGate
        from collections import deque
        gate=FaceStabilityGate()
        frame_times=deque(maxlen=20)
        last_detection=-float('inf')

        try:
            while not await request.is_disconnected():
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                original_frame = cv2.resize(frame, (640, 480))
                display_frame = original_frame.copy()
                if source == 'local':
                    display_frame = cv2.flip(display_frame, 1)

                now=time.monotonic()
                frame_times.append(now)
                fps=(len(frame_times)-1)/(frame_times[-1]-frame_times[0]) if len(frame_times)>1 and frame_times[-1]>frame_times[0] else cap.get(cv2.CAP_PROP_FPS) or 3
                state['observed_fps']=round(fps,2)
                if now-last_detection>=.35:
                    detected=await asyncio.to_thread(detect_face,original_frame)
                    last_detection=now
                    transition=gate.observe(detected,now)
                    if transition['lost'] or (transition['changed'] and state['analyzing']):
                        reset_analysis_state(source);analyzer.reset()
                    state['stable_count']=gate.count
                    state['stability_progress']=transition['progress']
                    state['last_detected_rect']=gate.rect
                face_rect=gate.rect if gate.visible(now) else None
                if not state['analyzing']:
                    state['stage']='stabilizing' if face_rect is not None else 'searching'
                if gate.ready and face_rect is not None and not state['analyzing']:
                    state['locked_rect']=face_rect;state['analyzing']=True
                    state['analysis_start_time']=time.time();state['analysis_completed']=False
                    state['stage']='collecting';state['result_samples']=0;state['sample_frames']=0
                    analyzer.reset()
                elif state['analyzing'] and face_rect is not None:
                    state['locked_rect']=face_rect

                # 人脸识别
                if recognize_task is not None and recognize_task.done():
                    try:
                        recognize_task.result()
                    except Exception as rec_task_err:
                        print(f"[{source}] recognize task error: {rec_task_err}")
                    recognize_task = None

                can_recognize = (
                    face_rect is not None
                    and recognize_task is None
                    and state.get("result_samples",0)>0
                    and not state["identified"]
                    and not state.get("recognizing", False)
                    and (time.time() - float(state.get("last_recognize_at", 0.0))) >= RECOGNIZE_MIN_GAP_SECONDS
                )
                if can_recognize:
                    state["recognizing"] = True
                    state["last_recognize_at"] = time.time()
                    frame_snapshot = original_frame.copy()
                    face_rect_snapshot = tuple(face_rect)

                    generation=state.get('session_generation',0)
                    recognition_state=state.copy()
                    async def _run_recognize(frame_data, rect_data):
                        try:
                            from config.database import AsyncSessionLocal
                            async with AsyncSessionLocal() as identity_db:
                                await recognize_face(identity_db,frame_data,rect_data,recognition_state)
                            if state.get('session_generation',0)==generation and recognition_state.get('identified'):
                                for key in ('identified','matched_person','person_id','match_similarity','feature_extracted'):
                                    state[key]=recognition_state.get(key)
                        except Exception as rec_err:
                            print(f"[{source}] identity match unavailable: {type(rec_err).__name__}")
                        finally:
                            state['recognizing']=False

                    recognize_task = asyncio.create_task(_run_recognize(frame_snapshot, face_rect_snapshot))

                if face_rect is not None:
                    remaining_time = None
                    if state["analysis_start_time"] is not None:
                        elapsed = time.time() - state["analysis_start_time"]
                        remaining_time = max(0, state["analysis_duration"] - elapsed)

                    draw_rect=(640-face_rect[0]-face_rect[2],face_rect[1],face_rect[2],face_rect[3]) if source=="local" else face_rect
                    draw_face_recognition(display_frame, state.get("matched_person") or "Unknown",
                                          state.get("match_similarity", 0.0), draw_rect,
                                          is_locked=state["analyzing"], remaining_time=remaining_time)

                    # 录制与分析完成
                    if (state["analyzing"] and not state["analysis_completed"] and
                        state.get("identified") and state.get("person_id") and state.get("matched_person") not in (None,"Unknown", "")):

                        if video_writers[source] is None and state["analysis_start_time"] is not None:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            person_id_str = str(state.get('person_id') or 'unknown')
                            safe_source=re.sub(r"[^A-Za-z0-9_-]","_",source)
                            video_filename = f"{timestamp}_{safe_source}_{person_id_str}.avi"
                            video_full_path = os.path.join(VIDEO_SAVE_DIR, video_filename)
                            fourcc = cv2.VideoWriter_fourcc(*'XVID')

                            video_writers[source] = cv2.VideoWriter(video_full_path, fourcc, RECORD_FPS, (640, 480))
                            video_start_times[source] = time.time()
                            state["current_video_path"] = video_full_path
                            state["video_frame_count"] = 0
                            print(f"[{source}] 【视频录制启动】 {video_full_path}")

                        if video_writers[source] is not None:
                            video_writers[source].write(original_frame)
                            state["video_frame_count"] += 1

                        # ==================== 录制时长到达 → 转码 + 删除AVI ====================
                        if video_start_times[source] is not None:
                            elapsed = time.time() - video_start_times[source]
                            if elapsed >= RECORD_DURATION and state.get("result_samples",0)>0:
                                if video_writers[source]:
                                    video_writers[source].release()
                                    video_writers[source] = None
                                video_start_times[source] = None

                                avi_path = state.get("current_video_path")
                                final_video_path = avi_path

                                # ==================== ffmpeg 转码并删除原始AVI ====================
                                if avi_path and avi_path.endswith('.avi'):
                                    mp4_path = avi_path.replace('.avi', '.mp4')
                                    try:
                                        cmd = [
                                            'ffmpeg', '-i', avi_path,
                                            '-vcodec', 'libx264',
                                            '-acodec', 'aac',
                                            '-pix_fmt', 'yuv420p',
                                            '-movflags', '+faststart',
                                            '-preset', 'fast',
                                            '-crf', '25',
                                            '-y', mp4_path
                                        ]
                                        await asyncio.to_thread(
                                            subprocess.run, cmd, check=True, capture_output=True, timeout=15
                                        )

                                        # 转码成功后删除 .avi 文件，只保留 .mp4
                                        if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 8000:
                                            try:
                                                os.remove(avi_path)
                                                print(f"[{source}] 【清理完成】 已删除原始AVI: {os.path.basename(avi_path)}")
                                            except Exception as del_err:
                                                print(f"[{source}] 【清理警告】 删除AVI失败: {del_err}")
                                        else:
                                            print(f"[{source}] 【清理跳过】 MP4文件无效或过小")

                                        final_video_path = mp4_path
                                        print(f"[{source}] 【ffmpeg 转码成功】 {mp4_path}")

                                    except subprocess.CalledProcessError as e:
                                        error_msg = e.stderr.decode(errors='ignore') if hasattr(e, 'stderr') and e.stderr else str(e)
                                        print(f"[{source}] 【ffmpeg转码失败】: {error_msg}")
                                        final_video_path = avi_path  # 失败时保留avi
                                    except Exception as e:
                                        print(f"[{source}] 【ffmpeg转码异常】: {e}")
                                        final_video_path = avi_path

                                state["current_video_path"] = final_video_path

                                if final_video_path and os.path.exists(final_video_path):
                                    file_size = os.path.getsize(final_video_path)
                                    if file_size > 8000 and not state["analysis_completed"]:
                                        state["analysis_completed"] = True
                                        state["analysis_start_time"] = None

                                        await save_analysis_to_db(query_db, source, state, latest_results[source], final_video_path)

                                        # ====================== 邮件发送任务 ======================
                                        happiness_index = float(latest_results[source].get("e12", 0.0))
                                        person_name = state.get("matched_person")
                                        person_id = state.get("person_id")

                                        if person_id and person_name and person_name != "Unknown" and happiness_index < 60:
                                            print(f"[{source}] 幸福指数 {happiness_index:.1f} < 60，准备发送预警邮件")
                                            state["email_status"] = "sending"
                                            state["email_message"] = "正在发送预警邮件..."
                                            state["email_updated_at"] = time.time()

                                            email_data = {
                                                "matched_person": person_name,
                                                "person_name": person_name,
                                                "person_id": person_id
                                            }

                                            async def protected_send_email():
                                                try:
                                                    sent = await send_analysis_email(
                                                        source=source,
                                                        state=email_data,
                                                        results=latest_results[source],
                                                        video_path=final_video_path
                                                    )
                                                    if sent:
                                                        state["email_status"] = "sent"
                                                        state["email_message"] = "预警邮件发送成功"
                                                        state["email_updated_at"] = time.time()
                                                    else:
                                                        state["email_status"] = "failed"
                                                        state["email_message"] = "邮件未发送，请检查邮件配置或后端日志"
                                                        state["email_updated_at"] = time.time()
                                                except Exception as e:
                                                    state["email_status"] = "failed"
                                                    state["email_message"] = "邮件发送异常，请检查后端日志"
                                                    state["email_updated_at"] = time.time()
                                                    print(f"[{source}] 邮件发送异常: {e}")
                                                    traceback.print_exc()

                                            try:
                                                asyncio.create_task(protected_send_email())
                                            except Exception as task_e:
                                                state["email_status"] = "failed"
                                                state["email_message"] = "邮件任务创建失败，请检查后端日志"
                                                state["email_updated_at"] = time.time()
                                                print(f"[{source}] 创建邮件任务失败: {task_e}")

                                        else:
                                            reason = "未识别到具体人员" if not person_id or person_name == "Unknown" else f"幸福指数 >= 60"
                                            state["email_status"] = "skipped"
                                            state["email_message"] = f"未发送邮件：{reason}"
                                            state["email_updated_at"] = time.time()
                                            print(f"[{source}] 跳过邮件发送：{reason}")

                # 振动分析
                # Recording/archive completion must not stop continuous live scoring.
                if state["analyzing"] and face_rect is not None:
                    try:
                        fps=max(.5,min(60.,fps))
                        analysis_results = await asyncio.to_thread(
                            analyzer.process_frame, original_frame, face_rect=face_rect, fps=fps
                        )
                        state['sample_frames']=len(analyzer.frame_buffer)
                        if analysis_results and all(np.isfinite(float(value)) for value in analysis_results.values()):
                            latest_results[source].update(analysis_results)
                            state['result_samples']=state.get('result_samples',0)+1
                            state['last_result_at']=time.time();state['stage']='analyzing';state['last_error']=None
                    except Exception as e:
                        state['last_error']='本帧计算失败，正在等待有效画面';state['stage']='error'
                if state['analyzing'] and not state['analysis_completed'] and not state.get('identified') and state.get('result_samples',0)>0 and time.time()-state['analysis_start_time']>=RECORD_DURATION:
                    state['analysis_completed']=True


                frame_count += 1
                state["frame_count"] = frame_count

                _, buffer = await asyncio.to_thread(cv2.imencode, '.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 45])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

                await asyncio.sleep(max(0.001, 1/30 - (time.time() - last_frame_time)))
                last_frame_time = time.time()

        except Exception as e:
            print(f"[{source}] 流异常: {e}")
            traceback.print_exc()
        finally:
            if recognize_task is not None and not recognize_task.done():
                recognize_task.cancel()
                try:
                    await recognize_task
                except (Exception,asyncio.CancelledError):
                    pass

            cap.release()
            active_clients[source] = max(0,active_clients[source]-1)
            print(f"[{source}] 客户端断开连接，当前客户端数: {active_clients[source]}")

            if active_clients[source] == 0:
                if global_caps[source]:
                    global_caps[source].release()
                    global_caps[source] = None
                reset_analysis_state(source)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ==================== 其他接口 ====================
@videoController.get("/results", dependencies=[Depends(_require_video_user)])
async def get_analysis_results(
        camera_id: str = Query(default=''),
        source: str = Query(default=''),
        device_id: str = '',
):
    if camera_id or source:
        source = _camera_selection(camera_id, source, device_id).camera_id
    if source and source in stable_state:
        state = stable_state[source]
        return {
            "camera_id": source,
            "stage": state.get('stage','searching'),
            "has_results": state.get('result_samples',0)>0,
            "result_samples": state.get('result_samples',0),
            "sample_frames": state.get('sample_frames',0),
            "stability_progress": state.get('stability_progress',0),
            "observed_fps": state.get('observed_fps',0),
            "identified": bool(state.get('identified')),
            "message": state.get('last_error') or ('持续评估中' if state.get('result_samples',0)>0 else '人脸已稳定，正在积累有效画面' if state['analyzing'] else '已检测到人脸，正在确认画面稳定' if state.get('stage')=='stabilizing' else '未检测到清晰人脸，请调整取景'),
            "analyzing": state["analyzing"],
            "completed": False,
            "recording_completed": state["analysis_completed"],
            "recognizing": state.get("recognizing", False),
            "source": source,
            "results": {k: float(v) for k, v in latest_results[source].items()},
            "matched_person": state["matched_person"] or "Unknown",
            "person_id": state["person_id"] or "未知ID",
            "similarity": state["match_similarity"] or 0.0,
            "video_path": state.get("current_video_path"),
            "email_status": state.get("email_status", "idle"),
            "email_message": state.get("email_message", ""),
            "email_updated_at": state.get("email_updated_at")
        }

    return {
        "camera_id": source or None,
        "analyzing": False,
        "completed": False,
        "recognizing": False,
        "message": "无任何摄像头正在分析",
        "results": {f"e{i}": 0.0 for i in range(1, 15)},
        "matched_person": "未识别",
        "person_id": "未知ID",
        "similarity": 0.0,
        "video_path": None,
        "email_status": "idle",
        "email_message": "",
        "email_updated_at": None
    }


@videoController.post("/reset", dependencies=[Depends(_require_video_user)])
async def reset_analysis(
        camera_id: str = Query(default=''),
        source: str = Query(default=''),
        device_id: str = '',
):
    if not camera_id and not source:
        raise HTTPException(400, '请提供 camera_id 或 source 参数')
    source = _camera_selection(camera_id, source, device_id).camera_id
    if source not in stable_state:
        raise HTTPException(404, '摄像头分析会话不存在')

    # Other consumers may still need the shared capture after an analysis reset.
    if global_caps[source]:
        global_caps[source].release()
        global_caps[source] = None

    reset_analysis_state(source)
    return {"status": "success", "camera_id": source, "message": f"{source} 已重置"}


# Authenticated local raw-frame sharing. Analysis overlays never enter Xiaozhi.

@videoController.get('/shared/frame')
async def shared_camera_frame(
        request: Request,
        camera_id: str = '',
        source: str = 'local',
        device_id: str = ''):
    if request.client is None or request.client.host not in ('127.0.0.1','::1'):
        raise HTTPException(403, '仅允许本机共享摄像头')
    supplied = request.headers.get('X-Camera-Bridge-Key', '')
    if not supplied or not hmac.compare_digest(supplied.encode(), _camera_bridge_key().encode()):
        raise HTTPException(403, '共享摄像头认证失败')
    source = await resolve_registered_camera_source(source, device_id, camera_id=camera_id)
    if source not in camera_hubs:
        raise HTTPException(400, '无效的摄像头来源')
    hub = camera_hubs[source]
    deadline = time.monotonic()+5
    while time.monotonic()<deadline:
        frame, sequence, captured_at = hub.latest()
        if frame is not None:
            ok, jpeg = await asyncio.to_thread(cv2.imencode, '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY),80])
            if ok:
                return Response(jpeg.tobytes(),media_type='image/jpeg',headers={
                    'Cache-Control':'no-store','X-Frame-Sequence':str(sequence),'X-Captured-At':str(captured_at)})
        await asyncio.sleep(.08)
    raise HTTPException(503, hub.error or '摄像头未返回新画面')

@videoController.get('/cameras', dependencies=[Depends(_require_video_user)])
async def camera_catalog():
    xiaozhi_error = ''
    try:
        devices = await _fetch_xiaozhi_devices()
    except HTTPException as exc:
        devices = []
        xiaozhi_error = str(exc.detail)
    cameras = [
        {
            'camera_id': 'local',
            'source': 'local',
            'device_id': '',
            'name': '本机摄像头',
            'online': None,
            'configured': True,
            'detail': 'USB / 内置',
        },
        {
            'camera_id': 'rtsp',
            'source': 'rtsp',
            'device_id': '',
            'name': '海康 RTSP',
            'online': None,
            'configured': bool(RTSP_URL.strip()),
            'detail': '网络视频' if RTSP_URL.strip() else '尚未配置地址',
        },
    ]
    seen = set()
    for device in devices:
        if not isinstance(device, dict):
            continue
        device_id = device.get('device_id')
        if not isinstance(device_id, str) or not device_id or device_id in seen:
            continue
        try:
            camera_id = to_camera_id('xiaozhi', device_id)
        except ValueError:
            continue
        seen.add(device_id)
        cameras.append({
            'camera_id': camera_id,
            'source': 'xiaozhi',
            'device_id': device_id,
            'name': device.get('name') or device_id,
            'online': bool(device.get('online')),
            'configured': True,
            'detail': '在线' if device.get('online') else '未出图',
        })
    try:
        for camera in cameras:
            camera['analysis'] = camera_algorithm_store.get(camera['camera_id'])
    except (ValueError, OSError) as exc:
        raise HTTPException(503, '摄像头算法配置读取失败，请检查配置文件') from exc
    return {
        'cameras': cameras,
        'default_camera_id': 'local',
        'xiaozhi_error': xiaozhi_error,
    }


class CameraAnalysisConfig(BaseModel):
    algorithm_id: str | None = None
    algorithm_ids: list[str] | None = None
    scene: str = Field(min_length=1, max_length=80)
    show_overlay: bool = False


@videoController.get('/algorithms', dependencies=[Depends(_require_video_user)])
async def analysis_algorithms():
    return {'algorithms': ALGORITHMS}


@videoController.put('/cameras/{camera_id}/analysis', dependencies=[Depends(_require_video_user)])
async def save_camera_analysis(camera_id: str, config: CameraAnalysisConfig):
    # Only assign actual registered devices, including currently offline Watchers.
    catalog = await camera_catalog()
    if camera_id not in {camera['camera_id'] for camera in catalog['cameras']}:
        raise HTTPException(404, '摄像头不存在，请刷新摄像头列表')
    try:
        analysis = camera_algorithm_store.save(
            camera_id, config.algorithm_ids if config.algorithm_ids is not None else config.algorithm_id,
            config.scene, config.show_overlay,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(503, '摄像头算法配置保存失败，请检查目录写入权限') from exc
    return {'camera_id': camera_id, 'analysis': analysis}


@videoController.get('/xiaozhi/devices', dependencies=[Depends(_require_video_user)])
async def xiaozhi_camera_devices():
    return {'devices': await _fetch_xiaozhi_devices()}
