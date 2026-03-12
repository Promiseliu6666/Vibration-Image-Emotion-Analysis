import json
import cv2
import numpy as np
import os
import urllib.request
from scipy import signal
import time
import base64
import asyncio
import traceback
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import face_recognition  # 仅用于兼容性，实际未在检测中使用
from hik_vision.Vibration_image_algorithm import VibraimageCore
from config.get_db import get_db
from module_xuzhou.service.people_service import PeopleService, FaceFeatureExtractor
from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.entity.vo.analysis_vo import BinhuaAnalysisModel

videoController = APIRouter(
    prefix='/video',
    include_in_schema=False
)

# ==================== 摄像头配置 ====================
RTSP_URL = "rtsp://admin:witai515@192.168.3.6:554/main/h264/av_stream"
LOCAL_CAMERA_INDEX = 1

# ==================== 人脸识别参数 ====================
SIMILARITY_THRESHOLD = 0.4

# ==================== OpenCV DNN 人脸检测模型 ====================
MODEL_PROTO = "deploy.prototxt"
MODEL_WEIGHTS = "res10_300x300_ssd_iter_140000.caffemodel"

MODEL_PROTO_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
MODEL_WEIGHTS_URL = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"

# 首次运行自动下载模型
if not os.path.exists(MODEL_PROTO):
    print("[DNN模型] 正在下载 deploy.prototxt ...")
    try:
        urllib.request.urlretrieve(MODEL_PROTO_URL, MODEL_PROTO)
        print("[DNN模型] deploy.prototxt 下载完成")
    except Exception as e:
        print(f"[DNN模型] deploy.prototxt 下载失败: {e}")
        raise HTTPException(status_code=500, detail="无法下载人脸检测模型文件 deploy.prototxt")

if not os.path.exists(MODEL_WEIGHTS):
    print("[DNN模型] 正在下载 res10_300x300_ssd_iter_140000.caffemodel ...")
    try:
        urllib.request.urlretrieve(MODEL_WEIGHTS_URL, MODEL_WEIGHTS)
        print("[DNN模型] res10_300x300_ssd_iter_140000.caffemodel 下载完成")
    except Exception as e:
        print(f"[DNN模型] res10_300x300_ssd_iter_140000.caffemodel 下载失败: {e}")
        raise HTTPException(status_code=500, detail="无法下载人脸检测模型文件 res10_300x300_ssd_iter_140000.caffemodel")

# 全局加载 DNN 模型
try:
    face_net = cv2.dnn.readNetFromCaffe(MODEL_PROTO, MODEL_WEIGHTS)
    print("[DNN模型] 模型加载成功")
except Exception as e:
    print(f"[DNN模型] 模型加载失败: {e}")
    raise HTTPException(status_code=500, detail="人脸检测模型加载失败")


# ==================== 获取摄像头（带超时） ====================
def get_camera_cap(source: str):
    if source == "local":
        print("[视频流] 使用本地摄像头")
        cap = cv2.VideoCapture(LOCAL_CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        start_time = time.time()
        while time.time() - start_time < 3:
            ret, _ = cap.read()  # ← 修正这里：改为 ret, _ （忽略frame）
            if ret:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 60)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print("[视频流] 本地摄像头已就绪")
                return cap
            time.sleep(0.05)

        cap.release()
        raise HTTPException(status_code=500, detail="本地摄像头无法打开或无视频信号（超时）")

    elif source == "rtsp":
        if not RTSP_URL.strip():
            raise HTTPException(status_code=500, detail="RTSP地址未配置")
        print(f"[视频流] 使用RTSP摄像头 {RTSP_URL}")

        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|timeout;5000000'

        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 60)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        start_time = time.time()
        while time.time() - start_time < 5:
            ret, _ = cap.read()  # ← 这里本来就正确，保持不变
            if ret:
                print("[视频流] RTSP摄像头已就绪")
                return cap
            time.sleep(0.05)

        cap.release()
        raise HTTPException(status_code=500, detail="RTSP摄像头连接失败或无视频流（超时）")

    else:
        raise HTTPException(status_code=400, detail="无效的source参数")


