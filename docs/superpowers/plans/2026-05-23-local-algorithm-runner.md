# LocalAlgorithmRunner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal backend `LocalAlgorithmRunner` so local algorithms can be loaded as plugins using the same code/version/params protocol as box algorithms.

**Architecture:** Introduce a small local algorithm package format under `ruoyi-fastapi-backend/algorithm/local_algorithms/{code}/{version}/` with `manifest.json` and `algorithm.py`. Add a registry to discover plugin manifests and a runner to instantiate `Algorithm(params, model_dir)` and call `infer(frame)` for each local `CameraAlgorithmBinding`. Keep the existing `hik_vision.py` hard-coded analysis flow intact for now; this plan adds the reusable execution path and tests without rewriting the stream worker.

**Tech Stack:** Python 3.12, unittest, dataclasses, importlib, pathlib, NumPy frames, existing `algorithm.runtime_service.CameraAlgorithmBinding`.

---

## File Structure

Create backend runtime files:
- `ruoyi-fastapi-backend/algorithm/local_algorithm_base.py` — defines `LocalAlgorithmResult` and documents the plugin interface shape used by local algorithms.
- `ruoyi-fastapi-backend/algorithm/local_algorithm_registry.py` — scans local algorithm package folders, reads `manifest.json`, validates minimal fields, and imports the configured `Algorithm` class.
- `ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py` — owns loaded local algorithm instances per `(vid_id, code, version)`, syncs bindings, runs `infer(frame)`, normalizes results, and isolates plugin exceptions.

Create a tiny example local plugin for tests and future reference:
- `ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/manifest.json` — declares a no-model local algorithm.
- `ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/algorithm.py` — returns frame shape and received params.

Create tests:
- `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py` — verifies registry discovery, runner loading, version-aware keys, infer interval, result normalization, and plugin exception isolation.

Existing files intentionally not modified in this minimal closed loop:
- `ruoyi-fastapi-backend/hik_vision/hik_vision.py` — remains the current production local video analysis path.
- `ruoyi-fastapi-backend/hik_vision/local_video_analysis.py` — remains the capability switcher for existing local algorithms.
- `ruoyi-fastapi-backend/algorithm/runtime_service.py` — already produces `CameraAlgorithmBinding` with `runtime_type`, `algorithm_code`, and `params`.

---

### Task 1: Add Local Algorithm Registry

**Files:**
- Create: `ruoyi-fastapi-backend/algorithm/local_algorithm_base.py`
- Create: `ruoyi-fastapi-backend/algorithm/local_algorithm_registry.py`
- Create: `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py`

- [ ] **Step 1: Write the failing registry tests**

Create `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py` with:

```python
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from algorithm.local_algorithm_registry import LocalAlgorithmRegistry


class LocalAlgorithmRegistryTests(unittest.TestCase):
    def create_algorithm_package(self, root: Path, code: str = "demo", version: str = "v1") -> Path:
        package_dir = root / code / version
        package_dir.mkdir(parents=True)
        (package_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "code": code,
                    "name": "Demo Algorithm",
                    "version": version,
                    "runtime": "local",
                    "entry": "algorithm.py",
                    "class": "Algorithm",
                    "params_schema": {
                        "threshold": {"type": "number", "default": 0.5, "label": "阈值"}
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "algorithm.py").write_text(
            textwrap.dedent(
                """
                class Algorithm:
                    def __init__(self, params, model_dir):
                        self.params = params
                        self.model_dir = model_dir

                    def infer(self, frame):
                        return {"shape": list(frame.shape), "params": self.params, "model_dir": self.model_dir}
                """
            ),
            encoding="utf-8",
        )
        return package_dir

    def test_registry_discovers_manifest_by_code_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_dir = self.create_algorithm_package(root, code="demo", version="v1")

            registry = LocalAlgorithmRegistry(root)
            manifest = registry.get_manifest("demo", "v1")

            self.assertEqual("demo", manifest.code)
            self.assertEqual("Demo Algorithm", manifest.name)
            self.assertEqual("v1", manifest.version)
            self.assertEqual("local", manifest.runtime)
            self.assertEqual(package_dir, manifest.package_dir)
            self.assertEqual(package_dir / "algorithm.py", manifest.entry_path)
            self.assertEqual({"threshold": {"type": "number", "default": 0.5, "label": "阈值"}}, manifest.params_schema)

    def test_registry_loads_algorithm_class_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.create_algorithm_package(root, code="demo", version="v1")

            registry = LocalAlgorithmRegistry(root)
            algorithm_class = registry.load_algorithm_class("demo", "v1")
            instance = algorithm_class({"threshold": 0.7}, str(root / "demo" / "v1" / "weights"))

            self.assertEqual({"threshold": 0.7}, instance.params)

    def test_registry_ignores_non_local_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_dir = self.create_algorithm_package(root, code="box_only", version="v1")
            manifest_path = package_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["runtime"] = "external_box"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            registry = LocalAlgorithmRegistry(root)

            self.assertIsNone(registry.get_manifest("box_only", "v1"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the registry tests and verify they fail**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'algorithm.local_algorithm_registry'`.

