"""
Algorithm plugin: realtime_face_analysis (实时人脸幸福指数分析)
Detects faces, tracks stability, runs vibraimage happiness analysis,
records 10-second video clips on stable detection.
"""
import base64
import subprocess
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from engine.face_detector import FaceDetector
from engine.vibraimage import VibraimageCore

_VIDEO_DIR = Path(__file__).resolve().parents[1] / "videos"


class Algorithm:
    def __init__(self, params: dict) -> None:
        self.confidence = float(params.get("confidence", 0.55))
        self.record_duration = float(params.get("record_duration", 10.0))
        self.face_detect_interval = int(params.get("face_detect_interval", 3))
        self.stable_frames_required = int(params.get("stable_frames_required", 5))
        self.tolerance = int(params.get("tolerance", 60))
        self.lost_check_interval = int(params.get("lost_check_interval", 20))
        self.stream_url = params.get("stream_url", "")
        self.stream_type = params.get("stream_type", "")

        self.detector = FaceDetector(confidence=self.confidence)
        self.analyzer = VibraimageCore()
        self.analyzer.halo_params["ACCUMULATE_FRAMES"] = 5

        self.stable_count = 0
        self.prev_center = None
        self.prev_size = None
        self.locked_rect = None
        self.analyzing = False
        self.frame_count = 0
        self.analysis_start_time = None
        self.analysis_completed = False

        self._ffmpeg_proc = None
        self.video_start_time = None
        self.current_video_path = None

        self._arcface = None
        self._cached_face_vector = None
        self._cached_face_image = None
        self._cached_annotated = None
        self._cached_face_bbox = None

        _VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    def _get_arcface(self):
        if self._arcface is not None:
            return self._arcface
        for mod_name in ("engine.arcface_onnx", "engine.arcface_ascend"):
            try:
                import importlib
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, "ArcFaceExtractorAscend", None) or getattr(mod, "ArcFaceExtractorONNX", None)
                if cls:
                    self._arcface = cls()
                    return self._arcface
            except Exception:
                continue
        return None

    def _extract_face_info(self, frame, face_rect):
        """Extract face crop, vector, and annotated frame once per stable lock."""
        x, y, w, h = face_rect
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)

        annotated = frame.copy()
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
        _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
        self._cached_annotated = base64.b64encode(jpeg).decode()
        self._cached_face_bbox = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

        face_crop = frame[y1:y2, x1:x2]
        if face_crop.size > 0:
            _, face_jpeg = cv2.imencode(".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
            self._cached_face_image = base64.b64encode(face_jpeg).decode()

            arcface = self._get_arcface()
            if arcface is not None:
                try:
                    emb = arcface.extract(face_crop)
                    self._cached_face_vector = emb.tolist()
                except Exception:
                    pass

    def _start_ffmpeg_recording(self):
        """Record video clip directly from RTSP source via ffmpeg."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = str(_VIDEO_DIR / f"vibra_{ts}.mp4")
        cmd = ["ffmpeg", "-y"]
        if self.stream_type in ("rtsp", "hik"):
            cmd += ["-rtsp_transport", "tcp"]
        cmd += [
            "-i", self.stream_url,
            "-t", str(self.record_duration),
            "-c", "copy",
            "-loglevel", "error",
            video_path,
        ]
        try:
            self._ffmpeg_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.video_start_time = time.time()
            self.current_video_path = video_path
            return True
        except Exception as e:
            print(f"[DEBUG] vibra: ffmpeg recording start failed: {e}", flush=True)
            return False

    def _stop_ffmpeg_recording(self):
        if self._ffmpeg_proc is None:
            return
        try:
            self._ffmpeg_proc.terminate()
            self._ffmpeg_proc.wait(timeout=5)
        except Exception:
            try:
                self._ffmpeg_proc.kill()
            except Exception:
                pass
        self._ffmpeg_proc = None

    def _reset_state(self):
        self.stable_count = 0
        self.prev_center = None
        self.prev_size = None
        self.locked_rect = None
        self.analyzing = False
        self.analysis_completed = False
        self.analysis_start_time = None
        self.analyzer.reset()
        self._cached_face_vector = None
        self._cached_face_image = None
        self._cached_annotated = None
        self._cached_face_bbox = None
        self._stop_ffmpeg_recording()
        self.video_start_time = None
        self.current_video_path = None

    def infer(self, frame: np.ndarray):
        self.frame_count += 1
        results = {}

        face_rect = None

        if self.analyzing and self.locked_rect is not None:
            face_rect = self.locked_rect
        elif self.frame_count % self.face_detect_interval == 0:
            face = self.detector.get_largest_face(frame)
            if face is not None:
                x1, y1 = face["x1"], face["y1"]
                x2, y2 = face["x2"], face["y2"]
                w, h = x2 - x1, y2 - y1
                face_rect = (x1, y1, w, h)
                center = (x1 + w // 2, y1 + h // 2)
                size = (w, h)

                if self.prev_center is not None:
                    center_dist = np.linalg.norm(
                        np.array(center) - np.array(self.prev_center)
                    )
                    size_dist = np.linalg.norm(
                        np.array(size) - np.array(self.prev_size)
                    )
                    if center_dist < self.tolerance and size_dist < self.tolerance:
                        self.stable_count += 1
                    else:
                        self.stable_count = 0
                else:
                    self.stable_count = 1

                self.prev_center = center
                self.prev_size = size
                if self.stable_count > 0:
                    print(f"[DEBUG] vibra: frame#{self.frame_count} face found stable={self.stable_count}/{self.stable_frames_required}", flush=True)
            elif self.stable_count > 0:
                print(f"[DEBUG] vibra: frame#{self.frame_count} face lost", flush=True)
                self.stable_count = 0

        if self.analyzing and self.frame_count % self.lost_check_interval == 0:
            current_face = self.detector.get_largest_face(frame)
            if current_face is None:
                self._reset_state()
                face_rect = None

        # trigger vibraimage analysis when face becomes stable
        if (
            not self.analyzing
            and face_rect is not None
            and self.stable_count >= self.stable_frames_required
        ):
            self.locked_rect = face_rect
            self.analyzing = True
            self.analysis_start_time = time.time()
            self.analyzer.reset()
            self._extract_face_info(frame, face_rect)
            # start ffmpeg recording from source stream
            if self.stream_url:
                self._start_ffmpeg_recording()
            print(f"[DEBUG] vibra: analysis started, recording video...", flush=True)

        if face_rect is not None:
            vibra_results = self.analyzer.process_frame(frame, face_rect=face_rect, fps=30)
            if vibra_results:
                results.update(vibra_results)

        # check if recording duration reached
        if self.analyzing and not self.analysis_completed:
            if self.video_start_time is not None:
                elapsed = time.time() - self.video_start_time
                if elapsed >= self.record_duration:
                    self.video_start_time = None
                    self.analysis_completed = True
                    results["video_path"] = self.current_video_path
                    results["analysis_completed"] = True
                    print(f"[DEBUG] vibra: recording done path={self.current_video_path}", flush=True)
                    if self._cached_annotated:
                        results["image"] = self._cached_annotated
                    if self._cached_face_bbox:
                        results["face_bbox"] = self._cached_face_bbox
                    if self._cached_face_image:
                        results["face_image"] = self._cached_face_image
                    if self._cached_face_vector:
                        results["face_vector"] = self._cached_face_vector

        return results if results else None
