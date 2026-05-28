"""
Algorithm plugin: face_detection (人脸检测)
Uses the shared engine FaceDetector to find faces in each frame.
"""
import cv2
import numpy as np

from engine.face_detector import FaceDetector


class Algorithm:
    def __init__(self, params: dict) -> None:
        self.confidence = float(params.get("confidence", 0.55))
        self.detector = FaceDetector(confidence=self.confidence)

    def infer(self, frame: np.ndarray):
        faces = self.detector.detect(frame)
        if not faces:
            return None
        return {"faces": faces, "count": len(faces)}
