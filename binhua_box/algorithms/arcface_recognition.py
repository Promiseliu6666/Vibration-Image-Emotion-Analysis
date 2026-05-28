"""
Algorithm plugin: arcface_recognition (人脸特征识别)
Runs face detection + ArcFace embedding extraction on Ascend NPU or CPU ONNX.
Sends face crop image (base64) to backend for database comparison.
"""
import base64
import importlib

import cv2
import numpy as np

from engine.face_detector import FaceDetector


def _load_extractor():
    """Try Ascend NPU first, fall back to ONNX CPU."""
    for mod_name in ("engine.arcface_onnx", "engine.arcface_ascend"):
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, "ArcFaceExtractorAscend", None) or getattr(mod, "ArcFaceExtractorONNX", None)
            if cls:
                print(f"[arcface_recognition] using {mod_name}", flush=True)
                return cls()
        except Exception as e:
            print(f"[arcface_recognition] {mod_name} failed: {e}", flush=True)
            continue
    raise RuntimeError("No ArcFace extractor available (tried Ascend, ONNX)")


class Algorithm:
    def __init__(self, params: dict) -> None:
        self.confidence = float(params.get("confidence", 0.55))
        self.detector = FaceDetector(confidence=self.confidence)
        self.extractor = _load_extractor()

    def infer(self, frame: np.ndarray):
        face = self.detector.get_largest_face(frame)
        if face is None:
            return None

        x1, y1 = max(0, face["x1"]), max(0, face["y1"])
        x2, y2 = min(frame.shape[1], face["x2"]), min(frame.shape[0], face["y2"])
        if x2 <= x1 or y2 <= y1:
            return None

        face_crop = frame[y1:y2, x1:x2]
        embedding = self.extractor.extract(face_crop)

        _, jpeg = cv2.imencode(".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
        face_image_b64 = base64.b64encode(jpeg).decode()

        return {
            "face_image": face_image_b64,
            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            "confidence": face["confidence"],
            "embedding": embedding.tolist(),
        }
