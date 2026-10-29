import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'ruoyi-fastapi-backend/hik_vision/face_stability.py'
spec=importlib.util.spec_from_file_location('face_gate',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_low_fps_face_ready_without_identity(self):
  gate=m.FaceStabilityGate();self.assertFalse(gate.observe((100,80,90,110),0)['ready']);self.assertFalse(gate.observe((103,81,90,110),.6)['ready']);self.assertTrue(gate.observe((101,82,91,109),1.3)['ready'])
 def test_loss_and_new_subject_reset(self):
  gate=m.FaceStabilityGate();gate.observe((100,80,90,110),0);gate.observe((100,80,90,110),.6);gate.observe((100,80,90,110),1.3)
  self.assertFalse(gate.observe(None,1.6)['lost']);self.assertTrue(gate.observe(None,3)['lost']);self.assertFalse(gate.ready);self.assertFalse(gate.observe((300,80,90,110),3.2)['ready'])
 def test_large_motion_requires_new_stable_window(self):
  gate=m.FaceStabilityGate();gate.observe((100,80,90,110),0);gate.observe((100,80,90,110),.6);gate.observe((100,80,90,110),1.3)
  state=gate.observe((300,80,90,110),1.4);self.assertTrue(state['changed']);self.assertFalse(state['ready']);self.assertLess(state['progress'],.5)
 def test_tiny_or_missing_face_cannot_start(self):
  gate=m.FaceStabilityGate()
  for t in range(10):self.assertFalse(gate.observe((100,80,10,10),t)['ready'])
unittest.main()
