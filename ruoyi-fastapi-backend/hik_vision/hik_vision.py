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
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from hik_vision.Vibration_image_algorithm import VibraimageCore
from config.get_db import get_db
from module_xuzhou.service.people_service import PeopleService
from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.entity.vo.analysis_vo import BinhuaAnalysisModel

from hik_vision.email_service import send_analysis_email

videoController = APIRouter(
    prefix='/video',
    include_in_schema=False
)

# ==================== 摄像头配置 ====================
RTSP_URL = "rtsp://admin:witai515@192.168.3.6:554/main/h264/av_stream"
LOCAL_CAMERA_INDEX = 0
SIMILARITY_THRESHOLD = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.25"))

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


def get_camera_cap(source: str):
    if source == "local":
        print("[视频流] 使用本地摄像头")
        camera_indices = list(dict.fromkeys([LOCAL_CAMERA_INDEX, 0, 1, 2]))

        for camera_index in camera_indices:
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                print(f"[视频流] 本地摄像头索引 {camera_index} 无法打开")
                continue

            start_time = time.time()
            while time.time() - start_time < 3:
                ret, _ = cap.read()
                if ret:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    print(f"[视频流] 本地摄像头索引 {camera_index} 已就绪")
                    return cap
                time.sleep(0.05)

            cap.release()
            print(f"[视频流] 本地摄像头索引 {camera_index} 无法读取画面")

        raise HTTPException(status_code=500, detail="本地摄像头无法打开")

    elif source == "rtsp":
        if not RTSP_URL.strip():
            raise HTTPException(status_code=500, detail="RTSP地址未配置")
        print(f"[视频流] 使用RTSP摄像头 {RTSP_URL}")

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
        "last_recognize_at": 0.0
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
        "last_recognize_at": 0.0
    }
}


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
            "last_recognize_at": 0.0
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
    if max_side > 640:
        scale = 640.0 / max_side
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

    _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return base64.b64encode(buffer).decode('utf-8')


async def recognize_face(db: AsyncSession, frame: np.ndarray, face_rect: tuple, state: dict):
    try:
        # PaddleX performs its own face detection and cropping. Passing the
        # full frame avoids cropping an already-tight face region twice.
        current_image_base64 = await asyncio.to_thread(encode_face_image, frame, None)

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


