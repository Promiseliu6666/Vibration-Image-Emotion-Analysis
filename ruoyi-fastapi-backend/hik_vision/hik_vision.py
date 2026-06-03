# hik_vision/hik_vision.py
import cv2
import numpy as np
import os
import urllib.request
import time
import asyncio
import traceback
import subprocess
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from hik_vision.Vibration_image_algorithm import VibraimageCore
from config.get_db import get_db
from config.database import AsyncSessionLocal
from module_xuzhou.service.people_service import PeopleService
from module_xuzhou.service.video_service import VideoService
from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.entity.vo.analysis_vo import BinhuaAnalysisModel
from algorithm.runtime_service import AlgorithmRuntimeService, algorithm_run_registry
from module_xuzhou.dao.local_algorithm_run_log_dao import LocalAlgorithmRunLogDao
from module_xuzhou.entity.vo.local_algorithm_run_log_vo import LocalAlgorithmRunLogModel
from hik_vision.email_service import send_analysis_email
from hik_vision.local_video_analysis import LocalVideoAnalysisCapabilities

videoController = APIRouter(
    prefix='/video',
    include_in_schema=False
)

# ==================== 摄像头配置 ====================
RTSP_URL = "rtsp://admin:witai515@192.168.3.6:554/main/h264/av_stream"
LOCAL_CAMERA_INDEX = 1
SIMILARITY_THRESHOLD = 0.4

# Dynamic camera config overrides (set from DB-registered cameras)
_camera_config_override: dict = {}
_camera_configs: dict = {}


def get_camera_key(vid_id: int = None, source: str = None) -> str:
    if vid_id is not None:
        return f"vid_{vid_id}"
    return source
def _set_camera_config(local_index: int = None, rtsp_url: str = None):
    """Dynamically override camera configuration from database-registered cameras."""
    if local_index is not None:
        _camera_config_override["local_index"] = local_index
    if rtsp_url is not None:
        _camera_config_override["rtsp_url"] = rtsp_url


async def _resolve_source_from_db(query_db: AsyncSession, vid_id: int) -> str:
    """Resolve a database camera ID to a source type ('local' or 'rtsp') and set camera config."""
    from module_xuzhou.entity.do.video_do import XuzhouVideo
    from sqlalchemy import select

    result = await query_db.execute(select(XuzhouVideo).where(XuzhouVideo.vid_id == vid_id))
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"摄像头不存在: vid_id={vid_id}")

    vid_type = (camera.vid_type or "").lower()
    vid_uri = (camera.vid_uri or "").strip()
    camera_key = get_camera_key(vid_id=vid_id)

    if vid_type == "local":
        try:
            local_index = int(vid_uri)
        except (ValueError, TypeError):
            local_index = 1
        _camera_configs[camera_key] = {"source": "local", "local_index": local_index}
        return "local"

    _camera_configs[camera_key] = {"source": "rtsp", "rtsp_url": vid_uri}
    return "rtsp"

# ==================== DNN 模型 ====================
MODEL_PROTO = os.path.join("algorithm", "model", "face_detection", "v1", "deploy.prototxt")
MODEL_WEIGHTS = os.path.join("algorithm", "model", "face_detection", "v1", "res10_300x300_ssd_iter_140000.caffemodel")

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

video_ffmpeg_procs = {}  # ffmpeg 子进程（直接编码 H.264，浏览器可播放）
video_start_times = {}

RECORD_FPS = 20.0  # 与 generate() 中 target_fps(analyzing)=20 一致
RECORD_DURATION = 10.0

# ==================== 优化参数 ====================
FACE_DETECT_INTERVAL = 10
RECOGNIZE_INTERVAL = 30
ANALYSIS_INTERVAL = 10
STABLE_FRAMES_REQUIRED = 15
TOLERANCE = 60
LOST_CHECK_INTERVAL = 20
LOST_FACE_THRESHOLD = 3        # 连续丢脸次数阈值，减少误触发
RECOGNIZE_TIMEOUT = 3.0
RECOGNIZE_MIN_GAP_SECONDS = 2.5



