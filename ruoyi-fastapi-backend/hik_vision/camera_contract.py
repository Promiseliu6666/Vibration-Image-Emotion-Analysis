"""Canonical camera identifiers shared by video and analysis endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass

_DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,64}$")
_SOURCES = {"local", "rtsp", "xiaozhi"}


@dataclass(frozen=True, slots=True)
class CameraSelection:
    camera_id: str
    source: str
    device_id: str = ""

    def legacy_params(self) -> dict[str, str]:
        params = {"source": self.source}
        if self.source == "xiaozhi" and self.device_id:
            params["device_id"] = self.device_id
        return params


def to_camera_id(source: str, device_id: str = "") -> str:
    if source not in _SOURCES:
        raise ValueError("视频来源必须是 local、rtsp 或 xiaozhi")
    if source != "xiaozhi":
        return source
    if not device_id:
        return "xiaozhi"
    if not _DEVICE_ID_PATTERN.fullmatch(device_id):
        raise ValueError("小智设备编号格式不正确")
    return f"xiaozhi:{device_id}"


def parse_camera_id(camera_id: str) -> CameraSelection:
    value = str(camera_id or "").strip()
    if value in {"local", "local:0"}:
        return CameraSelection("local", "local")
    if value in {"rtsp", "rtsp:default"}:
        return CameraSelection("rtsp", "rtsp")
    if value == "xiaozhi":
        return CameraSelection("xiaozhi", "xiaozhi")
    if value.startswith("xiaozhi:"):
        device_id = value.split(":", 1)[1]
        if not _DEVICE_ID_PATTERN.fullmatch(device_id):
            raise ValueError("小智设备编号格式不正确")
        return CameraSelection(value, "xiaozhi", device_id)
    raise ValueError("camera_id 必须是 local、rtsp、xiaozhi 或 xiaozhi:<设备ID>")


def resolve_camera_selection(
    camera_id: str = "",
    source: str = "local",
    device_id: str = "",
) -> CameraSelection:
    """Prefer camera_id while keeping source/device_id backward compatible."""
    if str(camera_id or "").strip():
        return parse_camera_id(camera_id)

    normalized_source = str(source or "local").strip()
    normalized_device = str(device_id or "").strip()
    return CameraSelection(
        camera_id=to_camera_id(normalized_source, normalized_device),
        source=normalized_source,
        device_id=normalized_device if normalized_source == "xiaozhi" else "",
    )
