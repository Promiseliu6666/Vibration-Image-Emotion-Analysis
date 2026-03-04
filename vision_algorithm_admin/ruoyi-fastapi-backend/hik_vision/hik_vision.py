# hik_vision/hik_vision.py

import cv2
import numpy as np
import os
import urllib.request
from scipy import signal

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from hik_vision. Vibration_image_algorithm import VibraimageCore

videoController = APIRouter(
    prefix='/video',
    include_in_schema=False
)

# ==================== 摄像头配置 ====================
RTSP_URL = "rtsp://admin:witai515@192.168.3.6:554/main/h264/av_stream"
LOCAL_CAMERA_INDEX = 1

# ==================== 人脸检测模型下载 ====================
MODEL_DIR = os.path.dirname(__file__)
PROTOTXT_PATH = os.path.join(MODEL_DIR, "deploy. prototxt")
CAFFEMODEL_PATH = os.path. join(MODEL_DIR, "res10_300x300_ssd_iter_140000.caffemodel")


def download_model(url, path):
    if not os.path.exists(path):
        print(f"[人脸检测] 下载模型:  {os.path.basename(path)}")
        urllib.request. urlretrieve(url, path)
        print(f"[人脸检测] 下载完成: {path}")


download_model("https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
               PROTOTXT_PATH)
download_model(
    "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
    CAFFEMODEL_PATH)

face_net = cv2.dnn.readNetFromCaffe(PROTOTXT_PATH, CAFFEMODEL_PATH)


def detect_face_dnn(frame, confidence_threshold=0.5):
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
    face_net.setInput(blob)
    detections = face_net.forward()

    best_box = None
    max_conf = confidence_threshold
    for i in range(detections.shape[2]):
        conf = detections[0, 0, i, 2]
        if conf > max_conf:
            max_conf = conf
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (x, y, x1, y1) = box.astype("int")
            best_box = (x, y, x1 - x, y1 - y)
    return best_box


# ==================== 获取摄像头 ====================
def get_camera_cap(source:  str):
    if source == "local":
        print("[视频流] 使用本地摄像头")
        cap = cv2.VideoCapture(LOCAL_CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail="本地摄像头无法打开")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap

    elif source == "rtsp":
        if not RTSP_URL.strip():
            raise HTTPException(status_code=500, detail="RTSP地址未配置")
        print(f"[视频流] 使用RTSP摄像头 {RTSP_URL}")
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail="RTSP摄像头连接失败")
        return cap

    else:
        raise HTTPException(status_code=400, detail="无效的source参数")


# ==================== 全局状态 ====================
latest_results = {f"e{i}": 0.0 for i in range(1, 11)}

# 稳定检测状态（每个source独立）
STABLE_FRAMES_REQUIRED = 15
TOLERANCE = 30

stable_state = {
    "local":  {
        "stable_count": 0,
        "prev_center": None,
        "prev_size": None,
        "locked_rect": None,
        "analyzing": False,
        "frame_count": 0
    },
    "rtsp": {
        "stable_count": 0,
        "prev_center":  None,
        "prev_size": None,
        "locked_rect": None,
        "analyzing": False,
        "frame_count": 0
    }
}


def reset_analysis_state(source: str):
    """重置指定source的分析状态"""
    global latest_results
    state = stable_state[source]
    state["stable_count"] = 0
    state["prev_center"] = None
    state["prev_size"] = None
    state["locked_rect"] = None
    state["analyzing"] = False
    state["frame_count"] = 0
    latest_results = {f"e{i}":  0.0 for i in range(1, 11)}
    print(f"[重置] {source}摄像头分析状态已重置")


