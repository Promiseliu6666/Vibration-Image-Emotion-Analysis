"""Capture-compatible remote reader; never falls back to a host webcam."""
from pathlib import Path
import time,requests,cv2,numpy as np
class XiaozhiCapture:
 def __init__(self,device=''):
  self.device=device;self.session=requests.Session();self.session.trust_env=False;self.last=None
  self.key=(Path(__file__).resolve().parents[2]/'.runtime/camera-bridge-secret.txt').read_text(encoding='utf-8').strip()
 def read(self):
  r=self.session.get('http://127.0.0.1:8000/api/camera-source/frame',params={'device_id':self.device},headers={'X-Camera-Bridge-Key':self.key},timeout=5)
  r.raise_for_status();seq=r.headers.get('X-Frame-Sequence');stamp=float(r.headers.get('X-Captured-At','0'))
  if not stamp or time.time()-stamp>5:raise ValueError('小智摄像头画面已过期')
  if seq==self.last:time.sleep(.08);return True,None
  frame=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_COLOR)
  if frame is None:raise ValueError('小智摄像头图像解码失败')
  if not self.device:self.device=r.headers.get('X-Device-Id','')
  self.last=seq;return True,frame
 def get(self,prop):return 15 if prop==cv2.CAP_PROP_FPS else 0
 def release(self):self.session.close()
