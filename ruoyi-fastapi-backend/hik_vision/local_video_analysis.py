from dataclasses import dataclass

from algorithm.runtime_service import AlgorithmRuntimeService


@dataclass(frozen=True)
class LocalVideoAnalysisCapabilities:
    enable_local_worker: bool
    enable_face_detection: bool
    enable_face_recognition: bool
    enable_happiness_analysis: bool

    @classmethod
    def from_video_detail(cls, video_detail: dict) -> "LocalVideoAnalysisCapabilities":
        bindings = [
            binding
            for binding in AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)
            if binding.runtime_type == "local"
        ]
        local_codes = {binding.algorithm_code for binding in bindings}
        enable_face_detection = bool(
            local_codes
            & {
                "face_detection",
                "person_recognition",
                "face_recognition",
                "arcface_recognition",
                AlgorithmRuntimeService.LOCAL_REALTIME_ALGORITHM_CODE,
            }
        )
        enable_face_recognition = bool(
            local_codes
            & {
                "face_recognition",
                "arcface_recognition",
            }
        )
        enable_happiness_analysis = AlgorithmRuntimeService.LOCAL_REALTIME_ALGORITHM_CODE in local_codes
        return cls(
            enable_local_worker=bool(bindings),
            enable_face_detection=enable_face_detection,
            enable_face_recognition=enable_face_recognition,
            enable_happiness_analysis=enable_happiness_analysis,
        )

    @classmethod
    def default_enabled(cls) -> "LocalVideoAnalysisCapabilities":
        return cls(
            enable_local_worker=True,
            enable_face_detection=True,
            enable_face_recognition=True,
            enable_happiness_analysis=True,
        )