- [ ] **Step 3: Add the local algorithm base dataclass**

Create `ruoyi-fastapi-backend/algorithm/local_algorithm_base.py` with:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LocalAlgorithmResult:
    vid_id: int
    code: str
    version: str
    extra: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Add the registry implementation**

Create `ruoyi-fastapi-backend/algorithm/local_algorithm_registry.py` with:

```python
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalAlgorithmManifest:
    code: str
    name: str
    version: str
    runtime: str
    package_dir: Path
    entry: str = "algorithm.py"
    class_name: str = "Algorithm"
    params_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def entry_path(self) -> Path:
        return self.package_dir / self.entry

    @property
    def model_dir(self) -> Path:
        return self.package_dir / "weights"


class LocalAlgorithmRegistry:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)

    def get_manifest(self, code: str, version: str) -> LocalAlgorithmManifest | None:
        manifest_path = self.root_dir / code / version / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if raw.get("runtime") != "local":
            return None
        if raw.get("code") != code or raw.get("version") != version:
            return None
        entry = raw.get("entry") or "algorithm.py"
        class_name = raw.get("class") or "Algorithm"
        return LocalAlgorithmManifest(
            code=code,
            name=raw.get("name") or code,
            version=version,
            runtime="local",
            package_dir=manifest_path.parent,
            entry=entry,
            class_name=class_name,
            params_schema=raw.get("params_schema") or {},
        )

    def load_algorithm_class(self, code: str, version: str):
        manifest = self.get_manifest(code, version)
        if manifest is None or not manifest.entry_path.exists():
            return None
        module_name = f"local_algorithms.{code}.{version}.algorithm"
        spec = importlib.util.spec_from_file_location(module_name, manifest.entry_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return getattr(module, manifest.class_name, None)
```

- [ ] **Step 5: Run the registry tests and verify they pass**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: PASS, 3 tests run.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add ruoyi-fastapi-backend/algorithm/local_algorithm_base.py ruoyi-fastapi-backend/algorithm/local_algorithm_registry.py ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py
git commit -m "feat: add local algorithm registry"
```

Expected: a new commit is created. If hooks fail, fix the reported issue and create a new commit; do not use `--no-verify`.

---

### Task 2: Add LocalAlgorithmRunner

**Files:**
- Create: `ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py`
- Modify: `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py`

- [ ] **Step 1: Add failing runner tests**

Append this import near the top of `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py`:

```python
import time

import numpy as np