def get_camera_cap(source: str, camera_key: str = None):
    config = _camera_configs.get(camera_key or source, {})
    if source == "local":
        local_index = config.get("local_index", _camera_config_override.get("local_index", LOCAL_CAMERA_INDEX))
        print(f"[视频流] 使用本地摄像头 index={local_index}")
        cap = cv2.VideoCapture(local_index, cv2.CAP_DSHOW)
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
        rtsp_url = config.get("rtsp_url", _camera_config_override.get("rtsp_url", RTSP_URL))
        if not rtsp_url.strip():
            raise HTTPException(status_code=500, detail="RTSP地址未配置")
        print(f"[视频流] 使用RTSP摄像头 {rtsp_url}")

        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|timeout;5000000'

        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
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


global_caps = {}
active_clients = {}
latest_results = {}
stable_state = {}


def _new_analysis_state() -> dict:
    return {
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
        "lost_face_count": 0,
        "reset_at": 0.0,
        "face_compare_semaphore": asyncio.Semaphore(1),
        "current_run_log_id": None,
    }


def ensure_camera_state(camera_key: str) -> dict:
    global_caps.setdefault(camera_key, None)
    active_clients.setdefault(camera_key, 0)
    latest_results.setdefault(camera_key, {f"e{i}": 0.0 for i in range(1, 15)})
    stable_state.setdefault(camera_key, _new_analysis_state())
    video_ffmpeg_procs.setdefault(camera_key, None)
    video_start_times.setdefault(camera_key, None)
    return stable_state[camera_key]


async def save_analysis_to_db(db: AsyncSession, source: str, state: dict, results: dict, video_path: str = None):
    try:
        person_id = state.get("person_id") or None
        person_name = state.get("matched_person") or "Unknown"

        # 仅保存已识别到真实人员的记录
        if not person_id or person_name == "Unknown":
            print(f"[{source}] 【跳过保存】 人员未识别 (person_name={person_name}, person_id={person_id})")
            return None

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


async def persist_analysis_result(source: str, state: dict, results: dict, video_path: str = None):
    try:
        async with AsyncSessionLocal() as db:
            return await save_analysis_to_db(db, source, state, results, video_path)
    except asyncio.CancelledError:
        # 任务被取消时静默退出，不触发 Session 回滚异常
        pass
    except Exception as e:
        print(f"[{source}] persist_analysis_result 异常: {e}")


def reset_analysis_state(camera_key: str):
    if camera_key in stable_state:
        state = stable_state[camera_key]

        # 清理未完成的录制视频（分析已完成的不删——已由 finalize_analysis 处理）
        if not state.get("analysis_completed"):
            orphan_video = state.get("current_video_path")
            if orphan_video and os.path.exists(orphan_video):
                try:
                    os.remove(orphan_video)
                    print(f"[{camera_key}] 删除未完成视频: {os.path.basename(orphan_video)}")
                except Exception as e:
                    print(f"[{camera_key}] 删除视频失败: {e}")

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
            "last_recognize_at": 0.0,
            "reset_at": time.time(),  # 冷却时间戳，防止立即重新分析
        })

        if video_ffmpeg_procs.get(camera_key) is not None:
            try:
                proc = video_ffmpeg_procs[camera_key]
                if proc.poll() is None:
                    proc.stdin.close()
                    proc.wait(timeout=5)
            except Exception as e:
                print(f"[{camera_key}] ffmpeg 关闭异常: {e}")
            video_ffmpeg_procs[camera_key] = None
        video_start_times[camera_key] = None

        latest_results[camera_key] = {f"e{i}": 0.0 for i in range(1, 15)}


def get_recognition_face_rect(face_rect: tuple | None, state: dict) -> tuple | None:
    return face_rect or state.get("last_detected_rect")


