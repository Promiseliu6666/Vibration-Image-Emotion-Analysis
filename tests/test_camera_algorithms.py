import sys
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ruoyi-fastapi-backend'))
from hik_vision.camera_algorithms import CameraAlgorithmStore, ALGORITHMS


class CameraAlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.json'
        self.store = CameraAlgorithmStore(self.path)

    def test_defaults_keep_existing_monitor_and_hide_geometry(self):
        self.assertEqual(self.store.get('local'), {
            'algorithm_id': 'vibration', 'scene': '心理状态观察', 'show_overlay': False,
            'algorithm_ids': ['vibration'],
        })

    def test_settings_persist_and_are_isolated_per_device(self):
        saved = self.store.save('xiaozhi:watcher-1', 'fatigue', '值班室', False)
        self.assertEqual(CameraAlgorithmStore(self.path).get('xiaozhi:watcher-1'), saved)
        self.assertEqual(self.store.get('xiaozhi:watcher-2')['algorithm_id'], 'vibration')
        self.store.save('rtsp', 'vibration', '门岗', True)
        self.assertEqual(self.store.get('xiaozhi:watcher-1')['algorithm_id'], 'fatigue')

    def test_multiple_algorithms_persist_and_legacy_configuration_migrates(self):
        saved = self.store.save('local', ['vibration', 'fatigue', 'vibration'], '值班室', False)
        self.assertEqual(saved['algorithm_ids'], ['vibration', 'fatigue'])
        self.assertEqual(CameraAlgorithmStore(self.path).get('local')['algorithm_ids'], ['vibration', 'fatigue'])
        self.path.write_text(json.dumps({'local': {'algorithm_id':'fatigue','scene':'值班室','show_overlay':False}}), encoding='utf-8')
        self.assertEqual(self.store.get('local')['algorithm_ids'], ['fatigue'])

    def test_empty_and_invalid_algorithm_lists_are_rejected(self):
        for algorithms in [[], ['fatigue', 'unknown'], ['face_identity'], [123]]:
            with self.assertRaises(ValueError):
                self.store.save('local', algorithms, '值班室', False)

    def test_bad_input_does_not_overwrite_configuration(self):
        self.store.save('local', 'fatigue', '值班室', False)
        for camera, algorithm, scene in [('local', 'unknown', '门岗'),
                                          ('file:bad', 'fatigue', '门岗'),
                                          ('local', 'fatigue', ' '),
                                          ('local', 'fatigue', 'a' * 81)]:
            with self.assertRaises(ValueError):
                self.store.save(camera, algorithm, scene, False)
        self.assertEqual(self.store.get('local')['algorithm_id'], 'fatigue')

    def test_corrupt_file_is_not_silently_overwritten(self):
        self.path.write_text('{bad json', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.save('local', 'fatigue', '门岗', False)
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{bad json')

    def test_failed_atomic_write_keeps_previous_configuration(self):
        self.store.save('local', 'vibration', '心理状态观察', False)
        with patch('hik_vision.camera_algorithms.os.replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.store.save('local', 'fatigue', '值班室', False)
        self.assertEqual(self.store.get('local')['algorithm_id'], 'vibration')
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_runnable_algorithms_declare_distinct_metrics(self):
        active = {item['id']: item for item in ALGORITHMS if item['selectable']}
        self.assertEqual(set(active), {'vibration', 'fatigue'})
        self.assertIn('fatigue_score', [m['key'] for m in active['fatigue']['metrics']])
        self.assertIn('happiness_index', [m['key'] for m in active['vibration']['metrics']])

    def test_invalid_saved_configuration_is_rejected_instead_of_running_wrong_algorithm(self):
        for config in [[], {'algorithm_id': 'unknown'},
                       {'algorithm_id': 'fatigue', 'scene': '值班室', 'show_overlay': 'false'}]:
            self.path.write_text(json.dumps({'local': config}), encoding='utf-8')
            with self.assertRaises(ValueError):
                self.store.get('local')


if __name__ == '__main__':
    unittest.main()
