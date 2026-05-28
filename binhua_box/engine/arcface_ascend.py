"""
ArcFace feature extractor for Huawei Ascend NPU.
Model: ONNX ArcFace converted via ATC:
  atc --model=w600k_r50.onnx --framework=5 --output=arcface \
      --soc_version=Ascend310B4 --input_shape="input:1,3,112,112"
"""
import os
import threading
from pathlib import Path

import acl
import cv2
import numpy as np

_WEIGHTS_DIR = Path(__file__).resolve().parents[1] / "weights"
_MODEL_PATH = str(_WEIGHTS_DIR / "arcface.om")

ACL_MEM_MALLOC_HUGE_FIRST = 0
ACL_MEMCPY_HOST_TO_DEVICE = 1
ACL_MEMCPY_DEVICE_TO_HOST = 2

_acl_lock = threading.Lock()
_acl_initialized = False


def _init_acl():
    """Initialize ACL once per process (singleton)."""
    global _acl_initialized
    with _acl_lock:
        if _acl_initialized:
            return
        ret = acl.init()
        if ret != 0 and ret != 100002:  # 100002 = already initialized
            raise RuntimeError(f"acl.init failed: {ret}")
        _acl_initialized = True


class ArcFaceExtractorAscend:
    def __init__(self):
        _init_acl()

        self.device_id = int(os.environ.get("ASCEND_DEVICE_ID", "0"))

        ret = acl.rt.set_device(self.device_id)
        if ret != 0:
            raise RuntimeError(f"acl.rt.set_device failed: {ret}")

        self.context, ret = acl.rt.create_context(self.device_id)
        if ret != 0:
            raise RuntimeError(f"acl.rt.create_context failed: {ret}")

        self.model_id, ret = acl.mdl.load_from_file(_MODEL_PATH)
        if ret != 0:
            raise RuntimeError(f"acl.mdl.load_from_file failed: {ret}")

        self.model_desc = acl.mdl.create_desc()
        ret = acl.mdl.get_desc(self.model_desc, self.model_id)
        if ret != 0:
            raise RuntimeError(f"acl.mdl.get_desc failed: {ret}")

        self.input_size = 112
        self.input_buffer_size = 3 * self.input_size * self.input_size * 4

        self.device_input, ret = acl.rt.malloc(self.input_buffer_size, ACL_MEM_MALLOC_HUGE_FIRST)
        if ret != 0:
            raise RuntimeError(f"acl.rt.malloc input failed: {ret}")

        self.output_buffer_size = 512 * 4
        self.device_output, ret = acl.rt.malloc(self.output_buffer_size, ACL_MEM_MALLOC_HUGE_FIRST)
        if ret != 0:
            raise RuntimeError(f"acl.rt.malloc output failed: {ret}")

        self.input_dataset = acl.mdl.create_dataset()
        input_data_buffer = acl.create_data_buffer(self.device_input, self.input_buffer_size)
        acl.mdl.add_dataset_buffer(self.input_dataset, input_data_buffer)

        self.output_dataset = acl.mdl.create_dataset()
        output_data_buffer = acl.create_data_buffer(self.device_output, self.output_buffer_size)
        acl.mdl.add_dataset_buffer(self.output_dataset, output_data_buffer)

    def extract(self, face_crop: np.ndarray) -> np.ndarray:
        img = cv2.resize(face_crop, (self.input_size, self.input_size))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 127.5 - 1.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)
        blob = img.astype(np.float32)

        ret = acl.rt.memcpy(
            self.device_input, self.input_buffer_size,
            blob.ctypes.data, blob.nbytes,
            ACL_MEMCPY_HOST_TO_DEVICE,
        )
        if ret != 0:
            return np.zeros(512, dtype=np.float32)

        ret = acl.mdl.execute(
            self.model_id, self.input_dataset, self.output_dataset
        )
        if ret != 0:
            return np.zeros(512, dtype=np.float32)

        host_output = np.zeros(self.output_buffer_size, dtype=np.byte)
        ret = acl.rt.memcpy(
            host_output.ctypes.data, self.output_buffer_size,
            self.device_output, self.output_buffer_size,
            ACL_MEMCPY_DEVICE_TO_HOST,
        )
        if ret != 0:
            return np.zeros(512, dtype=np.float32)

        vec = np.frombuffer(host_output, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def __del__(self):
        try:
            acl.mdl.destroy_dataset(self.output_dataset)
            acl.mdl.destroy_dataset(self.input_dataset)
            acl.rt.free(self.device_output)
            acl.rt.free(self.device_input)
            acl.mdl.unload(self.model_id)
            acl.rt.destroy_context(self.context)
        except Exception:
            pass