# ==================== 全局共享资源 ====================
global_caps = {"local": None, "rtsp": None}
active_clients = {"local": 0, "rtsp": 0}

# ==================== 全局状态 ====================
latest_results = {
    "local": {f"e{i}": 0.0 for i in range(1, 15)},
    "rtsp": {f"e{i}": 0.0 for i in range(1, 15)}
}

STABLE_FRAMES_REQUIRED = 15
TOLERANCE = 60
LOST_CHECK_INTERVAL = 20
LOST_DIST_THRESHOLD = 100

stable_state = {
    "local": {
        "stable_count": 0, "prev_center": None, "prev_size": None,
        "locked_rect": None, "analyzing": False, "frame_count": 0,
        "matched_person": None, "feature_extracted": False,
        "match_similarity": 0.0,
        "last_detected_rect": None,
        "identified": False,
        "analysis_start_time": None,
        "analysis_duration": 10.0,
        "analysis_completed": False,
        "person_id": ""
    },
    "rtsp": {
        "stable_count": 0, "prev_center": None, "prev_size": None,
        "locked_rect": None, "analyzing": False, "frame_count": 0,
        "matched_person": None, "feature_extracted": False,
        "match_similarity": 0.0,
        "last_detected_rect": None,
        "identified": False,
        "analysis_start_time": None,
        "analysis_duration": 10.0,
        "analysis_completed": False,
        "person_id": ""
    }
}


async def save_analysis_to_db(db: AsyncSession, source: str, state: dict, results: dict):
    """
    将分析结果保存到数据库
    修改为与前端一致的计算逻辑：
    - happiness_index = e12 (假设 0-100 范围)
    - happiness_level 基于 happiness_index: >=80 "幸福达标", >=60 "幸福待提升", else "幸福预警"
    - safety_risk 基于 happiness_index: >=70 "低风险", >=40 "中风险", else "高风险"
    """
    try:
        # 获取person_id
        person_id = None
        if state["matched_person"] and state["matched_person"] != "Unknown":
            # 直接通过人名查询获取person_id
            try:
                from module_xuzhou.entity.do.people_do import PeopleFace
                from sqlalchemy import select
                result = await db.execute(
                    select(PeopleFace)
                    .where(
                        PeopleFace.name == state["matched_person"],
                        PeopleFace.group_id == 1,
                        PeopleFace.is_deleted == False
                    )
                    .limit(1)
                )
                person = result.scalars().first()
                if person:
                    person_id = person.id
                    state["person_id"] = person_id  # 保存person_id到状态
            except Exception as e:
                print(f"[{source}] 获取person_id时发生异常: {e}")
                person_id = None

        # 与前端一致：使用 e12 作为 happiness_index（假设单位为 0-100）
        happiness_index = results.get("e12", 0.0)

        # 与前端一致的幸福水平计算
        if happiness_index >= 80:
            happiness_level = "高"
        elif happiness_index >= 60:
            happiness_level = "中"
        else:
            happiness_level = "低"

        # 与前端一致的安全风险计算
        if happiness_index >= 70:
            safety_risk = "低风险"
        elif happiness_index >= 40:
            safety_risk = "中风险"
        else:
            safety_risk = "高风险"

        # 创建分析记录
        analysis_model = BinhuaAnalysisModel(
            source=source,
            person_name=state["matched_person"] or "Unknown",
            person_id=person_id,
            e1=results.get("e1", 0.0),
            e2=results.get("e2", 0.0),
            e3=results.get("e3", 0.0),
            e4=results.get("e4", 0.0),
            e5=results.get("e5", 0.0),
            e6=results.get("e6", 0.0),
            e7=results.get("e7", 0.0),
            e8=results.get("e8", 0.0),
            e9=results.get("e9", 0.0),
            e10=results.get("e10", 0.0),
            e11=results.get("e11", 0.0),
            e12=results.get("e12", 0.0),
            e13=results.get("e13", 0.0),
            e14=results.get("e14", 0.0),
            happiness_index=happiness_index,
            happiness_level=happiness_level,
            safety_risk=safety_risk
        )

        # 保存到数据库
        analysis_id = await BinhuaAnalysisDao.add_analysis_dao(db, analysis_model)
        await db.commit()

        print(f"[{source}] 分析结果已保存到数据库，ID: {analysis_id}")
        return analysis_id

    except Exception as e:
        print(f"[{source}] 保存分析结果到数据库失败: {e}")
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
            "person_id": ""  # 重置person_id
        })
        latest_results[source] = {f"e{i}": 0.0 for i in range(1, 15)}


