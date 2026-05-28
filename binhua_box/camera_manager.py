"""
Camera stream manager – two independent paths:
  1. ffmpeg pulls RTSP/RTMP directly → pushes to SRS  (zero decode, low latency)
  2. OpenCV pulls same stream separately → feeds frames to algorithm runners
"""
import subprocess
import threading
import time
from collections.abc import Callable

import cv2
import numpy as np

from config import MAX_CONCURRENT_CAMERAS
from models import CameraState, CameraStatus, AlgorithmConfig

FrameCallback = Callable[[int, np.ndarray, list[AlgorithmConfig]], None]

# where SRS lives – can be overridden via env
import os
SRS_RTMP_HOST = os.environ.get("SRS_RTMP_HOST", "127.0.0.1")
SRS_RTMP_PORT = os.environ.get("SRS_RTMP_PORT", "1935")


def _ffmpeg_push_cmd(stream_url: str, stream_type: str, rtmp_url: str) -> list[str]:
    """Build the ffmpeg command to pull a stream and push to SRS (no re-encode)."""
    if stream_type in ("rtsp", "hik"):
        return [
            "ffmpeg", "-rtsp_transport", "tcp",
            "-i", stream_url,
            "-c", "copy", "-f", "flv",
            "-loglevel", "error",
            rtmp_url,
        ]
    elif stream_type == "rtmp":
        return [
            "ffmpeg", "-i", stream_url,
            "-c", "copy", "-f", "flv",
            "-loglevel", "error",
            rtmp_url,
        ]
    elif stream_type == "file":
        return [
            "ffmpeg", "-re", "-i", stream_url,
            "-c", "copy", "-f", "flv",
            "-loglevel", "error",
            rtmp_url,
        ]
    elif stream_type in ("local", "usb"):
        # local USB camera — ffmpeg reads from V4L2 device
        dev = f"/dev/video{stream_url}" if stream_url.isdigit() else stream_url
        return [
            "ffmpeg", "-f", "v4l2", "-i", dev,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
            "-f", "flv", "-loglevel", "error",
            rtmp_url,
        ]
    else:
        return [
            "ffmpeg", "-i", stream_url,
            "-c", "copy", "-f", "flv",
            "-loglevel", "error",
            rtmp_url,
        ]


