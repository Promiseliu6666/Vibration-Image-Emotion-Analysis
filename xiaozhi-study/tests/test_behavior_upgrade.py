import numpy as np
from types import SimpleNamespace as NS
from app.analysis.cbph_inference import _infer_ort
from app.analysis.study_observations import observe
from app.analysis.temporal_analysis import TemporalAnalysis

class Session:
    def get_inputs(self):return [NS(name='images')]
    def run(self,outputs,inputs):
        result=np.zeros((1,12,2100),np.float32)
        result[0,:4,0]=[160,160,120,160]
        result[0,4+0,0]=.85
        result[0,:4,1]=[162,160,120,160]
        result[0,4+1,1]=.6
        return [result]

def test_exported_pixel_boxes_and_new_class_survive_nms():
    action,conf=_infer_ort(Session(),np.zeros((240,320,3),np.uint8),.5)
    assert action=='hand_raising' and conf>.8

def test_new_behaviors_need_current_continuous_evidence():
    t=TemporalAnalysis()
    for state in ('engaged_hand_raising','engaged_discussing','standing'):
        assert t.update(state,state,0)[0]=='thinking'
        assert t.update(state,state,1)[0]=='thinking'
        assert t.update(state,state,2)[0]==state
        assert t.update(state,'engaged_reading',3)[0]=='thinking'

def test_break_clock_stops_on_absence_or_capture_gap():
    image=np.zeros((120,160,3),np.uint8);state={};pose=NS(pose_landmarks=None);face=NS(multi_face_landmarks=None)
    for now in (0,2,4):result=observe(image,pose,face,True,'screen',now,state,'engaged_screen')
    assert result['focus_seconds']==4
    result=observe(image,pose,face,False,'screen',6,state,'absent');assert result['focus_seconds']==0
    observe(image,pose,face,True,'screen',8,state,'engaged_screen')
    result=observe(image,pose,face,True,'screen',40,state,'engaged_screen');assert result['focus_seconds']==0

def test_invisible_shoulders_never_create_posture_alert():
    image=np.zeros((120,160,3),np.uint8);points=[NS(x=.5,y=.5,visibility=.1) for _ in range(33)]
    points[11].x=.3;points[12].x=.7;points[12].y=.8
    state={};pose=NS(pose_landmarks=NS(landmark=points));face=NS(multi_face_landmarks=None)
    for now in (0,2,4,6):result=observe(image,pose,face,True,'screen',now,state,'engaged_screen')
    assert not result['posture_tilt']

def test_ambiguous_reading_writing_is_not_forced():
    class Ambiguous(Session):
        def run(self,outputs,inputs):
            result=super().run(outputs,inputs)[0]
            result[:]=0
            result[0,:4,0]=[160,160,120,160]
            result[0,5,0]=.72;result[0,6,0]=.7
            return [result]
    assert _infer_ort(Ambiguous(),np.zeros((240,320,3),np.uint8),.5)==(None,0.)

def test_state_file_lock_does_not_raise_camera_error(tmp_path,monkeypatch):
    from app.device import usb_identity
    from pathlib import Path
    monkeypatch.setattr(usb_identity,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(Path,'replace',lambda *args:(_ for _ in ()).throw(PermissionError('locked')))
    assert usb_identity.write_state({'connected':True}) is False
    assert not list(tmp_path.glob('*.tmp'))

def test_observed_near_work_reaches_break_threshold():
    """break_due 现在按"连续近距离用眼"计，不再按分类派生的 focus_seconds。

    这里故意传入未确认标签 thinking，用来证明该指标与状态分类无关。
    """
    rng=np.random.default_rng(3)
    image=rng.integers(0,180,(20,20,3),dtype=np.uint8)
    state={};pose=NS(pose_landmarks=None);face=NS(multi_face_landmarks=[1])
    for now in range(0,2701,2):
        result=observe(image,pose,face,True,'screen',now,state,'thinking')
    assert result['near_work_seconds']==2700 and result['break_due']
