"""
Face detector for Huawei Ascend NPU — uses ACL Python API to load .om model.
Model: Caffe SSD face detection converted via ATC:
  atc --model=deploy.prototxt --weight=res10_300x300_ssd_iter_140000.caffemodel \
      --framework=0 --output=face_detection --soc_version=Ascend310B4 \
      --input_shape="data:1,3,300,300" --input_format=NCHW
"""
import os
from pathlib import Path

import acl
import numpy as np

_WEIGHTS_DIR = Path(__file__).resolve().parents[1] / "weights"
_MODEL_PATH = str(_WEIGHTS_DIR / "face_detection.om")

# image mean values for Caffe SSD
_MEAN = np.array([104.0, 177.0, 123.0], dtype=np.float32)


class FaceDetectorAscend:
    def __init__(self, confidence: float = 0.55):
        self.confidence = confidence
        self.device_id = int(os.environ.get("ASCEND_DEVICE_ID", "0"))

        ret = acl.init()
        if ret != 0:
            raise RuntimeError(f"acl.init failed: {ret}")

        self.context, ret = acl.rt.create_context(self.device_id)
        if ret != 0:
            raise RuntimeError(f"acl.rt.create_context failed: {ret}")

        self.model_id, self.model_desc = acl.mdl.load_from_file(_MODEL_PATH)
        if self.model_id is None:
            raise RuntimeError(f"Failed to load model: {_MODEL_PATH}")

        # input: 1,3,300,300 float32 NCHW
        self.input_size = 300
        self.input_buffer_size = 3 * self.input_size * self.input_size * 4  # float32

        self.device_input, ret = acl.rt.malloc(self.input_buffer_size, 0)
        if ret != 0:
            raise RuntimeError(f"acl.rt.malloc input failed: {ret}")

        # output size — allocate generously for 200 detections
        self.output_buffer_size = 200 * 7 * 4  # 200 boxes × 7 values × float32
        self.device_output, ret = acl.rt.malloc(self.output_buffer_size, 0)
        if ret != 0:
            raise RuntimeError(f"acl.rt.malloc output failed: {ret}")

        self.input_dataset = acl.mdl.create_dataset()
        acl.mdl.add_dataset_buffer(
            self.input_dataset, self.device_input, self.input_buffer_size
        )
        self.output_dataset = acl.mdl.create_dataset()
        acl.mdl.add_dataset_buffer(
            self.output_dataset, self.device_output, self.output_buffer_size
        )

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize, mean-subtract, convert BGR to NCHW float32."""
        resized = frame.astype(np.float32)
        h, w = frame.shape[:2]

        # mean subtraction per channel
        resized = cv2.resize(resized, (self.input_size, self.input_size))
        b = resized[:, :, 0] - _MEAN[0]  # B
        g = resized[:, :, 1] - _MEAN[1]  # G
        r = resized[:, :, 2] - _MEAN[2]  # R

        # NCHW layout
        blob = np.stack([b, g, r], axis=0)  # (3, H, W)
        blob = np.expand_dims(blob, axis=0)  # (1, 3, H, W)
        return blob.astype(np.float32)

    def _postprocess(self, output: np.ndarray, frame_w: int, frame_h: int) -> list[dict]:
        """Parse detection output (1,1,N,7) → list of face dicts."""
        # output shape: (batch=1, num_detections, 7)
        # each detection: [image_id, label, score, x1, y1, x2, y2]
        if output.ndim == 4:
            output = output[0, 0]  # (N, 7)
        elif output.ndim == 3:
            output = output[0]

        faces = []
        for det in output:
            score = float(det[2])
            if score < self.confidence:
                continue
            x1 = int(det[3] * frame_w)
            y1 = int(det[4] * frame_h)
            x2 = int(det[5] * frame_w)
            y2 = int(det[6] * frame_h)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame_w, x2), min(frame_h, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            faces.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "confidence": round(score, 3),
            })
        return faces

    def detect(self, frame: np.ndarray) -> list[dict]:
        h, w = frame.shape[:2]

        blob = self._preprocess(frame)
        ret = acl.rt.memcpy(
            self.device_input, self.input_buffer_size,
            blob.tobytes(), blob.nbytes,
            3,  # ACL_MEMCPY_HOST_TO_DEVICE
        )
        if ret != 0:
            return []

        ret = acl.mdl.execute(
            self.model_id, self.input_dataset, self.output_dataset
        )
        if ret != 0:
            return []

        # copy output back
        host_output = np.zeros(self.output_buffer_size, dtype=np.byte)
        ret = acl.rt.memcpy(
            host_output.ctypes.data, self.output_buffer_size,
            self.device_output, self.output_buffer_size,
            2,  # ACL_MEMCPY_DEVICE_TO_HOST
        )
        if ret != 0:
            return []

        output = np.frombuffer(host_output, dtype=np.float32)
        output = output.reshape(1, 1, -1, 7)
        return self._postprocess(output, w, h)

    def get_largest_face(self, frame: np.ndarray):
        faces = self.detect(frame)
        if not faces:
            return None
        return max(faces, key=lambda f: (f["x2"] - f["x1"]) * (f["y2"] - f["y1"]))

    def __del__(self):
        try:
            acl.mdl.destroy_dataset(self.output_dataset)
            acl.mdl.destroy_dataset(self.input_dataset)
            acl.rt.free(self.device_output)
            acl.rt.free(self.device_input)
            acl.mdl.unload(self.model_id)
            acl.rt.destroy_context(self.context)
            acl.finalize()
        except Exception:
            pass


import cv2  # noqa: E402