class CameraManager:
    """Manages per-camera video capture (OpenCV) and SRS push (ffmpeg)."""

    def __init__(self):
        self._cameras: dict[int, CameraState] = {}
        self._captures: dict[int, cv2.VideoCapture] = {}
        self._ffmpeg_procs: dict[int, subprocess.Popen] = {}
        self._read_threads: dict[int, threading.Thread] = {}
        self._frame_callbacks: list[FrameCallback] = []
        self._latest_frames: dict[int, np.ndarray] = {}
        self._frame_lock = threading.Lock()
        self._stop_events: dict[int, threading.Event] = {}

    def get_snapshot(self, vid_id: int) -> np.ndarray | None:
        with self._frame_lock:
            return self._latest_frames.get(vid_id)

    # ── public API ────────────────────────────────────────────────────

    @property
    def cameras(self) -> dict[int, CameraState]:
        return self._cameras

    def on_frame(self, callback: FrameCallback) -> None:
        self._frame_callbacks.append(callback)

    def start_camera(self, vid_id: int, stream_url: str, stream_type: str,
                     publish_path: str, algorithms: list[AlgorithmConfig],
                     vid_serial: str = "") -> CameraState:
        if vid_id in self._cameras:
            state = self._cameras[vid_id]
            if state.status == CameraStatus.RUNNING:
                self._update_algorithms(vid_id, algorithms)
                return state
            self.stop_camera(vid_id)

        state = CameraState(
            vid_id=vid_id, vid_serial=vid_serial,
            stream_url=stream_url, stream_type=stream_type,
            publish_path=publish_path, algorithms=algorithms,
            status=CameraStatus.STARTING, started_at=time.time(),
        )
        self._cameras[vid_id] = state

        if len(self._captures) >= MAX_CONCURRENT_CAMERAS:
            state.status = CameraStatus.ERROR
            state.error_message = f"Max concurrent cameras ({MAX_CONCURRENT_CAMERAS}) reached"
            return state

        # 1) Start SRS push via ffmpeg (only for network streams; local USB uses V4L2 exclusive)
        if publish_path and stream_type not in ("local", "usb"):
            ok, err = self._start_srs_push(stream_url, stream_type, publish_path)
            if not ok:
                state.status = CameraStatus.ERROR
                state.error_message = err
                return state

        # 2) Start OpenCV capture for algorithm inference
        # local/USB摄像头: "4" → "/dev/video4" (ARM 上必须用路径)
        capture_source = stream_url
        if stream_type in ("local", "usb") and stream_url.isdigit():
            capture_source = f"/dev/video{stream_url}"
        try:
            cap = cv2.VideoCapture(capture_source)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            if not cap.isOpened():
                state.status = CameraStatus.ERROR
                state.error_message = f"Failed to open stream: {stream_url}"
                self._stop_srs_push(publish_path)
                return state
            self._captures[vid_id] = cap
        except Exception as e:
            state.status = CameraStatus.ERROR
            state.error_message = str(e)
            self._stop_srs_push(publish_path)
            return state

        thread = threading.Thread(target=self._read_loop, args=(vid_id,), daemon=True)
        self._read_threads[vid_id] = thread
        self._stop_events[vid_id] = threading.Event()
        thread.start()
        state.status = CameraStatus.RUNNING
        return state

    def stop_camera(self, vid_id: int) -> None:
        # signal the read loop to exit — the loop's finally block handles cap.release()
        stop_event = self._stop_events.pop(vid_id, None)
        if stop_event is not None:
            stop_event.set()
        thread = self._read_threads.pop(vid_id, None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        # stop SRS push — key is publish_path
        state = self._cameras.get(vid_id)
        if state and state.publish_path:
            self._stop_srs_push(state.publish_path)
        if vid_id in self._cameras:
            self._cameras[vid_id].status = CameraStatus.STOPPED
        else:
            self._cameras[vid_id] = CameraState(
                vid_id=vid_id,
                vid_serial="",
                stream_url="",
                stream_type="",
                publish_path="",
                status=CameraStatus.STOPPED,
            )

    def update_algorithms(self, vid_id: int, algorithms: list[AlgorithmConfig]) -> CameraState | None:
        if vid_id not in self._cameras:
            return None
        self._cameras[vid_id].algorithms = algorithms
        return self._cameras[vid_id]

    def _update_algorithms(self, vid_id: int, algorithms: list[AlgorithmConfig]) -> None:
        if vid_id in self._cameras:
            self._cameras[vid_id].algorithms = algorithms

    def get_device_status_list(self) -> list[dict]:
        return [
            {
                "vid_id": s.vid_id,
                "status": s.status.value,
                "start_time": s.started_at,
                "algorithm_count": len(s.algorithms),
                "algorithms": [a.code for a in s.algorithms],
                "error_message": s.error_message or "",
            }
            for s in self._cameras.values()
        ]

    def stop_all(self) -> None:
        for vid_id in list(self._cameras):
            self.stop_camera(vid_id)

    # ── ffmpeg SRS push ────────────────────────────────────────────────

    def _start_srs_push(self, stream_url: str, stream_type: str, publish_path: str) -> tuple[bool, str]:
        """Launch ffmpeg to pull source and push to SRS. Returns (success, error_message)."""
        rtmp_url = f"rtmp://{SRS_RTMP_HOST}:{SRS_RTMP_PORT}/live/{publish_path}"
        cmd = _ffmpeg_push_cmd(stream_url, stream_type, rtmp_url)
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            # Give it a moment to fail fast
            time.sleep(0.5)
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
                return False, f"ffmpeg push failed: {stderr[:200]}" if stderr else "ffmpeg push failed immediately"
            # Store by publish_path since multiple cameras share the manager
            self._ffmpeg_procs[publish_path] = proc
            return True, ""
        except FileNotFoundError:
            return False, "ffmpeg not found on box"
        except Exception as e:
            return False, str(e)

    def _stop_srs_push(self, key: str) -> None:
        proc = self._ffmpeg_procs.pop(key, None)
        if proc is None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ── OpenCV inference loop ──────────────────────────────────────────

    def _read_loop(self, vid_id: int) -> None:
        cap = self._captures.get(vid_id)
        if cap is None:
            return
        state = self._cameras.get(vid_id)

        DISCONNECT_THRESHOLD = 30
        consecutive_failures = 0
        frame_count = 0
        print(f"[DEBUG] camera: read_loop started vid={vid_id}", flush=True)

        try:
            stop_event = self._stop_events.get(vid_id)
            while vid_id in self._captures and self._captures.get(vid_id) is cap \
                    and (stop_event is None or not stop_event.is_set()):
                ret, frame = cap.read()
                frame_count += 1
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures >= DISCONNECT_THRESHOLD and state:
                        state.status = CameraStatus.ERROR
                        state.error_message = f"视频流中断，连续 {DISCONNECT_THRESHOLD} 帧读取失败"
                        self._stop_srs_push(state.publish_path)
                        return
                    time.sleep(0.1)
                    continue

                consecutive_failures = 0

                # store original frame for snapshot
                with self._frame_lock:
                    self._latest_frames[vid_id] = frame.copy()

                # resize for inference
                infer_frame = cv2.resize(frame, (640, 480)) if frame.shape[1] > 640 else frame

                if state and state.status == CameraStatus.RUNNING:
                    if frame_count % 150 == 1:
                        print(f"[DEBUG] camera: frame#{frame_count} vid={vid_id} shape={infer_frame.shape} algo_count={len(state.algorithms)}", flush=True)
                    for cb in self._frame_callbacks:
                        try:
                            cb(vid_id, infer_frame, state.algorithms)
                        except Exception:
                            pass
        finally:
            # release capture in the same thread that created it to avoid V4L2 races.
            # suppress V4L2 ioctl stderr noise during release on ARM.
            if cap.isOpened():
                try:
                    _devnull = os.open(os.devnull, os.O_WRONLY)
                    _stderr_fd = 2
                    _saved = os.dup(_stderr_fd)
                    os.dup2(_devnull, _stderr_fd)
                    os.close(_devnull)
                    cap.release()
                    os.dup2(_saved, _stderr_fd)
                    os.close(_saved)
                except Exception:
                    cap.release()
            self._captures.pop(vid_id, None)