# ==================== 主视频流函数（已包含ffmpeg转码后删除AVI功能） ====================
@videoController.get("/feed/analysis")
async def generate_video_stream(
        source: str = Query(default='local'),
        query_db: AsyncSession = Depends(get_db)
):
    if source not in ["local", "rtsp"]:
        raise HTTPException(status_code=400, detail="无效的source参数")

    active_clients[source] += 1
    print(f"[{source}] 新客户端连接，当前活跃客户端数: {active_clients[source]}")

    if global_caps[source] is None:
        global_caps[source] = get_camera_cap(source)

    cap = global_caps[source]
    state = stable_state[source]
    analyzer = VibraimageCore()
    analyzer.halo_params["ACCUMULATE_FRAMES"] = 5

    async def generate():
        frame_count = 0
        last_frame_time = time.time()
        recognize_task = None

        try:
            while active_clients[source] > 0:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                original_frame = cv2.resize(frame, (640, 480))
                display_frame = original_frame.copy()
                if source == 'local':
                    display_frame = cv2.flip(display_frame, 1)
                # Detection, recognition, and vibration analysis must share the
                # same orientation and pixel coordinate system.
                processing_frame = display_frame

                face_rect = None
                should_detect = (frame_count % FACE_DETECT_INTERVAL == 0)

                if state["analyzing"] and state["locked_rect"] is not None:
                    face_rect = state["locked_rect"]
                elif should_detect:
                    face_rect = await asyncio.to_thread(detect_face, display_frame)
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

                if state["analyzing"] and frame_count % LOST_CHECK_INTERVAL == 0:
                    current_detect = await asyncio.to_thread(detect_face, display_frame)
                    if current_detect is None:
                        print(f"[{source}] 人脸丢失，重置")
                        reset_analysis_state(source)
                        analyzer.reset()
                        face_rect = None

                # 人脸识别
                if recognize_task is not None and recognize_task.done():
                    try:
                        recognize_task.result()
                    except Exception as rec_task_err:
                        print(f"[{source}] recognize task error: {rec_task_err}")
                    recognize_task = None

                can_recognize = (
                    face_rect is not None
                    and not state["identified"]
                    and not state["analyzing"]
                    and not state.get("recognizing", False)
                    and frame_count % RECOGNIZE_INTERVAL == 0
                    and (time.time() - float(state.get("last_recognize_at", 0.0))) >= RECOGNIZE_MIN_GAP_SECONDS
                )
                if can_recognize:
                    state["recognizing"] = True
                    state["last_recognize_at"] = time.time()
                    frame_snapshot = processing_frame.copy()
                    face_rect_snapshot = tuple(face_rect)

                    async def _run_recognize(frame_data, rect_data):
                        try:
                            name, _similarity = await recognize_face(query_db, frame_data, rect_data, state)
                            if name and name != "Unknown":
                                state["locked_rect"] = rect_data
                                state["analyzing"] = True
                                state["analysis_start_time"] = time.time()
                                analyzer.reset()
                        except Exception as rec_err:
                            print(f"[{source}] recognize failed: {rec_err}")
                        finally:
                            state["recognizing"] = False

                    recognize_task = asyncio.create_task(_run_recognize(frame_snapshot, face_rect_snapshot))

                if False and (face_rect is not None and not state["identified"] and frame_count % RECOGNIZE_INTERVAL == 0):
                    name, similarity = await recognize_face(query_db, frame, face_rect, state)
                    if name and name != "Unknown":
                        print(f"[{source}] 识别到具体人员: {name}，开始锁定分析")
                        state["locked_rect"] = face_rect
                        state["analyzing"] = True
                        state["analysis_start_time"] = time.time()
                        analyzer.reset()

                if face_rect is not None:
                    remaining_time = None
                    if state["analysis_start_time"] is not None:
                        elapsed = time.time() - state["analysis_start_time"]
                        remaining_time = max(0, state["analysis_duration"] - elapsed)

                    draw_face_recognition(display_frame, state.get("matched_person") or "Unknown",
                                          state.get("match_similarity", 0.0), face_rect,
                                          is_locked=state["analyzing"], remaining_time=remaining_time)

                    # 录制与分析完成
                    if (state["analyzing"] and not state["analysis_completed"] and
                        state.get("matched_person") != "Unknown"):

                        if video_writers[source] is None and state["analysis_start_time"] is not None:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            person_id_str = str(state.get('person_id') or 'unknown')
                            video_filename = f"{timestamp}_{source}_{person_id_str}.avi"
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
                            if elapsed >= RECORD_DURATION:
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

                                            email_data = {
                                                "matched_person": person_name,
                                                "person_name": person_name,
                                                "person_id": person_id
                                            }

                                            async def protected_send_email():
                                                try:
                                                    await send_analysis_email(
                                                        source=source,
                                                        state=email_data,
                                                        results=latest_results[source],
                                                        video_path=final_video_path
                                                    )
                                                except Exception as e:
                                                    print(f"[{source}] 邮件发送异常: {e}")
                                                    traceback.print_exc()

                                            try:
                                                email_coro = protected_send_email()
                                                shielded = asyncio.shield(email_coro)
                                                asyncio.create_task(shielded)
                                            except Exception as task_e:
                                                print(f"[{source}] 创建邮件任务失败: {task_e}")

                                        else:
                                            reason = "未识别到具体人员" if not person_id or person_name == "Unknown" else f"幸福指数 >= 60"
                                            print(f"[{source}] 跳过邮件发送：{reason}")

                # 振动分析
                if (state["analyzing"] and not state["analysis_completed"] and
                    frame_count % ANALYSIS_INTERVAL == 0 and state.get('matched_person') != "Unknown"):
                    try:
                        fps = cap.get(cv2.CAP_PROP_FPS) or 30
                        analysis_results = await asyncio.to_thread(
                            analyzer.process_frame, processing_frame, face_rect=face_rect, fps=fps
                        )
                        if analysis_results:
                            latest_results[source].update(analysis_results)
                    except Exception as e:
                        pass

                frame_count += 1
                state["frame_count"] = frame_count

                _, buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 45])
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
                except Exception:
                    pass

            active_clients[source] -= 1
            print(f"[{source}] 客户端断开连接，当前客户端数: {active_clients[source]}")

            if active_clients[source] == 0:
                if global_caps[source]:
                    global_caps[source].release()
                    global_caps[source] = None
                reset_analysis_state(source)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ==================== 其他接口 ====================
@videoController.get("/results")
async def get_analysis_results(source: str = Query(None)):
    if source and source in stable_state:
        state = stable_state[source]
        return {
            "analyzing": state["analyzing"],
            "completed": state["analysis_completed"],
            "recognizing": state.get("recognizing", False),
            "source": source,
            "results": {k: float(v) for k, v in latest_results[source].items()},
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
async def reset_analysis(source: str = Query(..., description="local 或 rtsp")):
    if source not in stable_state:
        raise HTTPException(status_code=400, detail="无效的source参数")

    active_clients[source] = 0
    if global_caps[source]:
        global_caps[source].release()
        global_caps[source] = None

    reset_analysis_state(source)
    return {"status": "success", "message": f"{source} 已重置"}
