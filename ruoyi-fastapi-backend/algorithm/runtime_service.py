import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


@dataclass(frozen=True)
class CameraAlgorithmBinding:
    vid_id: int
    algorithm_code: str
    algorithm_name: str
    runtime_type: str
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "enabled"
    priority: int = 100


@dataclass
class AlgorithmRun:
    run_id: str
    vid_id: int
    algorithm_code: str
    algorithm_name: str
    runtime_type: str
    status: str
    start_time: datetime
    stop_time: Optional[datetime] = None
    external_task_id: Optional[str] = None
    error_message: Optional[str] = None


class AlgorithmRunRegistry:
    def __init__(self):
        self._runs: dict[tuple[int, str], AlgorithmRun] = {}

    def start_run(
        self,
        binding: CameraAlgorithmBinding,
        external_task_id: str | None = None,
        status: str = "running",
        error_message: str | None = None,
    ) -> AlgorithmRun:
        run = AlgorithmRun(
            run_id=str(uuid4()),
            vid_id=binding.vid_id,
            algorithm_code=binding.algorithm_code,
            algorithm_name=binding.algorithm_name,
            runtime_type=binding.runtime_type,
            status=status,
            start_time=datetime.now(),
            external_task_id=external_task_id,
            error_message=error_message,
        )
        self._runs[(binding.vid_id, binding.algorithm_code)] = run
        return run

    def mark_camera_runs_status(self, vid_id: int, status: str, runtime_type: str | None = None) -> list[AlgorithmRun]:
        updated_runs = []
        for run in self.list_camera_runs(vid_id):
            if runtime_type is None or run.runtime_type == runtime_type:
                run.status = status
                if status in {"stopped", "failed"}:
                    run.stop_time = datetime.now()
                updated_runs.append(run)
        return updated_runs

    def get_run(self, vid_id: int, algorithm_code: str) -> AlgorithmRun | None:
        return self._runs.get((vid_id, algorithm_code))

    def stop_run(self, vid_id: int, algorithm_code: str) -> AlgorithmRun | None:
        run = self.get_run(vid_id, algorithm_code)
        if run:
            run.status = "stopped"
            run.stop_time = datetime.now()
        return run

    def stop_camera_runs(self, vid_id: int) -> list[AlgorithmRun]:
        stopped_runs = []
        for run_vid_id, algorithm_code in list(self._runs):
            if run_vid_id == vid_id:
                run = self.stop_run(run_vid_id, algorithm_code)
                if run:
                    stopped_runs.append(run)
        return stopped_runs

    def list_camera_runs(self, vid_id: int) -> list[AlgorithmRun]:
        return [run for (run_vid_id, _), run in self._runs.items() if run_vid_id == vid_id]