from algorithm.runtime_service import CameraAlgorithmBinding
from algorithm.local_algorithm_runner import LocalAlgorithmRunner
```

Append this test class before the `if __name__ == "__main__":` block:

```python
class LocalAlgorithmRunnerTests(unittest.TestCase):
    def create_algorithm_package(self, root: Path, code: str = "demo", version: str = "v1", body: str | None = None) -> Path:
        package_dir = root / code / version
        package_dir.mkdir(parents=True)
        (package_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "code": code,
                    "name": "Demo Algorithm",
                    "version": version,
                    "runtime": "local",
                    "entry": "algorithm.py",
                    "class": "Algorithm",
                }
            ),
            encoding="utf-8",
        )
        algorithm_body = body or """
class Algorithm:
    def __init__(self, params, model_dir):
        self.params = params
        self.model_dir = model_dir

    def infer(self, frame):
        return {"shape": list(frame.shape), "params": self.params, "model_dir": self.model_dir}
"""
        (package_dir / "algorithm.py").write_text(textwrap.dedent(algorithm_body), encoding="utf-8")
        return package_dir

    def test_runner_loads_local_binding_and_runs_infer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_dir = self.create_algorithm_package(root, code="demo", version="v1")
            runner = LocalAlgorithmRunner(LocalAlgorithmRegistry(root))
            binding = CameraAlgorithmBinding(
                vid_id=7,
                algorithm_code="demo",
                algorithm_name="Demo Algorithm",
                runtime_type="local",
                params={"alg_version": "v1", "default_conf": {"threshold": 0.8}},
            )

            runner.set_algorithms(7, [binding])
            results = runner.process_frame(7, np.zeros((2, 3, 3), dtype=np.uint8))

            self.assertEqual(1, len(results))
            self.assertEqual(7, results[0].vid_id)
            self.assertEqual("demo", results[0].code)
            self.assertEqual("v1", results[0].version)
            self.assertEqual([2, 3, 3], results[0].extra["shape"])
            self.assertEqual({"threshold": 0.8}, results[0].extra["params"])
            self.assertEqual(str(package_dir / "weights"), results[0].extra["model_dir"])

    def test_runner_uses_default_v1_when_binding_has_no_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.create_algorithm_package(root, code="demo", version="v1")
            runner = LocalAlgorithmRunner(LocalAlgorithmRegistry(root))
            binding = CameraAlgorithmBinding(
                vid_id=7,
                algorithm_code="demo",
                algorithm_name="Demo Algorithm",
                runtime_type="local",
                params={},
            )

            runner.set_algorithms(7, [binding])
            results = runner.process_frame(7, np.zeros((1, 1, 3), dtype=np.uint8))

            self.assertEqual("v1", results[0].version)

    def test_runner_respects_infer_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.create_algorithm_package(root, code="demo", version="v1")
            runner = LocalAlgorithmRunner(LocalAlgorithmRegistry(root))
            binding = CameraAlgorithmBinding(
                vid_id=7,
                algorithm_code="demo",
                algorithm_name="Demo Algorithm",
                runtime_type="local",
                params={"alg_version": "v1", "default_conf": {"infer_interval": 60}},
            )

            runner.set_algorithms(7, [binding])
            first = runner.process_frame(7, np.zeros((1, 1, 3), dtype=np.uint8))
            second = runner.process_frame(7, np.zeros((1, 1, 3), dtype=np.uint8))

            self.assertEqual(1, len(first))
            self.assertEqual([], second)

    def test_runner_isolates_plugin_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.create_algorithm_package(
                root,
                code="broken",
                version="v1",
                body="""
class Algorithm:
    def __init__(self, params, model_dir):
        pass

    def infer(self, frame):
        raise RuntimeError("boom")
""",
            )
            runner = LocalAlgorithmRunner(LocalAlgorithmRegistry(root))
            binding = CameraAlgorithmBinding(
                vid_id=7,
                algorithm_code="broken",
                algorithm_name="Broken Algorithm",
                runtime_type="local",
                params={"alg_version": "v1"},
            )

            runner.set_algorithms(7, [binding])
            results = runner.process_frame(7, np.zeros((1, 1, 3), dtype=np.uint8))

            self.assertEqual([], results)
```

- [ ] **Step 2: Run the runner tests and verify they fail**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'algorithm.local_algorithm_runner'`.

- [ ] **Step 3: Add the runner implementation**

Create `ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py` with:

