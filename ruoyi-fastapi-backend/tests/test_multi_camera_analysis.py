import json
import sys
import time
import types
import unittest
from pathlib import Path

import cv2
import numpy as np


class _DummyNet:
    pass


cv2.dnn.readNetFromCaffe = lambda *args, **kwargs: _DummyNet()
sys.modules.setdefault(
    "hik_vision.email_service",
    types.SimpleNamespace(send_analysis_email=lambda *args, **kwargs: None),
)

from hik_vision import hik_vision
from hik_vision.local_video_analysis import LocalVideoAnalysisCapabilities
from module_xuzhou.controller import command_controller
from algorithm.runtime_service import (
    AlgorithmRunRegistry,
    AlgorithmRuntimeService,
    algorithm_run_registry,
)


class MultiCameraStateTests(unittest.TestCase):
    def setUp(self):
        hik_vision.global_caps.clear()
        hik_vision.active_clients.clear()
        hik_vision.latest_results.clear()
        hik_vision.stable_state.clear()
        hik_vision.video_writers.clear()
        hik_vision.video_start_times.clear()

    def test_camera_state_is_created_per_vid_id(self):
        key_1 = hik_vision.get_camera_key(vid_id=11, source="rtsp")
        key_2 = hik_vision.get_camera_key(vid_id=12, source="rtsp")

        state_1 = hik_vision.ensure_camera_state(key_1)
        state_2 = hik_vision.ensure_camera_state(key_2)

        state_1["matched_person"] = "camera-11"
        hik_vision.latest_results[key_1]["e1"] = 11.0
        state_2["matched_person"] = "camera-12"
        hik_vision.latest_results[key_2]["e1"] = 12.0

        self.assertEqual("vid_11", key_1)
        self.assertEqual("vid_12", key_2)
        self.assertEqual("camera-11", hik_vision.stable_state[key_1]["matched_person"])
        self.assertEqual("camera-12", hik_vision.stable_state[key_2]["matched_person"])
        self.assertEqual(11.0, hik_vision.latest_results[key_1]["e1"])
        self.assertEqual(12.0, hik_vision.latest_results[key_2]["e1"])
        self.assertIsNone(hik_vision.global_caps[key_1])
        self.assertIsNone(hik_vision.global_caps[key_2])
        self.assertEqual(0, hik_vision.active_clients[key_1])
        self.assertEqual(0, hik_vision.active_clients[key_2])

    def test_legacy_source_state_still_works_without_vid_id(self):
        key = hik_vision.get_camera_key(vid_id=None, source="local")
        state = hik_vision.ensure_camera_state(key)

        state["matched_person"] = "local-camera"

        self.assertEqual("local", key)
        self.assertEqual("local-camera", hik_vision.stable_state["local"]["matched_person"])

    def test_local_display_face_rect_is_mirrored_with_frame(self):
        rect = (10, 5, 20, 30)

        display_rect = hik_vision.get_display_face_rect("local", rect, frame_width=100)

        self.assertEqual((70, 5, 20, 30), display_rect)

    def test_rtsp_display_face_rect_is_not_mirrored(self):
        rect = (10, 5, 20, 30)

        display_rect = hik_vision.get_display_face_rect("rtsp", rect, frame_width=100)

        self.assertEqual(rect, display_rect)

    def test_face_detection_model_paths_use_algorithm_model_directory(self):
        self.assertEqual(
            Path("algorithm/model/face_detection/v1/deploy.prototxt"),
            Path(hik_vision.MODEL_PROTO),
        )
        self.assertEqual(
            Path("algorithm/model/face_detection/v1/res10_300x300_ssd_iter_140000.caffemodel"),
            Path(hik_vision.MODEL_WEIGHTS),
        )

    def test_vibraimage_face_detection_uses_algorithm_model_directory(self):
        captured_paths = []
        original_exists = hik_vision.os.path.exists
        original_read_net = cv2.dnn.readNetFromCaffe

        def fake_exists(path):
            return str(path).replace("\\", "/") in {
                "algorithm/model/face_detection/v1/deploy.prototxt",
                "algorithm/model/face_detection/v1/res10_300x300_ssd_iter_140000.caffemodel",
            }

        def fake_read_net(config_file, model_file):
            captured_paths.extend([config_file, model_file])
            raise RuntimeError("stop after path capture")

        hik_vision.os.path.exists = fake_exists
        cv2.dnn.readNetFromCaffe = fake_read_net
        try:
            with self.assertRaises(RuntimeError):
                hik_vision.VibraimageCore()._detect_face(np.zeros((480, 640, 3), dtype=np.uint8))
        finally:
            hik_vision.os.path.exists = original_exists
            cv2.dnn.readNetFromCaffe = original_read_net

        self.assertEqual(
            [
                "algorithm/model/face_detection/v1/deploy.prototxt",
                "algorithm/model/face_detection/v1/res10_300x300_ssd_iter_140000.caffemodel",
            ],
            [path.replace("\\", "/") for path in captured_paths],
        )

    def test_prepare_face_crop_keeps_bgr_channel_order_for_arcface_preprocess(self):
        frame = np.array([[[10, 20, 30]]], dtype=np.uint8)

        face_crop = hik_vision.prepare_face_crop(frame, None)

        self.assertEqual([10, 20, 30], face_crop[0, 0].tolist())

    def test_face_recognition_can_run_while_happiness_analysis_is_active(self):
        state = hik_vision._new_analysis_state()
        state["last_detected_rect"] = (10, 20, 30, 40)
        state["analyzing"] = True
        state["identified"] = False
        capabilities = LocalVideoAnalysisCapabilities(
            enable_local_worker=True,
            enable_face_detection=True,
            enable_face_recognition=True,
            enable_happiness_analysis=True,
        )

        self.assertTrue(
            hik_vision.can_schedule_face_recognition(
                recognition_rect=hik_vision.get_recognition_face_rect(None, state),
                state=state,
                local_capabilities=capabilities,
                analysis_count=hik_vision.RECOGNIZE_INTERVAL,
                now=time.time() + hik_vision.RECOGNIZE_MIN_GAP_SECONDS,
            )
        )


