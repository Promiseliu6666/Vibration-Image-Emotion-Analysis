import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ruoyi-fastapi-backend'))
from hik_vision.camera_bridge_config import get_camera_bridge_key
from hik_vision.fatigue_service import FatigueServiceSupervisor

class BridgeKeyTests(unittest.TestCase):
    def test_atomic_concurrent_initialization(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            with ThreadPoolExecutor(max_workers=12) as pool:
                keys = list(pool.map(lambda _: get_camera_bridge_key(root), range(30)))
            self.assertEqual(len(set(keys)), 1)
            self.assertTrue(keys[0])
            self.assertFalse((root / 'xiaozhi-study/.runtime').exists())
    def test_actual_watcher_key_is_reused_without_overwriting_root(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            for path, key in [('xiaozhi-study/.runtime', 'watcher-key'), ('.runtime', 'old-key')]:
                (root/path).mkdir(parents=True)
                (root/path/'camera-bridge-secret.txt').write_text(key)
            self.assertEqual(get_camera_bridge_key(root), 'watcher-key')
            self.assertEqual((root/'.runtime/camera-bridge-secret.txt').read_text(), 'old-key')
    def test_existing_runtime_gets_missing_key_without_creating_runtime(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            watcher = root / 'xiaozhi-study/.runtime'
            watcher.mkdir(parents=True)
            key = get_camera_bridge_key(root)
            self.assertEqual((watcher / 'camera-bridge-secret.txt').read_text(), key)
    def test_empty_existing_key_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            path = root / '.runtime/camera-bridge-secret.txt'
            path.parent.mkdir()
            path.write_text('')
            with self.assertRaises(ValueError):
                get_camera_bridge_key(root)
            self.assertEqual(path.read_text(), '')

    def test_environment_wins(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'CAMERA_BRIDGE_KEY': 'explicit'}):
            self.assertEqual(get_camera_bridge_key(Path(tmp)), 'explicit')

class FatigueSupervisorTests(unittest.TestCase):
    def test_reuses_healthy_service_without_stopping_it(self):
        with patch.dict(os.environ, {}, clear=True), patch('hik_vision.fatigue_service.subprocess.Popen') as spawn:
            service = FatigueServiceSupervisor()
            with patch.object(service, '_healthy', return_value=True):
                service._start()
            service.stop()
            spawn.assert_not_called()
            self.assertEqual(service.status()['state'], 'reused')
    def test_remote_and_disabled_never_spawn(self):
        for env in ({'FATIGUE_SERVICE_URL': 'http://other:9101'}, {'FATIGUE_SERVICE_AUTOSTART': 'false'}):
            with patch.dict(os.environ, env, clear=True), patch('hik_vision.fatigue_service.subprocess.Popen') as spawn:
                service = FatigueServiceSupervisor()
                service._start()
                spawn.assert_not_called()
    def test_launches_hidden_child_with_shared_key_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            python = root / '.runtime/fatigue-venv/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.touch()
            service = FatigueServiceSupervisor(root)
            with patch.object(service, '_healthy', return_value=False), \
                 patch('hik_vision.fatigue_service.socket.socket'), \
                 patch('hik_vision.fatigue_service.subprocess.Popen') as spawn, \
                 patch.object(service, '_wait_ready', side_effect=service._stop.set):
                service._start()
            args, kwargs = spawn.call_args
            self.assertEqual(args[0], [str(python), str(root / 'start_fatigue.py')])
            self.assertTrue(kwargs['env']['CAMERA_BRIDGE_KEY'])
            self.assertIn('creationflags', kwargs)
            self.assertTrue((root / '.runtime/fatigue-service.log').is_file())

    def test_stop_only_terminates_owned_process(self):
        service = FatigueServiceSupervisor()
        process = Mock()
        process.poll.return_value = None
        service._process = process
        service.stop()
        process.terminate.assert_called_once()

if __name__ == '__main__': unittest.main()
