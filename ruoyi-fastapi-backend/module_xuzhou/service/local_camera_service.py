"""
Local camera capture service – runs on the backend server for cameras
that do NOT belong to a box (vidBoxSerial is empty / NULL).

Two independent paths:
  - USB / local  → OpenCV direct capture → MJPEG / snapshot
  - RTSP / RTMP  → ffmpeg subprocess → MJPEG frames → direct serve (no SRS needed)
"""

import io
import os
import subprocess
import threading
import time
from collections.abc import Callable

import cv2
import numpy as np

# ── callback type ──────────────────────────────────────────────────────

FrameCallback = Callable[[int, np.ndarray], None]

# ── singleton ──────────────────────────────────────────────────────────

class LocalCameraManager:
    """Manages OpenCV captures (USB) and ffmpeg MJPEG pipes (RTSP) for server-local cameras."""

    MAX_CAMERAS = 8

    def __init__(self):
        # OpenCV path (USB / local)
        self._captures: dict[int, cv2.VideoCapture] = {}
        # ffmpeg MJPEG path (RTSP / RTMP / HTTP) — stores JPEG bytes, not numpy arrays
        self._ffmpeg_procs: dict[int, subprocess.Popen] = {}
        self._mjpeg_frames: dict[int, bytes] = {}  # latest JPEG frame from ffmpeg
        self._threads: dict[int, threading.Thread] = {}
        self._latest_frames: dict[int, np.ndarray] = {}  # OpenCV numpy frames
        self._frame_idxs: dict[int, int] = {}
        self._states: dict[int, dict] = {}
        self._frame_callbacks: list[FrameCallback] = []
        self._lock = threading.Lock()

    # ── frame callbacks ─────────────────────────────────────────────

    def on_frame(self, callback: FrameCallback) -> None:
        """Register a callback invoked for every frame from every running camera."""
        if callback not in self._frame_callbacks:
            self._frame_callbacks.append(callback)

    def remove_frame_callback(self, callback: FrameCallback) -> None:
        """Remove a previously registered frame callback."""
        try:
            self._frame_callbacks.remove(callback)
        except ValueError:
            pass

    # ── public API ──────────────────────────────────────────────────

    def running(self, vid_id: int) -> bool:
        """Check if camera is running (either OpenCV or ffmpeg path)."""
        return vid_id in self._captures or vid_id in self._ffmpeg_procs

    def get_snapshot(self, vid_id: int) -> np.ndarray | None:
        with self._lock:
            return self._latest_frames.get(vid_id)

    def get_mjpeg_frame(self, vid_id: int) -> bytes | None:
        """Get latest JPEG frame from ffmpeg MJPEG path."""
        with self._lock:
            return self._mjpeg_frames.get(vid_id)

    def get_snapshot_with_idx(self, vid_id: int) -> tuple[np.ndarray | None, int]:
        """Returns (frame, index). Index increments on every new frame."""
        with self._lock:
            return self._latest_frames.get(vid_id), self._frame_idxs.get(vid_id, -1)

    def is_rtsp_camera(self, vid_id: int) -> bool:
        """Check if this camera uses the ffmpeg MJPEG path (RTSP/RTMP/HTTP)."""
        s = self._states.get(vid_id, {})
        return s.get("stream_type", "") in ("rtsp", "rtmp", "http", "https")

    def get_status(self, vid_id: int) -> dict:
        s = self._states.get(vid_id, {})
        return {
            "vid_id": vid_id,
            "status": "running" if self.running(vid_id) else "stopped",
            "started_at": s.get("started_at"),
            "error_message": s.get("error_message", ""),
        }

    def start_camera(self, vid_id: int, source: str, stream_type: str = "usb") -> str:
        """Launch camera capture. Non-blocking, returns immediately."""
        if self.running(vid_id):
            return ""

        active_count = len(self._captures) + len(self._ffmpeg_procs)
        if active_count >= self.MAX_CAMERAS:
            return f"已达到最大摄像头数量限制 ({self.MAX_CAMERAS})"

        self._states[vid_id] = {
            "started_at": time.time(),
            "source": source,
            "stream_type": stream_type,
            "error_message": "",
        }

        if stream_type in ("rtsp", "rtmp", "http", "https"):
            # Network stream → ffmpeg pulls RTSP → outputs MJPEG frames → serve directly
            return self._start_ffmpeg_mjpeg(vid_id, source, stream_type)
        else:
            # USB / local → OpenCV → MJPEG
            return self._start_opencv_capture(vid_id, source, stream_type)

    def stop_camera(self, vid_id: int) -> None:
        # Stop ffmpeg
        proc = self._ffmpeg_procs.pop(vid_id, None)
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

        # Stop OpenCV
        cap = self._captures.pop(vid_id, None)
        if cap:
            cap.release()

        self._threads.pop(vid_id, None)

        with self._lock:
            self._latest_frames.pop(vid_id, None)
            self._mjpeg_frames.pop(vid_id, None)
        self._frame_idxs.pop(vid_id, None)

        s = self._states.get(vid_id, {})
        s["status"] = "stopped"
        self._states[vid_id] = s

    def stop_all(self) -> None:
        for vid_id in list(self._states):
            self.stop_camera(vid_id)

    # ── ffmpeg MJPEG path (RTSP / RTMP / HTTP) ───────────────────────

    def _start_ffmpeg_mjpeg(self, vid_id: int, source: str, stream_type: str) -> str:
        """Launch ffmpeg to pull RTSP and output MJPEG frames to stdout pipe.
        No SRS required — frames are read from pipe and served directly."""
        from utils.log_util import logger

        # ffmpeg pulls RTSP → outputs JPEG frames via image2pipe (raw JPEG stream)
        cmd = [
            "ffmpeg", "-rtsp_transport", "tcp",
            "-i", source,
            "-vcodec", "mjpeg", "-q:v", "5", "-r", "10",
            "-an",
            "-f", "image2pipe",
            "pipe:1",
        ]

        logger.info(f"[local_camera] vid={vid_id} 启动 ffmpeg MJPEG: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            # Background thread reads JPEG frames from ffmpeg stdout pipe
            t = threading.Thread(
                target=self._read_mjpeg_pipe,
                args=(vid_id, proc, source),
                daemon=True,
            )
            t.start()

            # Mark as running after short delay if ffmpeg hasn't crashed
            def _confirm():
                time.sleep(3)
                if proc.poll() is not None:
                    logger.error(f"[local_camera] vid={vid_id} ffmpeg MJPEG 进程退出 (code={proc.poll()})")
                    self._states[vid_id]["error_message"] = f"ffmpeg 进程异常退出 (code={proc.poll()})"
                else:
                    logger.info(f"[local_camera] vid={vid_id} ffmpeg MJPEG 运行中, source={source}")
                    self._ffmpeg_procs[vid_id] = proc

            threading.Thread(target=_confirm, daemon=True).start()
            return ""

        except FileNotFoundError:
            msg = "ffmpeg 未安装，请先安装 ffmpeg"
            logger.error(f"[local_camera] vid={vid_id} {msg}")
            self._states[vid_id]["error_message"] = msg
            return msg
        except Exception as e:
            logger.error(f"[local_camera] vid={vid_id} ffmpeg 启动异常: {e}")
            self._states[vid_id]["error_message"] = str(e)
            return str(e)

    def _read_mjpeg_pipe(self, vid_id: int, proc: subprocess.Popen, source: str) -> None:
        """Read JPEG frames from ffmpeg stdout pipe, parse frame boundaries."""
        from utils.log_util import logger

        buf = b""
        JPEG_START = b"\xff\xd8"
        JPEG_END = b"\xff\xd9"

        try:
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk

                # Extract complete JPEG frames from buffer
                while True:
                    start = buf.find(JPEG_START)
                    if start == -1:
                        break
                    # Find end marker AFTER the start marker (could be same byte)
                    end = buf.find(JPEG_END, start + 2)
                    if end == -1:
                        break
                    # Extract the JPEG frame
                    jpeg_data = buf[start:end + 2]
                    buf = buf[end + 2:]

                    # Store latest frame
                    with self._lock:
                        self._mjpeg_frames[vid_id] = jpeg_data
        except Exception as e:
            logger.error(f"[local_camera] vid={vid_id} MJPEG pipe read error: {e}")
        finally:
            logger.info(f"[local_camera] vid={vid_id} MJPEG pipe closed")

    # ── OpenCV path (USB / local) ────────────────────────────────────

    def _start_opencv_capture(self, vid_id: int, source: str, stream_type: str) -> str:
        """Spawn background thread for OpenCV capture."""
        t = threading.Thread(
            target=self._connect_and_read_loop,
            args=(vid_id, source, stream_type),
            daemon=True,
        )
        self._threads[vid_id] = t
        t.start()
        return ""

    def _connect_and_read_loop(self, vid_id: int, source: str, stream_type: str) -> None:
        """Background: set FFmpeg timeout, open capture, then enter read loop."""
        self._set_ffmpeg_timeout()

        if stream_type in ("local", "usb"):
            capture_source = int(source) if source.isdigit() else source
        else:
            capture_source = source

        try:
            cap = cv2.VideoCapture(capture_source)
            if not cap.isOpened():
                self._states[vid_id]["error_message"] = f"无法打开摄像头: {source}"
                self._threads.pop(vid_id, None)
                return
            self._captures[vid_id] = cap
        except Exception as e:
            self._states[vid_id]["error_message"] = str(e)
            self._threads.pop(vid_id, None)
            return

        self._read_loop(vid_id)

    # ── internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _set_ffmpeg_timeout(timeout_sec: int = 5) -> None:
        """Set FFmpeg socket/read timeouts to avoid default 30 s block on dead streams."""
        timeout_us = timeout_sec * 1_000_000
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            f"rtsp_transport;tcp|timeout;{timeout_us}",
        )
        os.environ.setdefault(
            "OPENCV_FFMPEG_READ_TIMEOUT_MS",
            str(timeout_sec * 1000),
        )

    def _read_loop(self, vid_id: int) -> None:
        cap = self._captures.get(vid_id)
        if cap is None:
            return

        DISCONNECT_THRESHOLD = 30
        failures = 0

        while vid_id in self._captures:
            ret, frame = cap.read()
            if not ret:
                failures += 1
                if failures >= DISCONNECT_THRESHOLD:
                    self._states[vid_id] = {
                        **self._states.get(vid_id, {}),
                        "error_message": f"视频流中断，连续 {DISCONNECT_THRESHOLD} 帧读取失败",
                    }
                    self.stop_camera(vid_id)
                    return
                time.sleep(0.1)
                continue

            failures = 0
            with self._lock:
                self._latest_frames[vid_id] = frame.copy()
                self._frame_idxs[vid_id] = self._frame_idxs.get(vid_id, 0) + 1

            # invoke registered frame callbacks (algorithm runners, etc.)
            for cb in self._frame_callbacks:
                try:
                    cb(vid_id, frame)
                except Exception:
                    pass


# singleton instance
local_camera_manager = LocalCameraManager()