def can_schedule_face_recognition(
    recognition_rect: tuple | None,
    state: dict,
    local_capabilities: LocalVideoAnalysisCapabilities,
    analysis_count: int,
    now: float,
) -> bool:
    return (
        recognition_rect is not None
        and local_capabilities.enable_face_recognition
        and not state["identified"]
        and not state.get("recognizing", False)
        and analysis_count % RECOGNIZE_INTERVAL == 0
        and (now - float(state.get("last_recognize_at", 0.0))) >= RECOGNIZE_MIN_GAP_SECONDS
    )


def get_display_face_rect(source: str, rect: tuple, frame_width: int) -> tuple:
    if source != "local" or rect is None:
        return rect
    x, y, w, h = rect
    return frame_width - x - w, y, w, h


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


def detect_face(frame: np.ndarray):
    try:
        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        face_net.setInput(blob)
        detections = face_net.forward()

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


def prepare_face_crop(frame: np.ndarray, face_rect: tuple) -> Optional[np.ndarray]:
    """
    Crop face region, downscale it for faster inference, and convert to RGB.
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
        else:
            return None

    h, w = frame.shape[:2]
    max_side = max(h, w)
    if max_side > 320:
        scale = 320.0 / max_side
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

    return frame




async def apply_recognition_match(
    name: str,
    face_rect: tuple,
    state: dict,
    analyzer,
    local_capabilities: LocalVideoAnalysisCapabilities,
):
    if not name or name == "Unknown":
        return
    state["locked_rect"] = face_rect


async def start_happiness_analysis_if_ready(
    state: dict,
    analyzer,
    local_capabilities: LocalVideoAnalysisCapabilities,
):
    if not local_capabilities.enable_happiness_analysis or state["analyzing"]:
        return
    # cooldown after reset — prevent immediate restart loop
    if state.get("reset_at") and time.time() - state["reset_at"] < 3.0:
        return
    face_rect = state.get("locked_rect") or state.get("last_detected_rect")
    if face_rect is None:
        return
    state["locked_rect"] = tuple(face_rect)
    state["analyzing"] = True
    state["analysis_start_time"] = time.time()
    await asyncio.to_thread(analyzer.reset)


async def recognize_face(db: AsyncSession, frame: np.ndarray, face_rect: tuple, state: dict):
    try:
        face_crop = await asyncio.to_thread(prepare_face_crop, frame, face_rect)
        if face_crop is None:
            state["person_id"] = ""
            state["matched_person"] = "Unknown"
            state["identified"] = False
            return "Unknown", 0.0

        async with AsyncSessionLocal() as recognition_db:
            compare_results = [{}]
            async with state["face_compare_semaphore"]:
                compare_results = await asyncio.wait_for(
                    PeopleService.face_compare_by_face_crop_services(
                        recognition_db, face_crop, group_id=1, threshold=SIMILARITY_THRESHOLD
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
                        result = await recognition_db.execute(
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
                        await recognition_db.rollback()

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


# ==================== 主视频流函数（已包含ffmpeg转码后删除AVI功能） ====================
@videoController.get("/feed/analysis")
async def generate_video_stream(
        source: str = Query(default=None),
        vid_id: int = Query(default=None),
        query_db: AsyncSession = Depends(get_db)
):
    if vid_id is not None:
        source = await _resolve_source_from_db(query_db, vid_id)
    elif source not in ["local", "rtsp"]:
        raise HTTPException(status_code=400, detail="无效的source参数")

    camera_key = get_camera_key(vid_id=vid_id, source=source)
    video_detail = None
    local_analysis_enabled = source in ["local", "rtsp"] and vid_id is None
    local_capabilities = (
        LocalVideoAnalysisCapabilities.default_enabled()
        if local_analysis_enabled
        else LocalVideoAnalysisCapabilities(
            enable_local_worker=False,
            enable_face_detection=False,
            enable_face_recognition=False,
            enable_happiness_analysis=False,
        )
    )
    _local_algorithm_code = AlgorithmRuntimeService.LOCAL_REALTIME_ALGORITHM_CODE
    _local_algorithm_name = AlgorithmRuntimeService.LOCAL_REALTIME_ALGORITHM_NAME
    if vid_id is not None:
        video_detail = await VideoService.video_detail_services(query_db, vid_id)
        local_capabilities = LocalVideoAnalysisCapabilities.from_video_detail(video_detail)
        local_analysis_enabled = local_capabilities.enable_local_worker
        local_bindings = [
            b for b in AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)
            if b.runtime_type == "local"
        ]
        for binding in local_bindings:
            algorithm_run_registry.start_run(binding)
        if local_bindings:
            _local_algorithm_code = local_bindings[0].algorithm_code
            _local_algorithm_name = local_bindings[0].algorithm_name
    print(
        f"[实时分析] camera_key={camera_key}, source={source}, vid_id={vid_id}, "
        f"capabilities={local_capabilities}"
    )
    state = ensure_camera_state(camera_key)
    active_clients[camera_key] += 1
    print(f"[{camera_key}] 新客户端连接，当前活跃客户端数: {active_clients[camera_key]}")

    if global_caps[camera_key] is None:
        global_caps[camera_key] = get_camera_cap(source, camera_key)

    cap = global_caps[camera_key]
    analyzer = VibraimageCore()
    analyzer.halo_params["ACCUMULATE_FRAMES"] = 5

    # 共享帧缓冲：analysis_worker 通过此变量获取最新帧（Python 引用赋值是原子的）
    _shared_frame = None
    _analysis_task = None
    _bg_tasks: set = set()  # 跟踪所有后台异步任务，确保清理

    def _track_task(t: asyncio.Task) -> asyncio.Task:
        _bg_tasks.add(t)
        t.add_done_callback(_bg_tasks.discard)
        return t

    async def _write_run_log(camera_id: int | None, code: str, name: str, st: str,
                             run_log_id: int | None = None, err: str = None) -> int | None:
        if camera_id is None:
            return None
        try:
            async with AsyncSessionLocal() as log_db:
                if run_log_id is None:
                    model = LocalAlgorithmRunLogModel(
                        vid_id=camera_id, algorithm_code=code, algorithm_name=name,
                        status=st, start_time=datetime.now(),
                    )
                    new_id = await LocalAlgorithmRunLogDao.create(log_db, model)
                    await log_db.commit()
                    return new_id
                else:
                    await LocalAlgorithmRunLogDao.update_status(
                        log_db, run_log_id, st, end_time=datetime.now(), error_message=err,
                    )
                    await log_db.commit()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        return None


    async def analysis_worker():
        """后台独立任务：处理所有耗时计算（人脸检测/识别/振动分析/录制），不阻塞 MJPEG 流"""
        analysis_count = 0
        recognize_task = None

        # 写入运行记录
        if local_analysis_enabled and vid_id is not None:
            state["current_run_log_id"] = await _write_run_log(
                vid_id, _local_algorithm_code, _local_algorithm_name, "running"
            )

        try:
            while active_clients[camera_key] > 0:
                frame = _shared_frame
                if frame is None:
                    await asyncio.sleep(0.02)
                    continue

                analysis_count += 1

                # ---- 人脸检测 + 稳定性追踪 ----
                face_rect = None
                if state["analyzing"] and state["locked_rect"] is not None:
                    face_rect = state["locked_rect"]
                elif local_capabilities.enable_face_detection and analysis_count % FACE_DETECT_INTERVAL == 0:
                    face_rect = await asyncio.to_thread(detect_face, frame)
                    if face_rect is not None:
                        state["last_detected_rect"] = face_rect
                        x, y, w, h = face_rect
                        center = (x + w // 2, y + h // 2)
                        size = (w, h)
                        if state["prev_center"] is not None:
                            center_dist = np.linalg.norm(np.array(center) - np.array(state["prev_center"]))
                            size_dist = np.linalg.norm(np.array(size) - np.array(state["prev_size"]))
                            if center_dist < TOLERANCE and size_dist < TOLERANCE:
                                state["stable_count"] += 1
                            else:
                                state["stable_count"] = 0
                        else:
                            state["stable_count"] = 1
                        state["prev_center"] = center
                        state["prev_size"] = size

                # ---- 分析中：人脸丢失检测（需连续丢失 N 次才重置） ----
                if (state["analyzing"] and local_capabilities.enable_face_detection and
                    analysis_count % LOST_CHECK_INTERVAL == 0):
                    current_detect = await asyncio.to_thread(detect_face, frame)
                    if current_detect is None:
                        state["lost_face_count"] = state.get("lost_face_count", 0) + 1
                        if state["lost_face_count"] >= LOST_FACE_THRESHOLD:
                            print(f"[{source}] 人脸连续丢失 {state['lost_face_count']} 次，重置")
                            reset_analysis_state(camera_key)
                            await asyncio.to_thread(analyzer.reset)
                            face_rect = None
                    else:
                        state["lost_face_count"] = 0

                # ---- 人脸识别任务管理 ----
                if recognize_task is not None and recognize_task.done():
                    try:
                        recognize_task.result()
                    except Exception:
                        pass
                    recognize_task = None

                recognition_rect = get_recognition_face_rect(face_rect, state)
                can_recognize = can_schedule_face_recognition(
                    recognition_rect=recognition_rect,
                    state=state,
                    local_capabilities=local_capabilities,
                    analysis_count=analysis_count,
                    now=time.time(),
                )
                if can_recognize:
                    print(f"[人脸识别调度] camera_key={camera_key}, rect={recognition_rect}, analysis_count={analysis_count}")
                    state["recognizing"] = True
                    state["last_recognize_at"] = time.time()
                    frame_snap = frame.copy()
                    rect_snap = tuple(recognition_rect)

                    async def _do_recognize(fr, rc):
                        try:
                            name, _sim = await recognize_face(query_db, fr, rc, state)
                            await apply_recognition_match(name, rc, state, analyzer, local_capabilities)
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass
                        finally:
                            state["recognizing"] = False

                    recognize_task = _track_task(asyncio.create_task(_do_recognize(frame_snap, rect_snap)))

                await start_happiness_analysis_if_ready(state, analyzer, local_capabilities)

                # ---- 振动分析 ----
                if (state["analyzing"] and not state["analysis_completed"] and
                    analysis_count % ANALYSIS_INTERVAL == 0 and
                    local_capabilities.enable_happiness_analysis):
                    try:
                        results = await asyncio.to_thread(
                            analyzer.process_frame, frame, face_rect=face_rect, fps=30
                        )
                        if results:
                            latest_results[camera_key].update(results)
                    except Exception:
                        pass

                # ---- 视频录制管理 ----
                if (state["analyzing"] and not state["analysis_completed"] and
                    local_capabilities.enable_happiness_analysis):

                    if video_ffmpeg_procs[camera_key] is None and state["analysis_start_time"] is not None:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        person_id_str = str(state.get('person_id') or 'unknown')
                        video_filename = f"{timestamp}_{source}_{person_id_str}.mp4"
                        video_full_path = os.path.join(VIDEO_SAVE_DIR, video_filename)

                        # 使用 ffmpeg 直接录制 H.264（浏览器可播放）
                        ffmpeg_cmd = [
                            "ffmpeg", "-y",
                            "-f", "rawvideo",
                            "-pix_fmt", "bgr24",
                            "-s", "640x480",
                            "-r", str(int(RECORD_FPS)),
                            "-i", "-",
                            "-c:v", "libx264",
                            "-preset", "ultrafast",
                            "-crf", "28",
                            "-an",
                            "-movflags", "+faststart",
                            "-loglevel", "error",
                            video_full_path,
                        ]
                        try:
                            proc = subprocess.Popen(
                                ffmpeg_cmd,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,
                            )
                            video_ffmpeg_procs[camera_key] = proc
                            video_start_times[camera_key] = time.time()
                            state["current_video_path"] = video_full_path
                            state["video_frame_count"] = 0
                            print(f"[{source}] 【视频录制启动(H.264)】 {video_full_path}")
                        except FileNotFoundError:
                            print(f"[{source}] 【错误】 ffmpeg 未安装，无法录制视频")
                        except Exception as e:
                            print(f"[{source}] 【错误】 启动 ffmpeg 录制失败: {e}")

                    # 录制时长到达 → 关闭 ffmpeg 并保存到数据库
                    # 帧写入在 generate() 协程中完成（精确 20fps）
                    if video_start_times[camera_key] is not None:
                        elapsed = time.time() - video_start_times[camera_key]
                        if elapsed >= RECORD_DURATION:
                            proc_to_close = video_ffmpeg_procs.get(camera_key)
                            if proc_to_close is not None and proc_to_close.poll() is None:
                                try:
                                    proc_to_close.stdin.close()
                                except Exception:
                                    pass
                                try:
                                    proc_to_close.wait(timeout=10)
                                except subprocess.TimeoutExpired:
                                    proc_to_close.kill()
                                    proc_to_close.wait()
                            video_ffmpeg_procs[camera_key] = None
                            video_start_times[camera_key] = None

                            mp4_path = state.get("current_video_path")
                            state["analysis_completed"] = True
                            state["analysis_start_time"] = None

                            final_results = dict(latest_results[camera_key])

                            async def finalize_analysis():
                                try:
                                    await _finalize_impl()
                                except Exception as e:
                                    print(f"[{source}] finalize_analysis 异常: {e}")
                                    traceback.print_exc()

                            async def _finalize_impl():
                                nonlocal mp4_path
                                if not mp4_path or not os.path.exists(mp4_path) or os.path.getsize(mp4_path) <= 8000:
                                    print(f"[{source}] 【警告】 视频文件无效或太小，跳过DB保存")
                                    return

                                # 从 state 实时读取匹配结果（face loop 可能异步更新了）
                                save_person_name = state.get("matched_person")
                                save_person_id = state.get("person_id")

                                # 仅识别到真实人员时才保存视频和分析记录
                                if not save_person_name or save_person_name == "Unknown" or not save_person_id:
                                    print(
                                        f"[{source}] 【跳过】 未识别到人员 "
                                        f"(person_name={save_person_name}, person_id={save_person_id})，"
                                        f"删除视频文件 {mp4_path}"
                                    )
                                    try:
                                        os.remove(mp4_path)
                                    except Exception:
                                        pass
                                    state["current_video_path"] = None
                                    return

                                # 用真实人员ID重命名视频文件
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                renamed_path = os.path.join(
                                    VIDEO_SAVE_DIR,
                                    f"{timestamp}_{source}_{save_person_id}.mp4"
                                )
                                try:
                                    os.rename(mp4_path, renamed_path)
                                    mp4_path = renamed_path
                                    print(f"[{source}] 视频已重命名: {os.path.basename(renamed_path)}")
                                except Exception as e:
                                    print(f"[{source}] 视频重命名失败: {e}")

                                state["current_video_path"] = mp4_path
                                await persist_analysis_result(source, state, final_results, mp4_path)

                                # 标记本轮分析完成，并为下一轮创建新的运行记录
                                if state.get("current_run_log_id") is not None:
                                    await _write_run_log(
                                        vid_id, _local_algorithm_code, _local_algorithm_name,
                                        "completed", run_log_id=state["current_run_log_id"],
                                    )
                                    state["current_run_log_id"] = await _write_run_log(
                                        vid_id, _local_algorithm_code, _local_algorithm_name, "running",
                                    )

                                # 低幸福指数预警邮件（在后台任务内直接 sleep 后发送，避免嵌套 create_task）
                                happiness_index = float(final_results.get("e12", 0.0))
                                if save_person_id and save_person_name and save_person_name != "Unknown" and happiness_index < 60:
                                    await asyncio.sleep(10)
                                    try:
                                        await send_analysis_email(
                                            source=source,
                                            state={"matched_person": save_person_name, "person_name": save_person_name, "person_id": save_person_id},
                                            results=final_results,
                                            video_path=mp4_path
                                        )
                                    except Exception:
                                        pass

                            _track_task(asyncio.create_task(finalize_analysis()))

                state["frame_count"] = analysis_count
                await asyncio.sleep(0.03)

        except Exception as e:
            print(f"[{source}] analysis_worker 异常: {e}")
            traceback.print_exc()
            if local_analysis_enabled and state.get("current_run_log_id") is not None:
                await _write_run_log(
                    vid_id, _local_algorithm_code, _local_algorithm_name,
                    "failed", run_log_id=state["current_run_log_id"], err=str(e),
                )
                state["current_run_log_id"] = None
        finally:
            if recognize_task is not None and not recognize_task.done():
                recognize_task.cancel()

    async def generate():
        """MJPEG 流生成器：只负责取帧 → 画叠加层 → 编码 → 推流，不做任何耗时操作"""
        nonlocal _shared_frame
        last_frame_time = time.time()
        try:
            while active_clients[camera_key] > 0:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                original_frame = cv2.resize(frame, (640, 480))
                display_frame = original_frame.copy()
                if source == 'local':
                    display_frame = cv2.flip(display_frame, 1)

                # 将原始帧给分析 worker
                _shared_frame = original_frame

                # 视频录制：帧写入（generate 精确 20fps，避免 analysis_worker 丢帧导致视频加速）
                if video_ffmpeg_procs[camera_key] is not None:
                    proc = video_ffmpeg_procs[camera_key]
                    if proc.poll() is None:
                        try:
                            proc.stdin.write(original_frame.tobytes())
                            proc.stdin.flush()
                        except (BrokenPipeError, OSError):
                            video_ffmpeg_procs[camera_key] = None

                # 画人脸框和识别信息（只读 state，不等待任何耗时操作）
                face_rect = None
                if state["analyzing"] and state["locked_rect"] is not None:
                    face_rect = state["locked_rect"]
                elif state.get("last_detected_rect") is not None:
                    face_rect = state["last_detected_rect"]

                if face_rect is not None:
                    remaining_time = None
                    if state["analysis_start_time"] is not None:
                        elapsed = time.time() - state["analysis_start_time"]
                        remaining_time = max(0, state["analysis_duration"] - elapsed)
                    display_rect = get_display_face_rect(source, face_rect, display_frame.shape[1])
                    draw_face_recognition(display_frame, state.get("matched_person") or "Unknown",
                                          state.get("match_similarity", 0.0), display_rect,
                                          is_locked=state["analyzing"], remaining_time=remaining_time)

                # JPEG 编码 + 推流
                _, buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 45])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

                target_fps = 20 if state["analyzing"] else 30
                await asyncio.sleep(max(0.001, 1 / target_fps - (time.time() - last_frame_time)))
                last_frame_time = time.time()

        except Exception as e:
            print(f"[{source}] 流异常: {e}")
            traceback.print_exc()
        finally:
            active_clients[camera_key] -= 1
            print(f"[{source}] 客户端断开连接，当前客户端数: {active_clients[camera_key]}")

            # 取消所有后台任务（analysis_worker, finalize_analysis, recognize 等）
            for task in list(_bg_tasks):
                if not task.done():
                    task.cancel()
            if _analysis_task is not None and not _analysis_task.done():
                _analysis_task.cancel()

            # 等待后台任务结束（最多 5 秒），避免 DB 连接泄漏
            # 使用 asyncio.shield 确保即使客户端断开连接（generator 被取消），
            # 后台任务也能被正确等待和清理
            all_tasks = list(_bg_tasks)
            if _analysis_task is not None:
                all_tasks.append(_analysis_task)
            for task in all_tasks:
                try:
                    await asyncio.shield(asyncio.wait_for(task, timeout=5))
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                    pass

            if active_clients[camera_key] == 0:
                if global_caps[camera_key]:
                    global_caps[camera_key].release()
                    global_caps[camera_key] = None
                if vid_id is not None:
                    algorithm_run_registry.stop_camera_runs(vid_id)
                if state.get("current_run_log_id") is not None:
                    try:
                        await asyncio.shield(_write_run_log(
                            vid_id, _local_algorithm_code, _local_algorithm_name,
                            "stopped", run_log_id=state["current_run_log_id"],
                        ))
                    except Exception:
                        pass
                reset_analysis_state(camera_key)

    # 启动后台分析 worker（独立 asyncio Task，不阻塞 MJPEG 流）
    if local_analysis_enabled:
        _analysis_task = _track_task(asyncio.create_task(analysis_worker()))

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ==================== 其他接口 ====================
@videoController.get("/results")
async def get_analysis_results(
    source: str = Query(None),
    vid_id: int = Query(None),
    query_db: AsyncSession = Depends(get_db),
):
    if vid_id is not None:
        source = await _resolve_source_from_db(query_db, vid_id)
    camera_key = get_camera_key(vid_id=vid_id, source=source)
    if camera_key in stable_state:
        state = stable_state[camera_key]
        return {
            "analyzing": state["analyzing"],
            "completed": state["analysis_completed"],
            "recognizing": state.get("recognizing", False),
            "source": source,
            "camera_key": camera_key,
            "results": {k: float(v) for k, v in latest_results[camera_key].items()},
            "matched_person": state["matched_person"] or "Unknown",
            "person_id": state["person_id"] or "未知ID",
            "similarity": state["match_similarity"] or 0.0,
            "video_path": state.get("current_video_path")
        }

    return {
        "analyzing": False,
        "completed": False,
        "recognizing": False,
        "message": "无任何摄像头正在分析",
        "results": {f"e{i}": 0.0 for i in range(1, 15)},
        "matched_person": "未识别",
        "person_id": "未知ID",
        "similarity": 0.0,
        "video_path": None
    }


@videoController.get("/reset")
async def reset_analysis(
    source: str = Query(default=None, description="local 或 rtsp"),
    vid_id: int = Query(default=None),
    query_db: AsyncSession = Depends(get_db),
):
    if vid_id is not None:
        source = await _resolve_source_from_db(query_db, vid_id)
    elif source not in ["local", "rtsp"]:
        raise HTTPException(status_code=400, detail="无效的source参数")

    camera_key = get_camera_key(vid_id=vid_id, source=source)
    ensure_camera_state(camera_key)
    active_clients[camera_key] = 0
    if global_caps[camera_key]:
        global_caps[camera_key].release()
        global_caps[camera_key] = None

    reset_analysis_state(camera_key)
    if vid_id is not None:
        algorithm_run_registry.stop_camera_runs(vid_id)
    return {"status": "success", "message": f"{camera_key} 已重置"}


@videoController.get("/camera-list", summary="获取注册的摄像头列表")
async def list_registered_cameras(query_db: AsyncSession = Depends(get_db)):
    try:
        from module_xuzhou.entity.do.video_do import XuzhouVideo
        from sqlalchemy import select

        result = await query_db.execute(select(XuzhouVideo).order_by(XuzhouVideo.vid_id))
        cameras = result.scalars().all()

        rows = []
        for cam in cameras:
            rows.append({
                "vidId": cam.vid_id,
                "vidName": cam.vid_name or f"摄像头{cam.vid_id}",
                "vidSerial": cam.vid_serial or "",
                "vidType": cam.vid_type or "local",
                "vidUri": cam.vid_uri or "",
                "vidSceneName": cam.vid_scene_name or "",
            })
        print(f"[camera-list] 返回{len(rows)}个注册摄像头")
        return rows
    except Exception as e:
        print(f"[camera-list] 错误: {e}")
        traceback.print_exc()
        return []
