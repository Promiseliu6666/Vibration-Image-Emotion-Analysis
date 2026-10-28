"""One native capture per source; readers receive independent frame copies."""
import threading,time
import cv2

class CameraHub:
    def __init__(self,source,opener):
        self.source=source;self.opener=opener;self.lock=threading.RLock()
        self.frame=None;self.sequence=0;self.captured_at=0.;self.demand=0.;self.thread=None
        self.fps=30.;self.error='等待摄像头连接';self.closed=False
    def touch(self):
        with self.lock:
            self.demand=time.monotonic()
            if not self.thread or not self.thread.is_alive():
                self.closed=False;self.thread=threading.Thread(target=self._run,daemon=True,name='camera-'+self.source);self.thread.start()
    def _run(self):
        cap=None
        try:
            while not self.closed and time.monotonic()-self.demand<15:
                if cap is None:
                    try:
                        cap=self.opener(self.source);self.fps=cap.get(cv2.CAP_PROP_FPS) or 30
                    except Exception:
                        with self.lock:self.error='摄像头无法连接，请检查设备或 RTSP 配置'
                        time.sleep(1);continue
                try:ok,frame=cap.read()
                except Exception:ok,frame=False,None
                if ok and frame is None:
                    time.sleep(.03);continue
                if ok:
                    with self.lock:
                        self.frame=frame;self.sequence+=1;self.captured_at=time.time();self.error=None
                else:
                    with self.lock:self.error='摄像头未返回新画面，正在重连'
                    cap.release();cap=None;time.sleep(.3)
                time.sleep(.015)
        finally:
            if cap is not None:cap.release()
            with self.lock:self.frame=None;self.captured_at=0
    def latest(self):
        self.touch()
        with self.lock:
            if self.frame is None or time.time()-self.captured_at>2:return None,self.sequence,self.captured_at
            return self.frame.copy(),self.sequence,self.captured_at
    def subscribe(self):return CameraReader(self)
    def close(self):self.closed=True

class CameraReader:
    def __init__(self,hub):self.hub=hub;self.sequence=-1;self.released=False;hub.touch()
    def read(self):
        if self.released:return False,None
        frame,seq,_=self.hub.latest()
        if frame is None or seq==self.sequence:return False,None
        self.sequence=seq;return True,frame
    def get(self,prop):return self.hub.fps if prop==cv2.CAP_PROP_FPS else 0
    def release(self):self.released=True
