import base64
import io
import os
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

from module_xuzhou.error.people_error import InvalidPictureError

BACKEND_ROOT = Path(__file__).resolve().parents[2]

_onnx_model_path = os.environ.get(
    "FACE_RECOGNITION_MODEL",
    str(BACKEND_ROOT / "algorithm" / "model" / "arcface_recognition" / "v1" / "w600k_r50.onnx"),
)

_session = None
_input_name: str = ""
_output_name: str = ""


def _get_session():
    global _session, _input_name, _output_name
    if _session is not None:
        return _session, _input_name, _output_name

    if not os.path.exists(_onnx_model_path):
        raise FileNotFoundError(
            f"ArcFace ONNX model not found: {_onnx_model_path}. "
            "Download w600k_r50.onnx from InsightFace buffalo_l pack: "
            "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
        )

    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    _session = ort.InferenceSession(
        _onnx_model_path,
        sess_options=opts,
        providers=["DmlExecutionProvider", "CPUExecutionProvider"],
    )
    _input_name = _session.get_inputs()[0].name
    _output_name = _session.get_outputs()[0].name
    return _session, _input_name, _output_name


def _preprocess_face(face_image: np.ndarray) -> np.ndarray:
    if face_image.dtype != np.uint8:
        face_image = np.clip(face_image, 0, 255).astype(np.uint8)

    # ArcFace expects 112x112 RGB
    face_resized = cv2.resize(face_image, (112, 112))
    if len(face_resized.shape) == 2:
        face_resized = cv2.cvtColor(face_resized, cv2.COLOR_GRAY2RGB)
    elif face_resized.shape[2] == 4:
        face_resized = cv2.cvtColor(face_resized, cv2.COLOR_BGRA2RGB)
    else:
        face_resized = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)

    # Normalize to [-1, 1]
    face_float = face_resized.astype(np.float32)
    face_float = (face_float - 127.5) / 127.5

    # HWC → CHW → add batch dim: (1, 3, 112, 112)
    return np.expand_dims(np.transpose(face_float, (2, 0, 1)), axis=0)


def _decode_base64(image_str: str) -> np.ndarray:
    if not image_str:
        raise InvalidPictureError("Empty image string")
    if "," in image_str:
        image_str = image_str.split(",", 1)[1]
    image_str = image_str.strip()
    img_data = base64.b64decode(image_str)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise InvalidPictureError("Cannot decode image")
    return img


def _detect_face(image_np: np.ndarray) -> np.ndarray:
    """Detect largest face using OpenCV DNN (no PaddlePaddle dependency)."""
    face_detector = _get_face_detector()
    h, w = image_np.shape[:2]
    image_640 = cv2.resize(image_np, (640, 480))

    # Try DNN first
    net = face_detector.get("dnn_net")
    if net is not None:
        try:
            blob = cv2.dnn.blobFromImage(image_640, 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            best_box = None
            best_conf = 0.55
            for i in range(detections.shape[2]):
                confidence = float(detections[0, 0, i, 2])
                if confidence <= best_conf:
                    continue
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype("int")
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 > x1 and y2 > y1:
                    best_conf = confidence
                    best_box = (x1, y1, x2, y2)
            if best_box:
                x1, y1, x2, y2 = best_box
                return image_np[y1:y2, x1:x2]
        except Exception:
            pass

    # Fallback to Haar cascade
    gray = cv2.cvtColor(image_640, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    cascade = face_detector.get("haar_cascade")
    if cascade is not None:
        faces = cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=6, minSize=(90, 90))
        if len(faces) > 0:
            x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
            x1, y1 = max(0, int(x * w / 640)), max(0, int(y * h / 480))
            x2, y2 = min(w, int((x + fw) * w / 640)), min(h, int((y + fh) * h / 480))
            if x2 > x1 and y2 > y1:
                return image_np[y1:y2, x1:x2]

    raise InvalidPictureError("No face detected")


_face_detector_cache: dict = {}


def _get_face_detector() -> dict:
    if _face_detector_cache:
        return _face_detector_cache

    result: dict = {"dnn_net": None, "haar_cascade": None}

    # Try loading DNN model
    for proto_path, model_path in [
        (
            BACKEND_ROOT / "algorithm" / "model" / "face_detection" / "v1" / "deploy.prototxt",
            BACKEND_ROOT / "algorithm" / "model" / "face_detection" / "v1" / "res10_300x300_ssd_iter_140000.caffemodel",
        ),
        (BACKEND_ROOT / "deploy.prototxt", BACKEND_ROOT / "res10_300x300_ssd_iter_140000.caffemodel"),
        (BACKEND_ROOT / "hik_vision" / "deploy.prototxt", BACKEND_ROOT / "hik_vision" / "res10_300x300_ssd_iter_140000.caffemodel"),
    ]:
        if proto_path.exists() and model_path.exists():
            try:
                result["dnn_net"] = cv2.dnn.readNetFromCaffe(str(proto_path), str(model_path))
                break
            except Exception:
                pass

    # Load Haar cascade
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    if os.path.exists(cascade_path):
        result["haar_cascade"] = cv2.CascadeClassifier(cascade_path)

    _face_detector_cache.update(result)
    return _face_detector_cache


def extract_features(image_str: str) -> np.ndarray:
    """Extract face features from base64 image string."""
    image_np = _decode_base64(image_str)
    face_crop = _detect_face(image_np)
    return extract_features_from_face_image(face_crop)


def extract_large_features(image_str: str) -> np.ndarray:
    """Alias for extract_features."""
    return extract_features(image_str)


def extract_features_from_face_image(face_image: np.ndarray) -> np.ndarray:
    """Extract features from a pre-cropped face image."""
    if face_image is None or not isinstance(face_image, np.ndarray) or face_image.size == 0:
        raise InvalidPictureError("Invalid face image")

    session, input_name, output_name = _get_session()
    input_tensor = _preprocess_face(face_image)
    outputs = session.run([output_name], {input_name: input_tensor})
    embedding = outputs[0][0]

    # L2 normalize
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding.astype(np.float64)