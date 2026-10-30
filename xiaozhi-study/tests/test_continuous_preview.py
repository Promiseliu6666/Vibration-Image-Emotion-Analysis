import asyncio
import numpy as np
import cv2
from app.core import live_state
from app.api import ws_handler
from app.api.continuous_preview import packet

def test_original_jpeg_and_independent_analysis_cadence(monkeypatch,tmp_path):
    from app.core.latest_frames import LatestFrames
    queue=LatestFrames(10)
    monkeypatch.setattr(ws_handler,'frame_queue',queue)
    monkeypatch.setattr(ws_handler,'FRAME_SAVE_DIR',str(tmp_path))
    monkeypatch.setattr(ws_handler,'_analysis_received',{})
    clock=[10.]
    # Patch the clock reference used by ingestion, without modifying other timers.
    import time
    monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    ok,encoded=cv2.imencode('.jpg',np.zeros((48,64,3),np.uint8));assert ok
    jpeg=encoded.tobytes();device='preview-regression'
    assert ws_handler._process_frame(jpeg,device)
    assert packet(device)[1]==jpeg
    first=queue.get_nowait();queue.task_done();assert first['preview_jpeg']==jpeg
    clock[0]=10.5;assert ws_handler._process_frame(jpeg,device);assert queue.empty()
    clock[0]=12.1;assert ws_handler._process_frame(jpeg,device);assert queue.qsize()==1
    # Explicit per-request vision analysis must not be silently skipped by the preview cadence.
    clock[0]=12.2;assert ws_handler._process_frame(jpeg,device,request_id='requested-analysis')
    assert queue.get_nowait()['request_id']=='requested-analysis';queue.task_done()
    live_state.forget(device)

def test_preview_packet_offline_and_missing_are_not_streamed():
    live_state.forget('no-preview')
    assert packet('no-preview') is None
    live_state.received('no-preview',b'jpeg')
    with live_state._lock:live_state._devices['no-preview']['last_received']=1
    assert packet('no-preview') is None
    live_state.forget('no-preview')


def test_preview_only_frame_does_not_decode_or_recompress(monkeypatch):
    from app.api import ws_handler
    import time
    device='preview-decode-regression'
    live_state.forget(device)
    ws_handler._analysis_received[device]=time.monotonic()
    jpeg=b'\xff\xd8unchanged-preview-jpeg\xff\xd9'
    monkeypatch.setattr(ws_handler.cv2,'imdecode',lambda *a:(_ for _ in ()).throw(AssertionError('Preview decoded')))
    assert ws_handler._process_frame(jpeg,device)
    assert live_state.preview(device)==jpeg
    padded=jpeg+b'\x00'*34
    assert ws_handler._process_frame(padded,device)
    assert live_state.preview(device)==padded
    assert not ws_handler._process_frame(b'not-jpeg',device)
    live_state.forget(device);ws_handler._analysis_received.pop(device,None)