class AlgorithmRuntimeServiceTests(unittest.TestCase):
    def setUp(self):
        self.registry = AlgorithmRunRegistry()

    def test_local_analysis_binding_is_created_when_video_has_no_legacy_algorithms(self):
        video_detail = {"vid_id": 2, "vid_algorithm": None}

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual(1, len(bindings))
        self.assertEqual("realtime_face_analysis", bindings[0].algorithm_code)
        self.assertEqual("local", bindings[0].runtime_type)
        self.assertEqual("enabled", bindings[0].status)

    def test_no_algorithm_binding_is_created_when_camera_config_is_empty_list(self):
        video_detail = {"vid_id": 2, "vid_algorithm": []}

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual([], bindings)

    def test_no_algorithm_binding_is_created_when_camera_config_is_empty_json_string(self):
        video_detail = {"vid_id": 2, "vid_algorithm": "[]"}

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual([], bindings)

    def test_local_analysis_capabilities_disable_happiness_when_not_configured(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 20,
                    "algName": "人脸检测",
                    "algSerial": "face_detection",
                    "algVersion": "v1",
                    "runtimeType": "local",
                },
                {
                    "algId": 21,
                    "algName": "人脸特征识别",
                    "algSerial": "face_recognition",
                    "algVersion": "v1",
                    "runtimeType": "local",
                },
            ],
        }

        capabilities = LocalVideoAnalysisCapabilities.from_video_detail(video_detail)

        self.assertTrue(capabilities.enable_local_worker)
        self.assertTrue(capabilities.enable_face_detection)
        self.assertTrue(capabilities.enable_face_recognition)
        self.assertFalse(capabilities.enable_happiness_analysis)

    def test_local_analysis_capabilities_disable_recognition_when_not_configured(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 20,
                    "algName": "人脸跟踪",
                    "algSerial": "face_detection",
                    "algVersion": "v1",
                    "runtimeType": "local",
                }
            ],
        }

        capabilities = LocalVideoAnalysisCapabilities.from_video_detail(video_detail)

        self.assertTrue(capabilities.enable_local_worker)
        self.assertTrue(capabilities.enable_face_detection)
        self.assertFalse(capabilities.enable_face_recognition)
        self.assertFalse(capabilities.enable_happiness_analysis)

    def test_local_analysis_capabilities_enable_recognition_for_arcface_algorithm(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 2,
                    "algName": "人脸特征识别",
                    "algSerial": "arcface_recognition",
                    "algVersion": "v1",
                    "runtimeType": "local",
                }
            ],
        }

        capabilities = LocalVideoAnalysisCapabilities.from_video_detail(video_detail)

        self.assertTrue(capabilities.enable_local_worker)
        self.assertTrue(capabilities.enable_face_detection)
        self.assertTrue(capabilities.enable_face_recognition)
        self.assertFalse(capabilities.enable_happiness_analysis)

    def test_local_analysis_capabilities_enable_happiness_when_configured(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 8,
                    "algName": "实时人脸幸福指数分析",
                    "algSerial": "realtime_face_analysis",
                    "algVersion": "v1",
                    "runtimeType": "local",
                }
            ],
        }

        capabilities = LocalVideoAnalysisCapabilities.from_video_detail(video_detail)

        self.assertTrue(capabilities.enable_local_worker)
        self.assertTrue(capabilities.enable_face_detection)
        self.assertFalse(capabilities.enable_face_recognition)
        self.assertTrue(capabilities.enable_happiness_analysis)

    def test_runtime_type_local_binding_runs_locally(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 20,
                    "algName": "本地烟火检测",
                    "algSerial": "fire_detection",
                    "algVersion": "v1",
                    "runtimeType": "local",
                    "algDefaultConf": {"threshold": 0.7},
                }
            ],
        }

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual(1, len(bindings))
        self.assertEqual("fire_detection", bindings[0].algorithm_code)
        self.assertEqual("local", bindings[0].runtime_type)

    def test_runtime_type_external_box_binding_runs_on_box(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 21,
                    "algName": "盒子人脸识别",
                    "algSerial": "face_recognition",
                    "algVersion": "v1",
                    "runtimeType": "external_box",
                    "algDefaultConf": {"threshold": 0.8},
                }
            ],
        }

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual(1, len(bindings))
        self.assertEqual("face_recognition", bindings[0].algorithm_code)
        self.assertEqual("external_box", bindings[0].runtime_type)
        self.assertEqual({"threshold": 0.8}, bindings[0].params["default_conf"])

    def test_external_box_bindings_are_normalized_from_legacy_video_algorithm_json(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {"algId": 4, "algName": "烟火检测", "algDefaultConf": {"threshold": 0.6}},
                {"algId": "helmet", "algName": "安全帽", "algDefaultConf": "{\"threshold\": 0.8}"},
            ],
        }

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual(["4", "helmet"], [binding.algorithm_code for binding in bindings])
        self.assertEqual(["external_box", "external_box"], [binding.runtime_type for binding in bindings])
        self.assertEqual({"threshold": 0.6}, bindings[0].params)
        self.assertEqual({"threshold": 0.8}, bindings[1].params)

    def test_external_box_binding_includes_version_weight_and_default_conf(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 9,
                    "algName": "烟火检测",
                    "algSerial": "fire_detection",
                    "algVersion": "v1",
                    "algWeightPath": "algorithm/model/fire_detection/v1/fire.onnx",
                    "algDefaultConf": {"threshold": 0.6},
                }
            ],
        }

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual(1, len(bindings))
        self.assertEqual("fire_detection", bindings[0].algorithm_code)
        self.assertEqual("v1", bindings[0].params["alg_version"])
        self.assertEqual("algorithm/model/fire_detection/v1/fire.onnx", bindings[0].params["weight_path"])
        self.assertEqual({"threshold": 0.6}, bindings[0].params["default_conf"])
        self.assertEqual(9, bindings[0].params["alg_id"])

    def test_registry_tracks_runs_by_camera_and_algorithm(self):
        local_binding = AlgorithmRuntimeService.create_local_binding(vid_id=2)
        external_binding = AlgorithmRuntimeService.create_external_box_binding(
            vid_id=2,
            algorithm_code="fire_detection",
            algorithm_name="烟火检测",
            params={},
        )

        local_run = self.registry.start_run(local_binding)
        external_run = self.registry.start_run(external_binding, external_task_id="publish_2_fire_detection")

        self.assertNotEqual(local_run.run_id, external_run.run_id)
        self.assertEqual("running", self.registry.get_run(2, "realtime_face_analysis").status)
        self.assertEqual("running", self.registry.get_run(2, "fire_detection").status)

        self.registry.stop_camera_runs(2)

        self.assertEqual("stopped", self.registry.get_run(2, "realtime_face_analysis").status)
        self.assertEqual("stopped", self.registry.get_run(2, "fire_detection").status)

class DeviceStatusCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        command_controller.device_status_cache.clear()

    async def test_device_status_updates_incrementally_by_vid_id(self):
        now = time.time()
        await command_controller.save_device_status({
            "serial": "0004",
            "type": "devices",
            "time": now,
            "devices": [{"vid_id": 11, "status": "running", "start_time": now}],
        })
        await command_controller.save_device_status({
            "serial": "0004",
            "type": "devices",
            "time": now,
            "devices": [{"vid_id": 12, "status": "running", "start_time": now}],
        })

        self.assertEqual("running", command_controller.device_status_cache[11]["status"])
        self.assertEqual("running", command_controller.device_status_cache[12]["status"])
        self.assertEqual(now, command_controller.device_status_cache[11]["start_time"])
        self.assertEqual(now, command_controller.device_status_cache[12]["start_time"])

    async def test_external_box_status_waits_until_device_callback(self):
        algorithm_run_registry._runs.clear()
        binding = AlgorithmRuntimeService.create_external_box_binding(
            vid_id=13,
            algorithm_code="fire_detection",
            algorithm_name="烟火检测",
            params={},
        )
        algorithm_run_registry.start_run(
            binding,
            external_task_id="publish_13_fire_detection",
            status="waiting_box",
            error_message="等待外接盒子设备状态回调",
        )

        self.assertEqual("waiting_box", algorithm_run_registry.get_run(13, "fire_detection").status)

        now = time.time()
        await command_controller.save_device_status({
            "serial": "0004",
            "type": "devices",
            "time": now,
            "devices": [{"vid_id": 13, "status": "running", "start_time": now}],
        })

        self.assertEqual("running", algorithm_run_registry.get_run(13, "fire_detection").status)


class PushVideoConfigCamelCaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        algorithm_run_registry._runs.clear()
        command_controller.device_status_cache.clear()
        command_controller.video_start_time.clear()

    async def test_push_video_config_uses_camel_case_video_details(self):
        original_video_detail_services = command_controller.VideoService.video_detail_services
        original_send_message = command_controller.RabbitMQService.send_message
        sent_messages = []

        fake_video_detail = {
            "vidId": 21,
            "vidSerial": "cam-21",
            "vidType": "local",
            "vidUri": "0",
            "vidAlgorithm": [
                {
                    "algId": 12,
                    "algName": "烟火检测",
                    "algSerial": "fire_detection",
                    "algDefaultConf": {"threshold": 0.6},
                }
            ],
            "vidAlgorithmName": ["烟火检测"],
        }

        async def fake_video_detail_services(db, vid_id):
            self.assertEqual(21, vid_id)
            return fake_video_detail

        async def fake_send_message(app, queue_name, message_json):
            sent_messages.append((queue_name, message_json))

        request = types.SimpleNamespace(
            method="POST",
            app=object(),
            headers={"host": "test.local"},
            client=types.SimpleNamespace(host="127.0.0.1"),
            url=types.SimpleNamespace(scheme="http"),
        )

        command_controller.VideoService.video_detail_services = fake_video_detail_services
        command_controller.RabbitMQService.send_message = fake_send_message
        try:
            result = await command_controller.push_video_config(
                request,
                command_controller.PushVideoConfigRequest(vid_id=21),
                db=object(),
            )
        finally:
            command_controller.VideoService.video_detail_services = original_video_detail_services
            command_controller.RabbitMQService.send_message = original_send_message

        self.assertEqual(1, len(sent_messages))
        queue_name, message_json = sent_messages[0]
        message_data = json.loads(message_json)
        response_data = json.loads(result.body.decode())
        self.assertEqual("algorithm_0004", queue_name)
        self.assertEqual(21, message_data["vid_id"])
        self.assertEqual("cam-21", message_data["vid_serial"])
        self.assertEqual("local", message_data["stream_type"])
        self.assertEqual("0", message_data["stream_url"])
        self.assertEqual("publish_21", message_data["publish_path"])
        self.assertEqual("fire_detection", message_data["algorithms"][0]["code"])
        self.assertEqual("cam-21", response_data["data"]["serial"])
        self.assertEqual("publish_21", response_data["data"]["publish_path"])
        self.assertEqual("waiting_box", algorithm_run_registry.get_run(21, "fire_detection").status)


class RealtimeRecognitionSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_recognition_match_without_happiness_does_not_start_analysis_mode(self):
        state = hik_vision._new_analysis_state()
        capabilities = LocalVideoAnalysisCapabilities(
            enable_local_worker=True,
            enable_face_detection=True,
            enable_face_recognition=True,
            enable_happiness_analysis=False,
        )

        class FakeAnalyzer:
            def reset(self):
                raise AssertionError("happiness analyzer should not reset")

        await hik_vision.apply_recognition_match(
            "Alice",
            (10, 20, 30, 40),
            state,
            FakeAnalyzer(),
            capabilities,
        )

        self.assertFalse(state["analyzing"])
        self.assertIsNone(state["analysis_start_time"])
        self.assertEqual((10, 20, 30, 40), state["locked_rect"])

    async def test_recognition_match_with_happiness_does_not_start_analysis_mode(self):
        state = hik_vision._new_analysis_state()
        capabilities = LocalVideoAnalysisCapabilities(
            enable_local_worker=True,
            enable_face_detection=True,
            enable_face_recognition=True,
            enable_happiness_analysis=True,
        )

        class FakeAnalyzer:
            def reset(self):
                raise AssertionError("identity recognition should not start happiness analysis")

        await hik_vision.apply_recognition_match(
            "Alice",
            (10, 20, 30, 40),
            state,
            FakeAnalyzer(),
            capabilities,
        )

        self.assertFalse(state["analyzing"])
        self.assertIsNone(state["analysis_start_time"])
        self.assertEqual((10, 20, 30, 40), state["locked_rect"])

    async def test_happiness_analysis_starts_from_stable_face_without_identity_match(self):
        state = hik_vision._new_analysis_state()
        state["last_detected_rect"] = (10, 20, 30, 40)
        state["matched_person"] = "Unknown"
        capabilities = LocalVideoAnalysisCapabilities(
            enable_local_worker=True,
            enable_face_detection=True,
            enable_face_recognition=False,
            enable_happiness_analysis=True,
        )
        reset_calls = []

        class FakeAnalyzer:
            def reset(self):
                reset_calls.append(True)

        await hik_vision.start_happiness_analysis_if_ready(state, FakeAnalyzer(), capabilities)

        self.assertTrue(state["analyzing"])
        self.assertEqual((10, 20, 30, 40), state["locked_rect"])
        self.assertIsNotNone(state["analysis_start_time"])
        self.assertEqual([True], reset_calls)

    async def test_persist_analysis_result_uses_fresh_session(self):
        original_session_local = hik_vision.AsyncSessionLocal
        original_add = hik_vision.BinhuaAnalysisDao.add_analysis_dao
        sessions_seen = []

        class SessionFactory:
            async def __aenter__(self):
                return session_from_factory

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeSession:
            async def commit(self):
                return None

        session_from_factory = FakeSession()

        async def fake_add(db, analysis):
            sessions_seen.append(db)
            return 1

        hik_vision.AsyncSessionLocal = lambda: SessionFactory()
        hik_vision.BinhuaAnalysisDao.add_analysis_dao = fake_add
        try:
            result = await hik_vision.persist_analysis_result(
                "local",
                {"person_id": 7, "matched_person": "Alice"},
                {"e12": 88.0},
                "videos/demo.mp4",
            )
        finally:
            hik_vision.AsyncSessionLocal = original_session_local
            hik_vision.BinhuaAnalysisDao.add_analysis_dao = original_add

        self.assertEqual(1, result)
        self.assertEqual([session_from_factory], sessions_seen)

    async def test_recognize_face_uses_independent_database_session(self):
        original_session_local = hik_vision.AsyncSessionLocal
        original_compare = hik_vision.PeopleService.face_compare_by_face_crop_services
        original_prepare = hik_vision.prepare_face_crop
        original_to_thread = hik_vision.asyncio.to_thread
        session_from_request = object()
        session_from_factory = object()
        sessions_seen = []

        class SessionFactory:
            async def __aenter__(self):
                return session_from_factory

            async def __aexit__(self, exc_type, exc, tb):
                return False

        async def fake_compare(db, face_image, group_id, threshold):
            sessions_seen.append(db)
            return [{}]

        async def immediate_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        hik_vision.AsyncSessionLocal = lambda: SessionFactory()
        hik_vision.PeopleService.face_compare_by_face_crop_services = fake_compare
        hik_vision.prepare_face_crop = lambda frame, face_rect: frame
        hik_vision.asyncio.to_thread = immediate_to_thread
        try:
            await hik_vision.recognize_face(
                session_from_request,
                np.zeros((1, 1, 3), dtype=np.uint8),
                None,
                {"person_id": "", "matched_person": None, "identified": False},
            )
        finally:
            hik_vision.AsyncSessionLocal = original_session_local
            hik_vision.PeopleService.face_compare_by_face_crop_services = original_compare
            hik_vision.prepare_face_crop = original_prepare
            hik_vision.asyncio.to_thread = original_to_thread

        self.assertEqual([session_from_factory], sessions_seen)


if __name__ == "__main__":
    unittest.main()