# ==================== 视频流 + 自动稳定检测 + 实时分析 ====================
@videoController.get("/feed/analysis")
async def analysis_camera_stream(
        source: str = Query(..., description="local 或 rtsp")
):
    global latest_results

    cap = get_camera_cap(source)
    analyzer = VibraimageCore()
    state = stable_state[source]

    def generate():
        nonlocal state, analyzer

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    frame = np.zeros((480, 640, 3), np.uint8)
                    cv2.putText(frame, 'Disconnected', (100, 240),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                else:
                    frame = cv2.flip(frame, 1)  # 镜像，与本地demo一致

                frame_640 = cv2.resize(frame, (640, 480))
                display_frame = frame_640.copy()

                current_face = detect_face_dnn(frame_640, confidence_threshold=0.5)

                # ==================== 未锁定：稳定检测阶段 ====================
                if not state["analyzing"]:
                    if current_face is not None:
                        x, y, w, h = current_face
                        center_x = x + w // 2
                        center_y = y + h // 2
                        center = (center_x, center_y)
                        size = w * h

                        cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.putText(display_frame, "Detecting face...", (x, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                        # 稳定性判断
                        if state["prev_center"] is not None:
                            dist = np.sqrt((center_x - state["prev_center"][0]) ** 2 +
                                           (center_y - state["prev_center"][1]) ** 2)
                            size_diff = abs(size - state["prev_size"])
                            if dist < TOLERANCE and size_diff < TOLERANCE * 100:
                                state["stable_count"] += 1
                            else:
                                state["stable_count"] = 1
                        else:
                            state["stable_count"] = 1

                        state["prev_center"] = center
                        state["prev_size"] = size

                        cv2.putText(display_frame, f"Stable: {state['stable_count']}/{STABLE_FRAMES_REQUIRED}",
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

                        if state["stable_count"] >= STABLE_FRAMES_REQUIRED:
                            state["locked_rect"] = current_face
                            state["analyzing"] = True
                            state["frame_count"] = 0

                            cx = x + w // 2
                            analyzer.face_rect = np.array([current_face])
                            analyzer.left_face_rect = (x, y, w // 2, h)
                            analyzer.right_face_rect = (cx, y, w - w // 2, h)

                            cv2.putText(display_frame, "FACE STABLE!  ANALYSIS STARTED!", (50, 200),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                            print("[分析] 人脸稳定，开始振动图像分析")
                    else:
                        state["stable_count"] = 0
                        state["prev_center"] = None
                        state["prev_size"] = None
                        cv2.putText(display_frame, "Waiting for face...  Please face the camera", (50, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

                # ==================== 已锁定：正式分析阶段 ====================
                else:
                    x, y, w, h = state["locked_rect"]
                    lx, ly, lw, lh = analyzer.left_face_rect
                    rx, ry, rw, rh = analyzer.right_face_rect

                    # 始终显示绿色人脸框
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.rectangle(display_frame, (lx, ly), (lx + lw, ly + lh), (255, 0, 0), 2)
                    cv2.rectangle(display_frame, (rx, ry), (rx + rw, ry + rh), (0, 0, 255), 2)

                    preprocessed, _ = analyzer._preprocess_head_region(frame_640, (x, y, w, h))
                    analyzer.frame_buffer.append(preprocessed)
                    if len(analyzer.frame_buffer) > analyzer.halo_params['ACCUMULATE_FRAMES']:
                        analyzer.frame_buffer.pop(0)

                    if len(analyzer.frame_buffer) == analyzer.halo_params['ACCUMULATE_FRAMES']:
                        analyzer.A, analyzer.F = analyzer._calculate_vibra_params(analyzer.frame_buffer)
                        analyzer._normalize_vibra_params()

                        left_roi = frame_640[ly:ly + lh, lx:lx + lw]
                        right_roi = frame_640[ry:ry + rh, rx:rx + rw]

                        if left_roi.size > 0 and right_roi. size > 0:
                            left_gray = cv2.cvtColor(left_roi, cv2.COLOR_BGR2GRAY) / 255.0
                            right_gray = cv2.cvtColor(right_roi, cv2.COLOR_BGR2GRAY) / 255.0

                            left_ampl = np.sum(np.abs(left_gray - np.mean(left_gray)))
                            right_ampl = np.sum(np.abs(right_gray - np.mean(right_gray)))
                            left_freq = np.max(left_gray) if np.max(left_gray) > 0 else 0.001
                            right_freq = np.max(right_gray) if np.max(right_gray) > 0 else 0.001
                            energy = np.sum(analyzer.A ** 2) if analyzer.A. size > 0 else 0

                            analyzer.vibration_energies.append(energy)
                            analyzer.left_amplitudes.append(left_ampl)
                            analyzer.right_amplitudes.append(right_ampl)
                            analyzer.left_max_freqs.append(left_freq)
                            analyzer.right_max_freqs.append(right_freq)

                            # ✅ 频谱分析（与1117. py一致）
                            state["frame_count"] += 1
                            if state["frame_count"] % analyzer.time_window == 0 and len(analyzer.vibration_energies) >= analyzer.time_window:
                                energy_arr = np.array(analyzer.vibration_energies[-analyzer.time_window:])
                                freqs, psd = signal.welch(energy_arr, analyzer.fps, nperseg=min(analyzer.time_window, 1024))
                                analyzer.frequency_data. append(freqs)
                                analyzer.power_spectrum.append(psd)

                            results = analyzer._calculate_all_parameters()
                            latest_results. update({k: float(v) for k, v in results.items()})

                # 发送帧
                _, buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        except GeneratorExit:
            print("[视频流] 客户端断开")
        finally:
            cap.release()

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ==================== 返回实时参数 ====================
@videoController. get("/results")
async def get_analysis_results():
    return {k: float(v) for k, v in latest_results.items()}


# ==================== 重置分析状态 ====================
@videoController.get("/reset")
async def reset_analysis(source:  str = Query(..., description="local 或 rtsp")):
    """重置指定摄像头的分析状态和参数数据"""
    if source not in stable_state:
        raise HTTPException(status_code=400, detail="无效的source参数")

    reset_analysis_state(source)
    return {"status": "success", "message": f"{source}摄像头已重置"}