# ==================== 辅助函数 ====================
def image_to_base64(image: np.ndarray) -> str:
    _, buffer = cv2.imencode('.jpg', image)
    return base64.b64encode(buffer).decode('utf-8')


async def recognize_face(db: AsyncSession, frame: np.ndarray, face_rect: tuple, state: dict) -> tuple[
    str | None, float]:
    try:
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        current_image_base64 = base64.b64encode(buffer).decode('utf-8')

        compare_results = await PeopleService.face_compare_services(
            db, current_image_base64, group_id=1, threshold=SIMILARITY_THRESHOLD
        )

        if compare_results and compare_results[0]:
            best_match = compare_results[0]
            name = best_match['name']
            similarity = best_match['similarity']

            # 获取并保存person_id
            if name != "Unknown":
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
                        state["person_id"] = person.id  # 保存person_id到状态
                except Exception as e:
                    print(f"[{source}] 获取person_id时发生异常: {e}")
                    state["person_id"] = ""

            state["identified"] = True
            return name, similarity
        else:
            state["person_id"] = ""  # 未识别到则清空person_id
            return "Unknown", 0.0

    except Exception as e:
        print(f"[人脸识别] 异常: {e}")
        traceback.print_exc()
        state["person_id"] = ""
        return None, 0.0


def draw_face_recognition(frame: np.ndarray, name: str, similarity: float, rect: tuple, is_locked: bool = False,
                          remaining_time: float = None):
    if rect is None:
        return
    x, y, w, h = rect

    if is_locked:
        color = (255, 0, 0)  # 蓝色粗框
        thickness = 3
        # ✅ 只保留锁定标识，去掉姓名和相似度
        label = "[Locked]"
        if remaining_time is not None:
            label = f"[Locked] | {remaining_time:.1f}s"
    else:
        color = (0, 255, 0)  # 绿色细框
        thickness = 2
        # ✅ 去掉所有文字，只画框
        label = ""

    # 绘制人脸框
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)

    # ✅ 只有当label不为空时，才绘制文字背景和文字
    if label.strip():
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(frame, (x, y - 25), (x + text_size[0] + 10, y), (0, 0, 255), cv2.FILLED)
        cv2.putText(frame, label, (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


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


# ==================== 视频流生成 ====================
@videoController.get("/feed/analysis")
async def generate_video_stream(
        source: str = Query(default='local'),
        query_db: AsyncSession = Depends(get_db)
):
    if source not in ["local", "rtsp"]:
        raise HTTPException(status_code=400, detail="无效的source参数")

    # 客户端计数 +1
    active_clients[source] += 1
    print(f"[{source}] 新客户端连接，当前客户端数: {active_clients[source]}")

    # 共享 cap（首次打开）
    if global_caps[source] is None:
        global_caps[source] = get_camera_cap(source)

    cap = global_caps[source]
    state = stable_state[source]
    analyzer = VibraimageCore()
    analyzer.halo_params["ACCUMULATE_FRAMES"] = 5

    time.sleep(1.0)

    async def generate():
        try:
            last_frame_time = time.time()
            while active_clients[source] > 0:  # 关键：有活跃客户端才继续
                ret, frame = cap.read()
                if not ret:
                    print("[视频流] 无法读取帧")
                    await asyncio.sleep(0.1)
                    continue

                current_time = time.time()
                if current_time - last_frame_time < 0.0167:
                    await asyncio.sleep(0.001)
                    continue

                frame = cv2.resize(frame, (640, 480))
                display_frame = frame.copy()
                if source == 'local':
                    display_frame = cv2.flip(display_frame, 1)

                face_rect = None

                # 每4帧处理检测/稳定判定（锁定后不再检测）
                if state["frame_count"] % 4 == 0:
                    if state["analyzing"] and state["locked_rect"] is not None:
                        face_rect = state["locked_rect"]
                    else:
                        face_rect = await asyncio.to_thread(detect_face, display_frame)
                        if face_rect is not None:
                            state["last_detected_rect"] = face_rect

                            # 仅在未锁定阶段进行稳定判定
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

                            state["prev_center"] = center
                            state["prev_size"] = size

                            if state["stable_count"] >= STABLE_FRAMES_REQUIRED:
                                if not state["analyzing"]:
                                    print(f"[{source}] 人脸框已稳定锁定，立即开始振动分析（e1-e14）")
                                state["locked_rect"] = face_rect
                                state["analyzing"] = True
                                analyzer.reset()

                else:
                    if state["analyzing"]:
                        face_rect = state["locked_rect"]
                    elif state["last_detected_rect"] is not None:
                        face_rect = state["last_detected_rect"]

                # 锁定后的人脸丢失/大移动检查
                if state["analyzing"] and state["frame_count"] % LOST_CHECK_INTERVAL == 0:
                    current_detect = await asyncio.to_thread(detect_face, display_frame)
                    if current_detect is None:
                        print(f"[{source}] 人脸丢失，重置分析状态")
                        reset_analysis_state(source)
                        analyzer.reset()
                        face_rect = None
                    else:
                        cx, cy, cw, ch = current_detect
                        current_center = (cx + cw // 2, cy + ch // 2)
                        locked_x, locked_y, locked_w, locked_h = state["locked_rect"]
                        locked_center = (locked_x + locked_w // 2, locked_y + locked_h // 2)
                        dist = np.linalg.norm(np.array(current_center) - np.array(locked_center))
                        if dist > LOST_DIST_THRESHOLD:
                            print(f"[{source}] 人脸大移动，重置分析状态")
                            reset_analysis_state(source)
                            analyzer.reset()
                            face_rect = None

                if face_rect is not None:
                    # 人脸识别：仅在未锁定且未成功识别身份时进行
                    if state["frame_count"] % 30 == 0 and not state["identified"] and not state["analyzing"]:
                        name, similarity = await recognize_face(query_db, frame, face_rect, state)
                        if name:
                            state["matched_person"] = name
                            state["match_similarity"] = similarity
                            # 识别到身份后开始计时
                            if name != "Unknown" and state["analysis_start_time"] is None:
                                state["analysis_start_time"] = time.time()
                                print(f"[{source}] 识别到 {name}，开始10秒分析")
                        else:
                            state["matched_person"] = "Unknown"
                            state["match_similarity"] = 0.0
                            state["person_id"] = ""

                    # 计算剩余时间
                    remaining_time = None
                    if state["analysis_start_time"] is not None:
                        elapsed = time.time() - state["analysis_start_time"]
                        remaining_time = max(0, state["analysis_duration"] - elapsed)

                        # 如果时间到了，停止分析并固定结果
                        if remaining_time <= 0:
                            print(f"[{source}] 10秒分析完成，停止分析并固定结果")
                            state["analysis_completed"] = True  # 标记分析已完成
                            state["analysis_start_time"] = None
                            # 保存分析结果到数据库
                            await save_analysis_to_db(query_db, source, state, latest_results[source])
                            # 注意：不设置 analyzing=False，保持为True以兼容前端显示

                    # 统一绘制
                    draw_face_recognition(display_frame,
                                          state["matched_person"] or "Unknown",
                                          state["match_similarity"],
                                          face_rect,
                                          is_locked=state["analyzing"],
                                          remaining_time=remaining_time)

                    # 振动分析（仅在分析未完成时进行）
                    if state["analyzing"] and not state["analysis_completed"] and state["frame_count"] % 3 == 0 and \
                            state['matched_person'] != "Unknown":
                        try:
                            fps = cap.get(cv2.CAP_PROP_FPS) or 60
                            analysis_results = await asyncio.to_thread(
                                analyzer.process_frame, frame, face_rect=face_rect, fps=fps
                            )
                            if analysis_results:
                                latest_results[source].update(analysis_results)
                        except Exception as e:
                            print(f"[振动分析线程] 异常: {e}")
                            traceback.print_exc()

                state["frame_count"] += 1

                _, buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

                last_frame_time = time.time()
                await asyncio.sleep(max(0, 0.0167 - (time.time() - last_frame_time)))

        except asyncio.CancelledError:
            print(f"[{source}] 客户端断开或任务取消")
            raise
        except GeneratorExit:
            print(f"[{source}] 客户端断开 (GeneratorExit)")
        except Exception as e:
            print(f"[{source}] 发生异常: {e}")
            traceback.print_exc()
        finally:
            active_clients[source] -= 1
            print(f"[{source}] 客户端断开，剩余客户端数: {active_clients[source]}")
            if active_clients[source] == 0:
                if global_caps[source]:
                    global_caps[source].release()
                    global_caps[source] = None
                    print(f"[{source}] 最后一个客户端断开，摄像头已释放")
                reset_analysis_state(source)
                print(f"[{source}] 状态已重置")

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ==================== 返回实时参数（适配前端显示） ====================
@videoController.get("/results")
async def get_analysis_results(source: str = Query(None)):
    # 处理指定source的情况
    if source and source in stable_state:
        state = stable_state[source]
        # 处理分析完成的情况
        if state["analysis_completed"]:
            return {
                "analyzing": True,  # 保持analyzing=True以兼容前端显示
                "completed": True,
                "source": source,
                "results": {k: float(v) for k, v in latest_results[source].items()},
                "matched_person": state["matched_person"] or "Unknown",
                "person_id": state["person_id"] or "未知ID",  # 确保返回person_id
                "similarity": state["match_similarity"] or 0.0,
                "message": "分析已完成，结果已固定"
            }
        # 处理正在分析的情况
        elif state["analyzing"]:
            return {
                "analyzing": True,
                "completed": False,
                "source": source,
                "results": {k: float(v) for k, v in latest_results[source].items()},
                "matched_person": state["matched_person"] or "Unknown",
                "person_id": state["person_id"] or "未知ID",  # 确保返回person_id
                "similarity": state["match_similarity"] or 0.0
            }
        # 处理未分析的情况（返回默认人员信息）
        else:
            return {
                "analyzing": False,
                "completed": False,
                "message": "当前无有效分析（摄像头未连接或人脸未稳定）",
                "results": {f"e{i}": 0.0 for i in range(1, 15)},
                "matched_person": "未识别",
                "person_id": "未知ID",
                "similarity": 0.0
            }

    # 处理未指定source的情况
    active_sources = [s for s in stable_state if stable_state[s]["analyzing"]]
    if active_sources:
        s = active_sources[0]
        state = stable_state[s]
        return {
            "analyzing": True,
            "completed": False,
            "source": s,
            "results": {k: float(v) for k, v in latest_results[s].items()},
            "matched_person": state["matched_person"] or "Unknown",
            "person_id": state["person_id"] or "未知ID",
            "similarity": state["match_similarity"] or 0.0
        }

    # 无活跃源时返回默认值
    return {
        "analyzing": False,
        "completed": False,
        "message": "无任何摄像头正在分析",
        "results": {f"e{i}": 0.0 for i in range(1, 15)},
        "matched_person": "未识别",
        "person_id": "未知ID",
        "similarity": 0.0
    }


# ==================== 重置接口（强制释放资源） ====================
@videoController.get("/reset")
async def reset_analysis(source: str = Query(..., description="local 或 rtsp")):
    if source not in stable_state:
        raise HTTPException(status_code=400, detail="无效的source参数")

    # 强制视为所有客户端断开
    active_clients[source] = 0
    if global_caps[source]:
        global_caps[source].release()
        global_caps[source] = None
        print(f"[{source}] 重置接口强制释放摄像头")

    reset_analysis_state(source)
    return {
        "status": "success",
        "message": f"{source}摄像头已重置并释放资源",
        "data": {
            "analyzing": False,
            "matched_person": None,
            "person_id": "",
            "similarity": 0.0
        }
    }