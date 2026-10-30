"""Short-lived UI-only cache. Hardware commands always check current physical identity."""
import time
from threading import RLock
from app.device import capture_control
_lock=RLock()
_capture=None
_deadline=0
def snapshot():
    global _capture,_deadline
    with _lock:
        if _capture is None or time.monotonic()>=_deadline:
            _capture=capture_control.status()
            _deadline=time.monotonic()+2
        return _capture.copy()
def invalidate():
    global _deadline
    with _lock:_deadline=0
