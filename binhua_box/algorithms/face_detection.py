"""
Example algorithm plugin: face_detection.

Each plugin must export a class named `Algorithm` with:
    __init__(self, params: dict)   – receive configuration from backend
    infer(self, frame: np.ndarray) – return dict or None
"""
from pathlib import Path

import cv2
import numpy as np

_WEIGHTS_DIR = Path(__file__).resolve().parents[1] / "weights"


class Algorithm:
    def __init__(self, params: dict) -> None:
        self.confidence = float(params.get("confidence", 0.55))
        self.net = None
        proto = _WEIGHTS_DIR / "deploy.prototxt"
        model = _WEIGHTS_DIR / "res10_300x300_ssd_iter_140000.caffemodel"
        if proto.exists() and model.exists():
            self.net = cv2.dnn.readNetFromCaffe(str(proto), str(model))

    def infer(self, frame: np.ndarray) -> dict | None:
        if self.net is None:
            return None

        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
        self.net.setInput(blob)
        detections = self.net.forward()

        faces = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence < self.confidence:
                continue
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype("int")
            faces.append({"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2),
                          "confidence": round(confidence, 3)})

        return {"faces": faces, "count": len(faces)} if faces else None
