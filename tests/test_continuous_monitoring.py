import ast
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContinuousMonitoringTests(unittest.TestCase):
    def test_live_history_keeps_recent_minute_without_accumulating_forever(self):
        sys.path.insert(0, str(ROOT / 'ruoyi-fastapi-backend'))
        from hik_vision.Vibration_image_algorithm import VibraimageCore
        core = VibraimageCore()
        core.fps = 2
        core.e12_history = list(range(300))
        core.vibration_energies = list(range(300))
        core._trim_live_history()
        self.assertEqual(core.e12_history, list(range(180, 300)))
        self.assertEqual(core.vibration_energies, list(range(180, 300)))

    def test_recording_completion_does_not_gate_live_analysis(self):
        tree = ast.parse((ROOT / 'ruoyi-fastapi-backend/hik_vision/hik_vision.py').read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and any(
                isinstance(call, ast.Attribute) and call.attr == 'process_frame'
                for statement in node.body for call in ast.walk(statement)
            ):
                self.assertNotIn('analysis_completed', ast.unparse(node.test))


if __name__ == '__main__':
    unittest.main()
