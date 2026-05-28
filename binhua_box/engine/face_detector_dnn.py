"""
Face detector using OpenCV DNN with Caffe SSD model.
Same model as the local server — no Ascend NPU required.

Model files expected in binhua_box/models/:
  - deploy.prototxt   (Caffe SSD network definition)
  - res10_300x300_ssd_iter_140000.caffemodel  (pretrained weights)
"""
import os
from pathlib import Path

import cv2
import numpy as np

_MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
_PROTO_PATH = str(_MODELS_DIR / "deploy.prototxt")
_WEIGHTS_PATH = str(_MODELS_DIR / "res10_300x300_ssd_iter_140000.caffemodel")

# Download URLs (same as local server)
_PROTO_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
_WEIGHTS_URL = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"


def _ensure_model():
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    import urllib.request

    if not os.path.exists(_PROTO_PATH):
        print(f"[DNN] 下载 {_PROTO_URL} ...")
        urllib.request.urlretrieve(_PROTO_URL, _PROTO_PATH)
    if not os.path.exists(_WEIGHTS_PATH):
        print(f"[DNN] 下载 {_WEIGHTS_URL} ...")
        urllib.request.urlretrieve(_WEIGHTS_URL, _WEIGHTS_PATH)


class FaceDetectorDNN:
    def __init__(self, confidence: float = 0.55):
        _ensure_model()
        self.confidence = confidence
        self.net = cv2.dnn.readNetFromCaffe(_PROTO_PATH, _WEIGHTS_PATH)
        print(f"[DNN] 人脸检测模型加载成功 (confidence={confidence})")

    def detect(self, frame: np.ndarray) -> list[dict]:
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)),
            1.0, (300, 300),
            (104.0, 177.0, 123.0),
        )
        self.net.setInput(blob)
        detections = self.net.forward()

        faces = []
        for i in range(detections.shape[2]):
            score = float(detections[0, 0, i, 2])
            if score < self.confidence:
                continue
            x1 = int(detections[0, 0, i, 3] * w)
            y1 = int(detections[0, 0, i, 4] * h)
            x2 = int(detections[0, 0, i, 5] * w)
            y2 = int(detections[0, 0, i, 6] * h)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            faces.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "confidence": round(score, 3),
            })
        return faces

    def get_largest_face(self, frame: np.ndarray):
        faces = self.detect(frame)
        if not faces:
            return None
        return max(faces, key=lambda f: (f["x2"] - f["x1"]) * (f["y2"] - f["y1"]))