```python
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from algorithm.local_algorithm_base import LocalAlgorithmResult
from algorithm.local_algorithm_registry import LocalAlgorithmRegistry
from algorithm.runtime_service import CameraAlgorithmBinding


@dataclass
class _LoadedLocalAlgorithm:
    vid_id: int
    code: str
    version: str
    instance: Any
    infer_interval: float
    last_infer_time: float = 0.0


class LocalAlgorithmRunner:
    def __init__(self, registry: LocalAlgorithmRegistry):
        self.registry = registry
        self._loaded: dict[tuple[int, str, str], _LoadedLocalAlgorithm] = {}

    def set_algorithms(self, vid_id: int, bindings: list[CameraAlgorithmBinding]) -> None:
        local_bindings = [binding for binding in bindings if binding.runtime_type == "local"]
        wanted_keys = {(vid_id, binding.algorithm_code, self._binding_version(binding)) for binding in local_bindings}
        current_keys = {key for key in self._loaded if key[0] == vid_id}

        for key in current_keys - wanted_keys:
            loaded = self._loaded.pop(key)
            close = getattr(loaded.instance, "close", None)
            if callable(close):
                close()

        for binding in local_bindings:
            version = self._binding_version(binding)
            key = (vid_id, binding.algorithm_code, version)
            if key in self._loaded:
                continue
            manifest = self.registry.get_manifest(binding.algorithm_code, version)
            if manifest is None:
                continue
            algorithm_class = self.registry.load_algorithm_class(binding.algorithm_code, version)
            if algorithm_class is None:
                continue
            params = self._binding_params(binding)
            try:
                instance = algorithm_class(params, str(manifest.model_dir))
            except Exception:
                continue
            self._loaded[key] = _LoadedLocalAlgorithm(
                vid_id=vid_id,
                code=binding.algorithm_code,
                version=version,
                instance=instance,
                infer_interval=float(params.get("infer_interval", 1.0)),
            )

    def process_frame(self, vid_id: int, frame: np.ndarray) -> list[LocalAlgorithmResult]:
        results: list[LocalAlgorithmResult] = []
        wrappers = [loaded for key, loaded in self._loaded.items() if key[0] == vid_id]
        for wrapper in wrappers:
            now = time.time()
            if now - wrapper.last_infer_time < wrapper.infer_interval:
                continue
            wrapper.last_infer_time = now
            try:
                output = wrapper.instance.infer(frame)
            except Exception:
                continue
            if output is None:
                continue
            extra = output if isinstance(output, dict) else {"value": output}
            results.append(
                LocalAlgorithmResult(
                    vid_id=vid_id,
                    code=wrapper.code,
                    version=wrapper.version,
                    extra=extra,
                )
            )
        return results

    def remove_camera(self, vid_id: int) -> None:
        keys = [key for key in self._loaded if key[0] == vid_id]
        for key in keys:
            loaded = self._loaded.pop(key)
            close = getattr(loaded.instance, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _binding_version(binding: CameraAlgorithmBinding) -> str:
        version = binding.params.get("alg_version") or binding.params.get("version")
        return str(version or "v1")

    @staticmethod
    def _binding_params(binding: CameraAlgorithmBinding) -> dict[str, Any]:
        default_conf = binding.params.get("default_conf")
        if isinstance(default_conf, dict):
            return dict(default_conf)
        return dict(binding.params)
```

- [ ] **Step 4: Run the runner tests and verify they pass**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: PASS, 7 tests run.

- [ ] **Step 5: Run existing runtime tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_multi_camera_analysis.py
```

Expected: PASS. This confirms the new runner did not change existing runtime parsing or `hik_vision.py` behavior.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py
git commit -m "feat: add local algorithm runner"
```

Expected: a new commit is created. If hooks fail, fix the reported issue and create a new commit; do not use `--no-verify`.

---

### Task 3: Add Example Local Algorithm Package

**Files:**
- Create: `ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/manifest.json`
- Create: `ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/algorithm.py`
- Modify: `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py`

- [ ] **Step 1: Add failing test for default registry root**

Append this import to `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py`:

```python
from algorithm.local_algorithm_runner import default_local_algorithm_runner
```

Append this test method inside `LocalAlgorithmRunnerTests`:

```python
    def test_default_runner_loads_echo_frame_example_package(self):
        binding = CameraAlgorithmBinding(
            vid_id=99,
            algorithm_code="echo_frame",
            algorithm_name="Echo Frame",
            runtime_type="local",
            params={"alg_version": "v1", "default_conf": {"infer_interval": 0, "label": "demo"}},
        )

        default_local_algorithm_runner.remove_camera(99)
        default_local_algorithm_runner.set_algorithms(99, [binding])
        try:
            results = default_local_algorithm_runner.process_frame(99, np.zeros((4, 5, 3), dtype=np.uint8))
        finally:
            default_local_algorithm_runner.remove_camera(99)

        self.assertEqual(1, len(results))
        self.assertEqual("echo_frame", results[0].code)
        self.assertEqual("v1", results[0].version)
        self.assertEqual([4, 5, 3], results[0].extra["shape"])
        self.assertEqual("demo", results[0].extra["params"]["label"])
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: FAIL because `default_local_algorithm_runner` is not defined and the `echo_frame` package does not exist.

- [ ] **Step 3: Add the example manifest**

Create `ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/manifest.json` with:

```json
{
  "code": "echo_frame",
  "name": "Echo Frame",
  "version": "v1",
  "runtime": "local",
  "entry": "algorithm.py",
  "class": "Algorithm",
  "params_schema": {
    "infer_interval": {
      "type": "number",
      "default": 1.0,
      "label": "推理间隔秒"
    },
    "label": {
      "type": "string",
      "default": "demo",
      "label": "测试标签"
    }
  }
}
```

- [ ] **Step 4: Add the example plugin**

Create `ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/algorithm.py` with:

```python
class Algorithm:
    def __init__(self, params: dict, model_dir: str):
        self.params = params
        self.model_dir = model_dir

    def infer(self, frame):
        return {
            "shape": list(frame.shape),
            "params": self.params,
            "model_dir": self.model_dir,
        }
