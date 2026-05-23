"""
Data models used internally by the box service.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CameraStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class CommandAction(str, Enum):
    START = "start"
    STOP = "stop"
    UPDATE = "update"


@dataclass
class AlgorithmConfig:
    """A single algorithm binding – maps to one CameraAlgorithmBinding on the backend."""
    code: str                                     # alg_serial
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class CameraTask:
    """Describes a camera that should run inference, received from backend."""
    vid_id: int
    vid_serial: str
    action: CommandAction
    stream_url: str
    stream_type: str = "rtsp"                     # rtsp / rtmp / file
    algorithms: list[AlgorithmConfig] = field(default_factory=list)
    publish_path: str = ""                        # for SRS push, e.g. publish_4


@dataclass
class CameraState:
    """Runtime state of a single camera on this box."""
    vid_id: int
    vid_serial: str
    stream_url: str
    stream_type: str
    publish_path: str
    algorithms: list[AlgorithmConfig] = field(default_factory=list)
    status: CameraStatus = CameraStatus.STOPPED
    started_at: float | None = None
    error_message: str = ""


@dataclass
class InferenceResult:
    """A single inference result produced by an algorithm on a frame."""
    vid_id: int
    code: str                                    # algorithm serial
    image_base64: str | None = None
    time: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceStatusMessage:
    """Message sent to backend reporting which cameras are running."""
    serial: str
    type: str = "devices"
    time: float = field(default_factory=lambda: datetime.now().timestamp())
    devices: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AlarmMessage:
    """Message sent to backend with inference results for a camera."""
    key: str                                     # e.g. publish_4
    serial: str
    type: str = "alarm"
    data: list[dict[str, Any]] = field(default_factory=list)
