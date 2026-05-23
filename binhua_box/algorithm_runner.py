"""
Algorithm execution engine – loads algorithm plugins, runs inference on camera
frames, and reports results.

Algorithm plugins live in box/algorithms/ as <alg_code>.py files.
Each plugin must expose:

    class Algorithm:
        def __init__(self, params: dict) -> None: ...
        def infer(self, frame: np.ndarray) -> dict | None: ...
"""
import base64
import importlib
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from config import ALGORITHM_DIR
from models import AlgorithmConfig, InferenceResult

ResultCallback = Callable[[InferenceResult], None]

# global registry of loaded algorithm instances, keyed by (vid_id, alg_code)
_loaded: dict[tuple[int, str], "AlgorithmWrapper"] = {}
_lock = threading.Lock()


class AlgorithmWrapper:
    """Holds a loaded algorithm instance and its config."""

    def __init__(self, vid_id: int, config: AlgorithmConfig, instance):
        self.vid_id = vid_id
        self.code = config.code
        self.config = config
        self.instance = instance
        self.last_infer_time = 0.0
        self.infer_interval = float(config.params.get("infer_interval", 1.0))


def _load_algorithm_class(code: str):
    """Import and return the Algorithm class from a plugin file."""
    plugin_path = ALGORITHM_DIR / f"{code}.py"
    if not plugin_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"alg_{code}", plugin_path)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"algorithms.{code}"] = module
    spec.loader.exec_module(module)
    return getattr(module, "Algorithm", None)


class AlgorithmRunner:
    """Receives frames, runs algorithms, emits results."""

    def __init__(self):
        self._result_callbacks: list[ResultCallback] = []
        self._running = False

    def on_result(self, callback: ResultCallback) -> None:
        self._result_callbacks.append(callback)

    def set_algorithms(self, vid_id: int, algorithms: list[AlgorithmConfig]) -> None:
        """Sync the algorithm list for a camera – add new, remove stale."""
        with _lock:
            current_keys = {k for k in _loaded if k[0] == vid_id}
            wanted_keys = {(vid_id, a.code) for a in algorithms}

            # remove stale
            for key in current_keys - wanted_keys:
                del _loaded[key]

            # add new
            for alg in algorithms:
                key = (vid_id, alg.code)
                if key not in _loaded:
                    cls = _load_algorithm_class(alg.code)
                    if cls is None:
                        continue
                    try:
                        instance = cls(alg.params)
                        wrapper = AlgorithmWrapper(vid_id, alg, instance)
                        _loaded[key] = wrapper
                    except Exception:
                        pass

    def process_frame(self, vid_id: int, frame: np.ndarray) -> list[InferenceResult]:
        """Run all algorithms bound to vid_id on a single frame."""
        results: list[InferenceResult] = []
        with _lock:
            wrappers = [w for k, w in _loaded.items() if k[0] == vid_id]

        for wrapper in wrappers:
            now = time.time()
            if now - wrapper.last_infer_time < wrapper.infer_interval:
                continue
            wrapper.last_infer_time = now
            try:
                output = wrapper.instance.infer(frame)
                if output is None:
                    continue
                image_b64 = None
                if isinstance(output, dict) and "image" in output:
                    img = output.pop("image")
                    if isinstance(img, np.ndarray):
                        _, buf = cv2.imencode(".jpg", img)
                        image_b64 = base64.b64encode(buf).decode()
                result = InferenceResult(
                    vid_id=vid_id,
                    code=wrapper.code,
                    image_base64=image_b64,
                    extra=output if isinstance(output, dict) else {"value": str(output)},
                )
                results.append(result)
                for cb in self._result_callbacks:
                    cb(result)
            except Exception:
                pass
        return results

    def remove_camera(self, vid_id: int) -> None:
        with _lock:
            keys = [k for k in _loaded if k[0] == vid_id]
            for k in keys:
                del _loaded[k]