class AlgorithmRuntimeService:
    LOCAL_REALTIME_ALGORITHM_CODE = "realtime_face_analysis"
    LOCAL_REALTIME_ALGORITHM_NAME = "实时人脸幸福指数分析"
    LOCAL_ALGORITHM_CODES = set()

    @classmethod
    def create_local_binding(
        cls,
        vid_id: int,
        algorithm_code: str | None = None,
        algorithm_name: str | None = None,
    ) -> CameraAlgorithmBinding:
        return CameraAlgorithmBinding(
            vid_id=vid_id,
            algorithm_code=algorithm_code or cls.LOCAL_REALTIME_ALGORITHM_CODE,
            algorithm_name=algorithm_name or cls.LOCAL_REALTIME_ALGORITHM_NAME,
            runtime_type="local",
            params={},
            priority=0,
        )

    @classmethod
    def create_external_box_binding(
        cls,
        vid_id: int,
        algorithm_code: str,
        algorithm_name: str | None,
        params: dict[str, Any] | None,
        priority: int = 100,
    ) -> CameraAlgorithmBinding:
        return CameraAlgorithmBinding(
            vid_id=vid_id,
            algorithm_code=str(algorithm_code),
            algorithm_name=algorithm_name or str(algorithm_code),
            runtime_type="external_box",
            params=params or {},
            priority=priority,
        )

    @classmethod
    def resolve_camera_algorithms(cls, video_detail: dict[str, Any]) -> list[CameraAlgorithmBinding]:
        vid_id = video_detail.get("vid_id") or video_detail.get("vidId")
        if vid_id is None:
            return []

        configured_value = video_detail.get("vid_algorithm", video_detail.get("vidAlgorithm"))
        legacy_algorithms = cls._parse_legacy_algorithms(configured_value)
        if not legacy_algorithms:
            return [] if cls._is_explicit_empty_algorithm_config(configured_value) else [cls.create_local_binding(vid_id=int(vid_id))]

        bindings = []
        for index, legacy_algorithm in enumerate(legacy_algorithms):
            if not isinstance(legacy_algorithm, dict):
                continue
            alg_id = cls._first_non_empty(legacy_algorithm, "algId", "alg_id")
            alg_version = cls._first_non_empty(legacy_algorithm, "algVersion", "alg_version")
            weight_path = cls._first_non_empty(legacy_algorithm, "algWeightPath", "alg_weight_path")

            algorithm_code = cls._first_non_empty(legacy_algorithm, "algSerial", "alg_serial")
            algorithm_code = algorithm_code or cls._first_non_empty(legacy_algorithm, "algorithm_code", "algCode")
            algorithm_code = algorithm_code or alg_id
            if not algorithm_code:
                continue
            runtime_type = cls._first_non_empty(legacy_algorithm, "runtimeType", "runtime_type", "algRuntimeType", "alg_runtime_type")
            if runtime_type == "local":
                bindings.append(cls.create_local_binding(vid_id=int(vid_id), algorithm_code=str(algorithm_code), algorithm_name=legacy_algorithm.get("algorithm_name") or legacy_algorithm.get("algName")))
                continue
            if runtime_type is None and str(algorithm_code) in cls.LOCAL_ALGORITHM_CODES:
                bindings.append(cls.create_local_binding(vid_id=int(vid_id), algorithm_code=str(algorithm_code), algorithm_name=legacy_algorithm.get("algorithm_name") or legacy_algorithm.get("algName")))
                continue

            default_conf = cls._parse_default_conf(legacy_algorithm)
            has_versioned_metadata = any(
                cls._first_non_empty(legacy_algorithm, *keys) is not None
                for keys in (
                    ("algSerial", "alg_serial"),
                    ("algVersion", "alg_version"),
                    ("algWeightPath", "alg_weight_path"),
                    ("alg_id",),
                    ("default_conf", "alg_default_conf"),
                )
            )
            params = (
                {
                    "alg_id": alg_id,
                    "alg_version": alg_version,
                    "weight_path": weight_path,
                    "default_conf": default_conf,
                }
                if has_versioned_metadata
                else default_conf
            )
            bindings.append(
                cls.create_external_box_binding(
                    vid_id=int(vid_id),
                    algorithm_code=str(algorithm_code),
                    algorithm_name=legacy_algorithm.get("algorithm_name") or legacy_algorithm.get("algName"),
                    params=params,
                    priority=100 + index,
                )
            )
        return sorted(bindings, key=lambda binding: binding.priority)

    @staticmethod
    def _first_non_empty(source: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = source.get(key)
            if value is not None and value != "":
                return value
        return None

    @staticmethod
    def _is_explicit_empty_algorithm_config(value: Any) -> bool:
        if value == []:
            return True
        if isinstance(value, str):
            try:
                return json.loads(value) == []
            except json.JSONDecodeError:
                return False
        return False

    @classmethod
    def _parse_default_conf(cls, source: dict[str, Any]) -> dict[str, Any]:
        for key in ("params", "algDefaultConf", "alg_default_conf", "default_conf"):
            value = source.get(key)
            if value is not None and value != "":
                return cls._parse_params(value)
        return {}

    @staticmethod
    def _parse_legacy_algorithms(value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        return []

    @staticmethod
    def _parse_params(value: Any) -> dict[str, Any]:
        if value is None or value == "":
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}


algorithm_run_registry = AlgorithmRunRegistry()
