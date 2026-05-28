"""
ArcFace feature extractor using OpenCV DNN (CPU, no extra deps).
Model: w600k_r50.onnx from InsightFace buffalo_l pack.
"""
import os
from pathlib import Path

import cv2
import numpy as np

_MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
_MODEL_PATH = str(_MODELS_DIR / "w600k_r50.onnx")


class ArcFaceExtractorONNX:
    def __init__(self):
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(f"ArcFace model not found: {_MODEL_PATH}")
        self.net = cv2.dnn.readNetFromONNX(_MODEL_PATH)

    def extract(self, face_crop: np.ndarray) -> np.ndarray:
        """Extract 512-dim L2-normalized embedding from BGR face crop."""
        img = cv2.resize(face_crop, (112, 112))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32)
        img = (img - 127.5) / 127.5
        blob = cv2.dnn.blobFromImage(img)

        self.net.setInput(blob)
        vec = self.net.forward().flatten()

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.astype(np.float32)
