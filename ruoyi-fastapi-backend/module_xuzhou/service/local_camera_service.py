"""
Local camera capture service – runs on the backend server for cameras
that do NOT belong to a box (vidBoxSerial is empty / NULL).

Supports:
  - USB cameras   → OpenCV direct capture → MJPEG / snapshot
  - RTSP / file   → OpenCV can also read these; otherwise SRS/FLV is used
"""

import threading
import time

import cv2
import numpy as np

# ── singleton ──────────────────────────────────────────────────────────

class LocalCameraManager:
    """Manages OpenCV captures for server-local cameras."""

    MAX_CAMERAS = 8

    def __init__(self):
        self._captures: dict[int, cv2.VideoCapture] = {}
        self._threads: dict[int, threading.Thread] = {}
        self._latest_frames: dict[int, np.ndarray] = {}
        self._frame_idxs: dict[int, int] = {}
        self._states: dict[int, dict] = {}
        self._lock = threading.Lock()

    # ── public API ──────────────────────────────────────────────────

    def running(self, vid_id: int) -> bool:
        return vid_id in self._captures

    def get_snapshot(self, vid_id: int) -> np.ndarray | None:
        with self._lock:
            return self._latest_frames.get(vid_id)

    def get_snapshot_with_idx(self, vid_id: int) -> tuple[np.ndarray | None, int]:
        """Returns (frame, index).  Index increments on every new frame so
        the stream generator can skip duplicates without extra encoding."""
        with self._lock:
            return self._latest_frames.get(vid_id), self._frame_idxs.get(vid_id, -1)

    def get_status(self, vid_id: int) -> dict:
        s = self._states.get(vid_id, {})
        return {
            "vid_id": vid_id,
            "status": "running" if self.running(vid_id) else "stopped",
            "started_at": s.get("started_at"),
            "error_message": s.get("error_message", ""),
        }

    def start_camera(self, vid_id: int, source: str, stream_type: str = "usb") -> str:
        """Launch OpenCV capture.  Returns empty string on success, error message on failure."""
        if vid_id in self._captures:
            return ""

        if len(self._captures) >= self.MAX_CAMERAS:
            return f"已达到最大摄像头数量限制 ({self.MAX_CAMERAS})"

        # USB: source is a device index like "0" → cv2.VideoCapture(0)
        # The box convention passes "4" for /dev/video4; on Windows we try
        if stream_type in ("local", "usb"):
            if source.isdigit():
                capture_source = int(source)
            else:
                capture_source = source
        else:
            capture_source = source

        try:
            cap = cv2.VideoCapture(capture_source)
            if not cap.isOpened():
                return f"无法打开摄像头: {source}"
            self._captures[vid_id] = cap
        except Exception as e:
            return str(e)

        self._states[vid_id] = {
            "started_at": time.time(),
            "source": source,
            "stream_type": stream_type,
            "error_message": "",
        }

        t = threading.Thread(target=self._read_loop, args=(vid_id,), daemon=True)
        self._threads[vid_id] = t
        t.start()
        return ""

    def stop_camera(self, vid_id: int) -> None:
        t = self._threads.pop(vid_id, None)
        cap = self._captures.pop(vid_id, None)
        if cap:
            cap.release()
        if vid_id in self._latest_frames:
            del self._latest_frames[vid_id]
        self._frame_idxs.pop(vid_id, None)
        s = self._states.get(vid_id, {})
        s["status"] = "stopped"
        self._states[vid_id] = s

    def stop_all(self) -> None:
        for vid_id in list(self._captures):
            self.stop_camera(vid_id)

    # ── internal ────────────────────────────────────────────────────

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


# singleton instance
local_camera_manager = LocalCameraManager()
