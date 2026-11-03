"""Local HTTP service that exposes the FatigueSense pipeline to the platform.

The service pulls the latest authenticated frame from the RuoYi backend's
localhost camera bridge. This keeps camera ownership in one process while
running the PyTorch/MediaPipe environment separately from the main backend.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import threading
import time
from collections import deque
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np
import requests
import torch

from fatigue_pipeline.aggregation.step_features import FeatureStep
from fatigue_pipeline.cnn_predictors import EyeStateClassifier, MouthStateClassifier
from fatigue_pipeline.constants import (
    DEFAULT_BIGRU_INFERENCE_STRIDE,
    DEFAULT_STEP_STRIDE_S,
    DEFAULT_SUB_WINDOW_S,
    FEATURE_NAMES,
    POSE_NUM_KPTS,
    UPPER_BODY_KPT_NAMES,
)
from fatigue_pipeline.feature_aggregator import FeatureAggregator
from fatigue_pipeline.inference_pipeline import FrameProbs
from fatigue_pipeline.pose_estimator import PoseEstimator
from fatigue_pipeline.region_cropper import RegionCropper
from model_architecture.models.bigru_temporal import load_temporal_checkpoint
from model_architecture.utils.normalization import load_normalization
from scripts.weights_path import (
    EYE_CKPT,
    LANDMARKER_PATH,
    MOUTH_CKPT,
    NORMALIZATION_PATH,
    POSE_MODEL_PATH,
    TEMPORAL_MODEL_PATH,
    resolve_asset,
)

TARGET_FPS = max(5.0, float(os.getenv("FATIGUE_INFERENCE_FPS", "12")))
TARGET_DT = 1.0 / TARGET_FPS
WINDOW_STEPS = 30
BIGRU_INFERENCE_STRIDE = DEFAULT_BIGRU_INFERENCE_STRIDE
EMA_ALPHA = 0.4
SESSION_IDLE_SECONDS = 45.0

BUNDLE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = BUNDLE_ROOT.parent
DEFAULT_BRIDGE_URL = "http://127.0.0.1:9099/video/shared/frame"
BRIDGE_SECRET_PATH = REPOSITORY_ROOT / ".runtime" / "camera-bridge-secret.txt"


def _resolve_device() -> str:
    requested = os.getenv("FATIGUE_DEVICE", "cuda").strip().lower()
    if requested != "cuda":
        return requested or "cpu"
    if not torch.cuda.is_available():
        return "cpu"
    try:
        probe = torch.zeros(1, device="cuda")
        (probe + 1).cpu()
    except RuntimeError:
        return "cpu"
    return "cuda"


def _status_label(score: float | None) -> str:
    if score is None:
        return "预热中"
    if score < 0.30:
        return "疲劳"
    if score < 0.55:
        return "困倦"
    return "清醒"


def _mean_pose_confidence(kpts: np.ndarray | None) -> float | None:
    if kpts is None or not kpts.size:
        return None
    values = kpts[:POSE_NUM_KPTS, 2]
    values = values[np.isfinite(values)]
    return float(values.mean()) if values.size else None


def _pose_keypoints_payload(
    kpts: np.ndarray | None,
    frame_width: int,
    frame_height: int,
) -> list[dict]:
    if kpts is None or not kpts.size:
        return []

    points = []
    for index, name in enumerate(UPPER_BODY_KPT_NAMES):
        x, y, confidence = (float(value) for value in kpts[index])
        valid = (
            math.isfinite(x)
            and math.isfinite(y)
            and math.isfinite(confidence)
            and confidence >= 0.0
        )
        points.append(
            {
                "name": name,
                "x": x / frame_width if valid else None,
                "y": y / frame_height if valid else None,
                "confidence": confidence if valid else None,
            }
        )
    return points


def _detection_boxes_payload(
    boxes: dict[str, tuple[int, int, int, int] | None],
    frame_width: int,
    frame_height: int,
) -> dict[str, dict[str, float] | None]:
    payload = {}
    for name in ("face", "left_eye", "right_eye", "mouth"):
        box = boxes.get(name)
        if box is None:
            payload[name] = None
            continue
        x1, y1, x2, y2 = box
        payload[name] = {
            "x1": x1 / frame_width,
            "y1": y1 / frame_height,
            "x2": x2 / frame_width,
            "y2": y2 / frame_height,
        }
    return payload


class FatigueRuntime:
    """Loads each model once and runs one stateful analysis session at a time."""

    def __init__(self) -> None:
        self.device = _resolve_device()
        print(f"[fatigue-service] device={self.device}", flush=True)
        self.cropper = RegionCropper(
            resolve_asset(LANDMARKER_PATH),
            fps=TARGET_FPS,
        )
        self.eye_classifier = EyeStateClassifier(
            resolve_asset(EYE_CKPT),
            device=self.device,
        )
        self.mouth_classifier = MouthStateClassifier(
            resolve_asset(MOUTH_CKPT),
            device=self.device,
        )
        self.pose_estimator = PoseEstimator(
            resolve_asset(POSE_MODEL_PATH),
            device=self.device,
        )
        self.temporal_model = load_temporal_checkpoint(
            resolve_asset(TEMPORAL_MODEL_PATH),
            self.device,
        )
        norm = load_normalization(resolve_asset(NORMALIZATION_PATH))
        self.norm_mean = torch.from_numpy(norm["mean"]).to(self.device)
        self.norm_std = torch.from_numpy(norm["std"]).to(self.device)
        print("[fatigue-service] all models loaded", flush=True)

    def new_session(self) -> "FatigueSessionState":
        self.cropper.reset(fps=TARGET_FPS)
        return FatigueSessionState(
            aggregator=FeatureAggregator(
                fps=TARGET_FPS,
                sub_window_s=DEFAULT_SUB_WINDOW_S,
                step_stride_s=DEFAULT_STEP_STRIDE_S,
            ),
            feature_buffer=deque(maxlen=WINDOW_STEPS),
        )

    def process_frame(
        self,
        frame: np.ndarray,
        session: "FatigueSessionState",
    ) -> dict:
        started = time.perf_counter()
        (left_eye, right_eye, mouth), boxes = (
            self.cropper.get_crops_with_boxes(frame)
        )
        p_left, p_right = self.eye_classifier.predict_probs_batch(
            [left_eye, right_eye]
        )
        p_mouth = self.mouth_classifier.predict_prob(mouth)
        kpts = self.pose_estimator.predict(frame)

        frame_idx = self.cropper.frame_idx - 1
        probs = FrameProbs(
            frame_idx=frame_idx,
            timestamp_s=frame_idx / TARGET_FPS,
            face_detected=any(
                crop is not None for crop in (left_eye, right_eye, mouth)
            ),
            p_eye_left_closed=p_left,
            p_eye_right_closed=p_right,
            p_mouth_open=p_mouth,
            keypoints=kpts,
        )
        step = session.aggregator.add(probs)

        inference_dt = time.perf_counter() - started
        session.inference_dt_avg = (
            inference_dt
            if session.inference_dt_avg == 0.0
            else 0.9 * session.inference_dt_avg + 0.1 * inference_dt
        )

        if step is not None:
            session.last_step = step
            features = step.features
            if features.valid:
                session.feature_buffer.append(features.to_array())
                if len(session.feature_buffer) == WINDOW_STEPS:
                    should_run = (
                        session.emits_since_full % BIGRU_INFERENCE_STRIDE
                    ) == 0
                    session.emits_since_full += 1
                    if should_run:
                        self._score_window(session)

        return {
            "face_detected": probs.face_detected,
            "keypoints": _pose_keypoints_payload(
                kpts,
                frame.shape[1],
                frame.shape[0],
            ),
            "boxes": _detection_boxes_payload(
                boxes,
                frame.shape[1],
                frame.shape[0],
            ),
            "p_left": p_left,
            "p_right": p_right,
            "p_mouth": p_mouth,
            "posture_confidence": _mean_pose_confidence(kpts),
            "inference_fps": (
                1.0 / session.inference_dt_avg
                if session.inference_dt_avg > 0
                else 0.0
            ),
            "inference_latency_ms": inference_dt * 1000.0,
            "temporal_fps": session.temporal_fps,
            "warmup_progress": min(
                session.frames_seen,
                session.aggregator.sub_window_frames,
            ),
            "warmup_target": session.aggregator.sub_window_frames,
            "feature_buffer": len(session.feature_buffer),
            "feature_target": WINDOW_STEPS,
            "last_step": self._step_payload(session.last_step),
            "score_raw": session.score_raw,
            "score_ema": session.score_ema,
            "score_status": _status_label(session.score_ema),
            "blink_total": session.aggregator.blink_total,
            "yawn_total": session.aggregator.yawn_total,
            "is_blinking": session.aggregator.is_blinking,
            "is_yawning": session.aggregator.is_yawning,
        }

    def _score_window(self, session: "FatigueSessionState") -> None:
        started = time.perf_counter()
        window = np.stack(session.feature_buffer, axis=0)
        tensor = torch.from_numpy(window).to(self.device)
        tensor = (tensor - self.norm_mean) / self.norm_std
        with torch.no_grad():
            logit = self.temporal_model.forward_logits(
                tensor.unsqueeze(0)
            ).squeeze()
        score_raw = float(torch.sigmoid(logit).item())
        session.score_raw = score_raw
        session.score_ema = (
            score_raw
            if session.score_ema is None
            else EMA_ALPHA * score_raw + (1.0 - EMA_ALPHA) * session.score_ema
        )
        temporal_dt = time.perf_counter() - started
        session.temporal_dt_avg = (
            temporal_dt
            if session.temporal_dt_avg == 0.0
            else 0.9 * session.temporal_dt_avg + 0.1 * temporal_dt
        )
        if session.temporal_dt_avg > 0:
            session.temporal_fps = 1.0 / session.temporal_dt_avg

    @staticmethod
    def _step_payload(step: FeatureStep | None) -> dict | None:
        if step is None:
            return None
        features = asdict(step.features)
        return {
            "step_idx": step.step_idx,
            "timestamp_s": step.timestamp_s,
            "valid": features.pop("valid"),
            "features": {
                name: features.get(name)
                for name in FEATURE_NAMES
            },
        }


class FatigueSessionState:
    def __init__(self, aggregator: FeatureAggregator, feature_buffer: deque) -> None:
        self.aggregator = aggregator
        self.feature_buffer = feature_buffer
        self.frames_seen = 0
        self.inference_dt_avg = 0.0
        self.temporal_dt_avg = 0.0
        self.temporal_fps = 0.0
        self.emits_since_full = 0
        self.last_step: FeatureStep | None = None
        self.score_raw: float | None = None
        self.score_ema: float | None = None


class AnalysisSession(threading.Thread):
    def __init__(
        self,
        runtime: FatigueRuntime,
        source: str,
        device_id: str,
        bridge_url: str,
        bridge_secret: str,
        session_state: FatigueSessionState,
    ) -> None:
        super().__init__(daemon=True, name=f"fatigue-{source}:{device_id}")
        self.runtime = runtime
        self.source = source
        self.device_id = device_id
        self.bridge_url = bridge_url
        self.bridge_secret = bridge_secret
        self.state = session_state
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_access = time.monotonic()
        self._latest_frame: np.ndarray | None = None
        self._latest_payload: dict | None = None
        self._frame_sequence = 0
        self._payload = {
            "ok": True,
            "status": "starting",
            "message": "正在加载疲劳检测模型",
            "source": source,
            "device_id": device_id,
            "face_detected": False,
            "keypoints": [],
            "boxes": {},
            "score_raw": None,
            "score_ema": None,
            "score_status": "预热中",
            "warmup_progress": 0,
            "warmup_target": self.state.aggregator.sub_window_frames,
            "feature_buffer": 0,
            "feature_target": WINDOW_STEPS,
            "last_step": None,
            "blink_total": 0,
            "yawn_total": 0,
            "is_blinking": False,
            "is_yawning": False,
        }

    def touch(self) -> None:
        self._last_access = time.monotonic()

    def snapshot(self) -> dict:
        self.touch()
        with self._lock:
            return copy.deepcopy(self._payload)

    def frame_snapshot(self) -> tuple[int, np.ndarray | None, dict | None]:
        self.touch()
        with self._lock:
            return (
                self._frame_sequence,
                None if self._latest_frame is None else self._latest_frame.copy(),
                copy.deepcopy(self._latest_payload),
            )

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        self._update(status="running", message="正在等待摄像头画面")
        request = requests.Session()
        headers = {"X-Camera-Bridge-Key": self.bridge_secret}
        params = {"source": self.source}
        if self.device_id:
            params["device_id"] = self.device_id

        while not self._stop_event.is_set():
            if time.monotonic() - self._last_access > SESSION_IDLE_SECONDS:
                self._update(status="stopped", message="检测页面长时间未访问")
                return

            loop_started = time.perf_counter()
            try:
                response = request.get(
                    self.bridge_url,
                    params=params,
                    headers=headers,
                    timeout=5,
                )
                response.raise_for_status()
                image = cv2.imdecode(
                    np.frombuffer(response.content, dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if image is None:
                    raise RuntimeError("摄像头返回的画面无法解码")

                self.state.frames_seen += 1
                payload = self.runtime.process_frame(image, self.state)
                payload.update(
                    status="running",
                    message="实时检测中" if payload["face_detected"] else "请将面部置于画面中",
                    source=self.source,
                    device_id=self.device_id,
                    ok=True,
                )
                self._update_frame(payload, image)
            except Exception as exc:
                self._update(
                    status="error",
                    ok=False,
                    message=f"疲劳检测暂时不可用：{exc}",
                    source=self.source,
                    device_id=self.device_id,
                )
                if self._stop_event.wait(1.0):
                    return
                continue

            elapsed = time.perf_counter() - loop_started
            if self._stop_event.wait(max(0.0, TARGET_DT - elapsed)):
                return

    def _update(self, **values) -> None:
        with self._lock:
            self._payload.update(values)

    def _update_frame(self, payload: dict, frame: np.ndarray) -> None:
        with self._lock:
            self._frame_sequence += 1
            self._latest_frame = frame.copy()
            self._latest_payload = copy.deepcopy(payload)
            self._payload.update(payload)


class SessionManager:
    def __init__(
        self,
        bridge_url: str,
        bridge_secret: str,
        idle_seconds: float = SESSION_IDLE_SECONDS,
    ) -> None:
        self.bridge_url = bridge_url
        self.bridge_secret = bridge_secret
        self.idle_seconds = idle_seconds
        self._runtime: FatigueRuntime | None = None
        self._runtime_lock = threading.Lock()
        self._session: AnalysisSession | None = None
        self._session_lock = threading.Lock()

    def _get_runtime(self) -> FatigueRuntime:
        with self._runtime_lock:
            if self._runtime is None:
                self._runtime = FatigueRuntime()
            return self._runtime

    def results(self, source: str, device_id: str = "") -> dict:
        _validate_camera_args(source, device_id)
        with self._session_lock:
            session = self._ensure_session(source, device_id)
        return session.snapshot()

    def frame_snapshot(
        self,
        source: str,
        device_id: str = "",
    ) -> tuple[int, np.ndarray | None, dict | None]:
        _validate_camera_args(source, device_id)
        with self._session_lock:
            session = self._ensure_session(source, device_id)
        return session.frame_snapshot()

    def reset(self, source: str, device_id: str = "") -> dict:
        _validate_camera_args(source, device_id)
        with self._session_lock:
            if self._session is not None:
                self._session.stop()
                self._session.join(timeout=5.0)
                self._session = None
        return self.results(source, device_id)

    def close(self) -> None:
        with self._session_lock:
            if self._session is not None:
                self._session.stop()
                self._session.join(timeout=5.0)
                self._session = None

    def _ensure_session(self, source: str, device_id: str) -> AnalysisSession:
        key = f"{source}:{device_id}"
        if (
            self._session is None
            or self._session.name != f"fatigue-{key}"
            or not self._session.is_alive()
        ):
            if self._session is not None:
                self._session.stop()
                self._session.join(timeout=5.0)
            runtime = self._get_runtime()
            self._session = AnalysisSession(
                runtime=runtime,
                source=source,
                device_id=device_id,
                bridge_url=self.bridge_url,
                bridge_secret=self.bridge_secret,
                session_state=runtime.new_session(),
            )
            self._session.start()
        return self._session


def _validate_camera_args(source: str, device_id: str) -> None:
    if source not in {"local", "rtsp", "xiaozhi"}:
        raise ValueError("视频来源必须是 local、rtsp 或 xiaozhi")
    if device_id and not re.fullmatch(r"[A-Za-z0-9:_-]{1,64}", device_id):
        raise ValueError("小智设备编号格式不正确")


def _load_bridge_secret() -> str:
    configured = os.getenv("CAMERA_BRIDGE_KEY", "").strip()
    if configured:
        return configured
    if not BRIDGE_SECRET_PATH.is_file():
        raise FileNotFoundError(
            f"摄像头桥接密钥不存在：{BRIDGE_SECRET_PATH}"
        )
    return BRIDGE_SECRET_PATH.read_text(encoding="utf-8").strip()


def _draw_label(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    cv2.putText(
        frame,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (12, 16, 22),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
        cv2.LINE_AA,
    )


def _render_detection_frame(
    frame: np.ndarray,
    payload: dict,
    source: str,
    show_boxes: bool,
) -> np.ndarray:
    display = cv2.flip(frame, 1) if source == "local" else frame.copy()
    height, width = display.shape[:2]
    mirrored = source == "local"

    def point(value: float, axis: str) -> int:
        normalized = 1.0 - value if mirrored and axis == "x" else value
        limit = width - 1 if axis == "x" else height - 1
        return max(0, min(limit, int(round(normalized * limit))))

    if show_boxes:
        eye_color = (
            (0, 0, 255)
            if payload.get("is_blinking")
            else (123, 209, 255)
        )
        mouth_color = (
            (0, 0, 255)
            if payload.get("is_yawning")
            else (106, 174, 255)
        )
        box_specs = (
            ("face", "face", None, (110, 226, 161)),
            ("left_eye", "L eye", payload.get("p_left"), eye_color),
            ("right_eye", "R eye", payload.get("p_right"), eye_color),
            ("mouth", "mouth", payload.get("p_mouth"), mouth_color),
        )
        for name, label, confidence, color in box_specs:
            box = (payload.get("boxes") or {}).get(name)
            if not box:
                continue
            x1 = point(box["x1"], "x")
            x2 = point(box["x2"], "x")
            if mirrored:
                x1, x2 = x2, x1
            y1 = point(box["y1"], "y")
            y2 = point(box["y2"], "y")
            thickness = (
                3
                if name in {"left_eye", "right_eye"} and payload.get("is_blinking")
                or name == "mouth" and payload.get("is_yawning")
                else 2
            )
            cv2.rectangle(
                display,
                (x1, y1),
                (x2, y2),
                color,
                thickness,
                cv2.LINE_AA,
            )
            caption = (
                f"{label} {float(confidence):.2f}"
                if confidence is not None
                else label
            )
            _draw_label(
                display,
                caption,
                x1,
                max(14, y1 - 6),
                color,
            )
    else:
        return display

    points: list[tuple[int, int] | None] = []
    for item in payload.get("keypoints") or []:
        if item.get("x") is None or item.get("y") is None:
            points.append(None)
        else:
            points.append((point(item["x"], "x"), point(item["y"], "y")))

    for start, end in ((0, 1), (0, 2), (0, 3), (0, 4), (3, 4)):
        if start >= len(points) or end >= len(points):
            continue
        if points[start] is None or points[end] is None:
            continue
        cv2.line(
            display,
            points[start],
            points[end],
            (105, 210, 255),
            2,
            cv2.LINE_AA,
        )

    for index, position in enumerate(points):
        if position is None:
            continue
        cv2.circle(display, position, 4, (105, 210, 255), -1, cv2.LINE_AA)
        if index < len(UPPER_BODY_KPT_NAMES):
            _draw_label(
                display,
                UPPER_BODY_KPT_NAMES[index],
                position[0] + 6,
                max(14, position[1] - 6),
                (105, 210, 255),
            )
    return display


class Handler(BaseHTTPRequestHandler):
    manager: SessionManager

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                self._json(200, {"ok": True, "service": "fatigue"})
                return
            if parsed.path == "/results":
                source = query.get("source", ["local"])[0]
                device_id = query.get("device_id", [""])[0]
                self._json(200, self.manager.results(source, device_id))
                return
            if parsed.path == "/feed":
                source = query.get("source", ["local"])[0]
                device_id = query.get("device_id", [""])[0]
                show_boxes = query.get("show_boxes", ["0"])[0] == "1"
                self._stream_feed(source, device_id, show_boxes)
                return
            self._json(404, {"ok": False, "message": "接口不存在"})
        except ValueError as exc:
            self._json(400, {"ok": False, "message": str(exc)})
        except Exception as exc:
            self._json(503, {"ok": False, "message": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path != "/reset":
                self._json(404, {"ok": False, "message": "接口不存在"})
                return
            source = query.get("source", ["local"])[0]
            device_id = query.get("device_id", [""])[0]
            self._json(200, self.manager.reset(source, device_id))
        except ValueError as exc:
            self._json(400, {"ok": False, "message": str(exc)})
        except Exception as exc:
            self._json(503, {"ok": False, "message": str(exc)})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _stream_feed(
        self,
        source: str,
        device_id: str,
        show_boxes: bool,
    ) -> None:
        try:
            _validate_camera_args(source, device_id)
            self.manager.frame_snapshot(source, device_id)
        except ValueError as exc:
            self._json(400, {"ok": False, "message": str(exc)})
            return
        except Exception as exc:
            self._json(503, {"ok": False, "message": str(exc)})
            return

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=frame",
        )
        self.send_header("Cache-Control", "no-store, no-cache")
        self.send_header("Pragma", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        last_sequence = -1
        last_activity = time.monotonic()
        try:
            while time.monotonic() - last_activity < 60.0:
                sequence, frame, payload = self.manager.frame_snapshot(
                    source,
                    device_id,
                )
                if frame is None or payload is None or sequence == last_sequence:
                    time.sleep(0.02)
                    continue
                rendered = _render_detection_frame(
                    frame,
                    payload,
                    source,
                    show_boxes,
                )
                ok, encoded = cv2.imencode(
                    ".jpg",
                    rendered,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 84],
                )
                if not ok:
                    continue
                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                    + encoded.tobytes()
                    + b"\r\n"
                )
                self.wfile.flush()
                last_sequence = sequence
                last_activity = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            self.close_connection = True

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(
            _json_safe(payload),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[fatigue-service] {fmt % args}", flush=True)


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="FatigueSense platform service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9101)
    args = parser.parse_args()

    bridge_url = os.getenv("FATIGUE_CAMERA_BRIDGE_URL", DEFAULT_BRIDGE_URL)
    manager = SessionManager(
        bridge_url=bridge_url,
        bridge_secret=_load_bridge_secret(),
    )
    Handler.manager = manager
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"[fatigue-service] listening on http://{args.host}:{args.port}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.close()
        server.server_close()


if __name__ == "__main__":
    main()
