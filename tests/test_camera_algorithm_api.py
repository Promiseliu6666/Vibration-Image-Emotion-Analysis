"""Exercise the real camera routes without booting GPU models or the database."""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
import sys

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

BACKEND = Path(__file__).resolve().parents[1] / 'ruoyi-fastapi-backend'
sys.path.insert(0, str(BACKEND))
from hik_vision.camera_algorithms import ALGORITHMS, CameraAlgorithmStore
from hik_vision.camera_contract import to_camera_id


class CameraAlgorithmApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        async def require_user(request: Request):
            if request.headers.get('Authorization') != 'Bearer test':
                raise HTTPException(401, '请登录')

        namespace = {
            'videoController': APIRouter(prefix='/video'),
            '_require_video_user': require_user, 'Depends': Depends,
            'HTTPException': HTTPException, 'BaseModel': BaseModel, 'Field': Field,
            'ALGORITHMS': ALGORITHMS, 'RTSP_URL': '', 'to_camera_id': to_camera_id,
            'camera_algorithm_store': CameraAlgorithmStore(Path(temporary.name) / 'config.json'),
            '_fetch_xiaozhi_devices': AsyncMock(return_value=[
                {'device_id': 'watcher-1', 'name': '值班室', 'online': False},
            ]),
        }
        tree = ast.parse((BACKEND / 'hik_vision/hik_vision.py').read_text(encoding='utf-8'))
        selected = {'camera_catalog', 'CameraAnalysisConfig', 'analysis_algorithms', 'save_camera_analysis'}
        module = ast.Module(body=[node for node in tree.body if getattr(node, 'name', '') in selected], type_ignores=[])
        exec(compile(module, '<camera-routes>', 'exec'), namespace)
        self.namespace = namespace
        app = FastAPI()
        app.include_router(namespace['videoController'])
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                                        headers={'Authorization': 'Bearer test'})
        self.addAsyncCleanup(self.client.aclose)

    async def test_catalog_and_algorithms_require_authentication(self):
        for path in ['/video/cameras', '/video/algorithms']:
            response = await self.client.get(path, headers={'Authorization': ''})
            self.assertEqual(response.status_code, 401)
        response = await self.client.put('/video/cameras/local/analysis',
                                        json={'algorithm_id': 'fatigue', 'scene': '值班室'},
                                        headers={'Authorization': ''})
        self.assertEqual(response.status_code, 401)

    async def test_save_offline_watcher_and_reload_catalog(self):
        response = await self.client.put('/video/cameras/xiaozhi%3Awatcher-1/analysis',
                                        json={'algorithm_id': 'fatigue', 'scene': '值班室'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['analysis']['show_overlay'])
        cameras = (await self.client.get('/video/cameras')).json()['cameras']
        self.assertEqual(cameras[-1]['analysis']['algorithm_id'], 'fatigue')
        self.assertEqual(cameras[0]['analysis']['algorithm_id'], 'vibration')
        algorithms = (await self.client.get('/video/algorithms')).json()['algorithms']
        self.assertEqual(len([a for a in algorithms if a['selectable']]), 2)

    async def test_multiple_algorithms_and_empty_selection(self):
        response = await self.client.put('/video/cameras/local/analysis',
            json={'algorithm_ids':['vibration','fatigue'], 'scene':'值班室'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['analysis']['algorithm_ids'], ['vibration','fatigue'])
        response = await self.client.put('/video/cameras/local/analysis',
            json={'algorithm_ids':[], 'scene':'值班室'})
        self.assertEqual(response.status_code, 400)

    async def test_reject_missing_camera_auxiliary_algorithm_and_invalid_scene(self):
        for camera, config, status in [
            ('xiaozhi:missing', {'algorithm_id': 'fatigue', 'scene': '值班室'}, 404),
            ('local', {'algorithm_id': 'face_detection', 'scene': '值班室'}, 400),
            ('local', {'algorithm_id': 'fatigue', 'scene': ' '}, 400),
            ('local', {'algorithm_id': 'fatigue', 'scene': ''}, 422),
        ]:
            response = await self.client.put(f'/video/cameras/{camera}/analysis', json=config)
            self.assertEqual(response.status_code, status, response.text)

    async def test_unavailable_watcher_service_still_lists_native_sources(self):
        self.namespace['_fetch_xiaozhi_devices'].side_effect = HTTPException(503, '小智服务未连接')
        response = await self.client.get('/video/cameras')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['cameras']), 2)
        self.assertEqual(response.json()['xiaozhi_error'], '小智服务未连接')


if __name__ == '__main__':
    unittest.main()