```

- [ ] **Step 5: Add the default runner singleton**

Append this to the end of `ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py`:

```python
DEFAULT_LOCAL_ALGORITHM_ROOT = __import__("pathlib").Path(__file__).resolve().parent / "local_algorithms"
default_local_algorithm_runner = LocalAlgorithmRunner(LocalAlgorithmRegistry(DEFAULT_LOCAL_ALGORITHM_ROOT))
```

- [ ] **Step 6: Run all local runner tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: PASS, 8 tests run.

- [ ] **Step 7: Run compile check on new files**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python -m compileall algorithm/local_algorithm_base.py algorithm/local_algorithm_registry.py algorithm/local_algorithm_runner.py algorithm/local_algorithms/echo_frame/v1/algorithm.py
```

Expected: command exits 0.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/manifest.json ruoyi-fastapi-backend/algorithm/local_algorithms/echo_frame/v1/algorithm.py ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py
git commit -m "feat: add example local algorithm plugin"
```

Expected: a new commit is created. If hooks fail, fix the reported issue and create a new commit; do not use `--no-verify`.

---

### Task 4: Add Runtime Adapter Helper for Local Bindings

**Files:**
- Modify: `ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py`
- Modify: `ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py`

- [ ] **Step 1: Add failing adapter test**

Append this test method inside `LocalAlgorithmRunnerTests`:

```python
    def test_runner_syncs_only_local_bindings_from_runtime_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.create_algorithm_package(root, code="local_demo", version="v2")
            runner = LocalAlgorithmRunner(LocalAlgorithmRegistry(root))
            local_binding = CameraAlgorithmBinding(
                vid_id=5,
                algorithm_code="local_demo",
                algorithm_name="Local Demo",
                runtime_type="local",
                params={"alg_version": "v2", "default_conf": {"infer_interval": 0}},
            )
            box_binding = CameraAlgorithmBinding(
                vid_id=5,
                algorithm_code="box_demo",
                algorithm_name="Box Demo",
                runtime_type="external_box",
                params={"alg_version": "v1"},
            )

            runner.sync_camera_bindings(5, [local_binding, box_binding])
            results = runner.process_frame(5, np.zeros((1, 2, 3), dtype=np.uint8))

            self.assertEqual(1, len(results))
            self.assertEqual("local_demo", results[0].code)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: FAIL with `AttributeError: 'LocalAlgorithmRunner' object has no attribute 'sync_camera_bindings'`.

- [ ] **Step 3: Add adapter method**

Add this method to `LocalAlgorithmRunner` in `ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py`, directly above `set_algorithms`:

```python
    def sync_camera_bindings(self, vid_id: int, bindings: list[CameraAlgorithmBinding]) -> None:
        self.set_algorithms(vid_id, [binding for binding in bindings if binding.runtime_type == "local"])
```

- [ ] **Step 4: Run local runner tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: PASS, 9 tests run.

- [ ] **Step 5: Run runtime tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_multi_camera_analysis.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add ruoyi-fastapi-backend/algorithm/local_algorithm_runner.py ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py
git commit -m "feat: add local binding sync helper"
```

Expected: a new commit is created. If hooks fail, fix the reported issue and create a new commit; do not use `--no-verify`.

---

### Task 5: Final Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run LocalAlgorithmRunner tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_local_algorithm_runner.py
```

Expected: PASS, 9 tests run.

- [ ] **Step 2: Run existing multi-camera/runtime tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_multi_camera_analysis.py
```

Expected: PASS.

- [ ] **Step 3: Run algorithm management helper tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: PASS.

- [ ] **Step 4: Run compile check for algorithm package**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python -m compileall algorithm
```

Expected: command exits 0.

- [ ] **Step 5: Review current diff**

Run:

```bash
git status --short
git diff -- ruoyi-fastapi-backend/algorithm ruoyi-fastapi-backend/tests/test_local_algorithm_runner.py
```

Expected: only intentional new local algorithm runner, registry, example plugin, and tests are present.

---

## Self-Review

- Spec coverage: This plan creates a backend `LocalAlgorithmRunner`, plugin registry, common code/version/params protocol, an example local plugin, and tests. It intentionally does not rewrite `hik_vision.py`; that integration should be a later plan after the runner is verified.
- Placeholder scan: No `TBD`, `TODO`, or vague implementation-only steps remain.
- Type consistency: Tests and implementation consistently use `CameraAlgorithmBinding`, `LocalAlgorithmRegistry`, `LocalAlgorithmRunner`, `LocalAlgorithmResult`, `alg_version`, `default_conf`, and `infer_interval`.
