import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "ruoyi-fastapi-backend"
sys.path.insert(0, str(BACKEND_ROOT))

from hik_vision.camera_contract import (  # noqa: E402
    parse_camera_id,
    resolve_camera_selection,
    to_camera_id,
)


class CameraContractTests(unittest.TestCase):
    def test_canonical_local_and_rtsp_ids(self):
        self.assertEqual(parse_camera_id("local").camera_id, "local")
        self.assertEqual(parse_camera_id("local:0").camera_id, "local")
        self.assertEqual(parse_camera_id("rtsp").camera_id, "rtsp")
        self.assertEqual(parse_camera_id("rtsp:default").camera_id, "rtsp")

    def test_xiaozhi_device_id_round_trip(self):
        camera_id = to_camera_id("xiaozhi", "watcher-001")
        selection = parse_camera_id(camera_id)
        self.assertEqual(camera_id, "xiaozhi:watcher-001")
        self.assertEqual(selection.source, "xiaozhi")
        self.assertEqual(selection.device_id, "watcher-001")
        self.assertEqual(
            selection.legacy_params(),
            {"source": "xiaozhi", "device_id": "watcher-001"},
        )

    def test_camera_id_takes_precedence_over_legacy_fields(self):
        selection = resolve_camera_selection(
            "xiaozhi:new-device",
            "local",
            "old-device",
        )
        self.assertEqual(selection.camera_id, "xiaozhi:new-device")
        self.assertEqual(selection.device_id, "new-device")

    def test_legacy_fields_remain_supported(self):
        selection = resolve_camera_selection(
            "",
            "xiaozhi",
            "watcher-002",
        )
        self.assertEqual(selection.camera_id, "xiaozhi:watcher-002")
        self.assertEqual(
            selection.legacy_params(),
            {"source": "xiaozhi", "device_id": "watcher-002"},
        )

    def test_non_xiaozhi_ignores_legacy_device_id(self):
        selection = resolve_camera_selection("", "local", "unexpected")
        self.assertEqual(selection.camera_id, "local")
        self.assertEqual(selection.device_id, "")
        self.assertEqual(selection.legacy_params(), {"source": "local"})

    def test_invalid_ids_are_rejected(self):
        for value in ("camera-1", "xiaozhi:", "xiaozhi:has space", "file:test"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_camera_id(value)


if __name__ == "__main__":
    unittest.main()
