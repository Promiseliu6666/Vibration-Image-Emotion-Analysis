import unittest
from types import SimpleNamespace

from module_xuzhou.controller import command_controller
from module_xuzhou.dao.video_dao import VideoDao
from module_xuzhou.entity.do.video_do import XuzhouVideo
from module_xuzhou.service.video_service import VideoService


class VideoListDeviceStatusTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        command_controller.device_status_cache.clear()

    async def test_local_camera_without_callback_is_returned_running(self):
        original_get_video_list = VideoDao.get_video_list
        original_get_video_count = VideoDao.get_video_count
        rows = [
            {"vidId": 1, "vidType": "local", "vidAlgorithm": None, "vidAlgorithmName": None},
            {"vidId": 2, "vidType": "rtsp", "vidAlgorithm": None, "vidAlgorithmName": None},
        ]

        async def fake_get_video_list(query_db, query_object, is_page):
            return SimpleNamespace(rows=rows)

        async def fake_get_video_count(query_db):
            return len(rows)

        VideoDao.get_video_list = fake_get_video_list
        VideoDao.get_video_count = fake_get_video_count
        try:
            result = await VideoService.get_video_list_services(None, None)
        finally:
            VideoDao.get_video_list = original_get_video_list
            VideoDao.get_video_count = original_get_video_count

        self.assertEqual("running", result.rows[0]["deviceStatus"])
        self.assertTrue(result.rows[0]["isRunning"])
        self.assertEqual("unknown", result.rows[1]["deviceStatus"])
        self.assertFalse(result.rows[1]["isRunning"])
        self.assertEqual(1, result.running_count)
        self.assertEqual(1, result.stopped_count)


class VideoDetailTests(unittest.IsolatedAsyncioTestCase):
    async def test_video_detail_returns_camel_case_fields_for_frontend_binding(self):
        original_get_video_detail_by_id = VideoDao.get_video_detail_by_id

        video = XuzhouVideo(
            vid_id=9,
            vid_name="本地摄像头",
            vid_serial="local-9",
            vid_type="local",
            vid_algorithm='[{"algId": 12, "algName": "烟火检测"}]',
            vid_algorithm_name='["烟火检测"]',
            vid_uri="demo.mp4",
            vid_analysis_mode="realtime",
            vid_update_time=None,
        )

        async def fake_get_video_detail_by_id(db, vid_id):
            return video

        VideoDao.get_video_detail_by_id = fake_get_video_detail_by_id
        try:
            result = await VideoService.video_detail_services(None, 9)
        finally:
            VideoDao.get_video_detail_by_id = original_get_video_detail_by_id

        self.assertEqual(9, result["vidId"])
        self.assertEqual("本地摄像头", result["vidName"])
        self.assertEqual("local", result["vidType"])
        self.assertEqual([{"algId": 12, "algName": "烟火检测"}], result["vidAlgorithm"])
        self.assertEqual(["烟火检测"], result["vidAlgorithmName"])


if __name__ == "__main__":
    unittest.main()
