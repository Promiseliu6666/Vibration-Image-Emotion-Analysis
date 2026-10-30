import asyncio
from types import SimpleNamespace as NS
import numpy as np
from app.analysis.temporal_analysis import TemporalAnalysis
from app.analysis.phone_detector import held_by_person, detect
from app.core.latest_frames import LatestFrames
from app.core import live_state

def test_phone_requires_continuous_current_evidence():
    t=TemporalAnalysis()
    assert t.update('a','distracted_phone',0)[0]=='thinking'
    assert t.update('a','distracted_phone',1)[0]=='thinking'
    assert t.update('a','distracted_phone',2)[0]=='distracted_phone'
    assert t.update('a','engaged_screen',3)[0]=='thinking'
    assert t.update('a','distracted_phone',4)[0]=='thinking'
    assert t.update('b','distracted_phone',5)[0]=='thinking'
    assert t.update('a','distracted_phone',10)[0]=='thinking'
    assert t.update('a','distracted_phone',11,present=False)[0]=='absent'

def test_hand_near_face_without_phone_is_not_phone():
    lm=[NS(x=.5,y=.5,visibility=1.) for _ in range(33)]
    pose=NS(pose_landmarks=NS(landmark=lm))
    assert not held_by_person({'boxes':[]},pose)
    assert held_by_person({'boxes':[{'box':[.45,.45,.55,.55]}]},pose)
    for i in (15,16,19,20):lm[i].visibility=.1
    assert not held_by_person({'boxes':[{'box':[.45,.45,.55,.55]}]},pose)

def test_table_phone_without_hand_interaction():
    lm=[NS(x=.1,y=.1,visibility=1.) for _ in range(33)]
    pose=NS(pose_landmarks=NS(landmark=lm))
    assert not held_by_person({'boxes':[{'box':[.7,.7,.85,.85]}]},pose)

def test_exact_analyzed_preview_separate_from_current_camera():
    live_state.forget('pair')
    live_state.received('pair',b'camera-new')
    live_state.analyzed('pair',{'frame_id':'old-id','preview_jpeg':b'analyzed-old','person_present':True})
    live_state.analyzed('pair',{'frame_id':'new-id','preview_jpeg':b'analyzed-new','person_present':True})
    assert live_state.preview('pair')==b'camera-new'
    assert live_state.preview('pair',True,'old-id')==b'analyzed-old'
    assert live_state.preview('pair',True,'new-id')==b'analyzed-new'
    assert live_state.preview('pair',True,'missing') is None
    assert 'analysis_previews' not in live_state.status('pair')
    live_state.forget('pair')

def test_newest_waiting_frame_keeps_other_device_and_cleans_old_file(tmp_path):
    async def run():
        q=LatestFrames(3)
        path=tmp_path/'old.jpg';path.write_bytes(b'old')
        q.put_nowait({'device_id':'a','filepath':str(path),'frame_id':'old'})
        q.put_nowait({'device_id':'b','filepath':'','frame_id':'other'})
        q.put_nowait({'device_id':'a','filepath':'','frame_id':'new'})
        assert not path.exists() and q.qsize()==2
        assert (await q.get())['frame_id']=='other';q.task_done()
        assert (await q.get())['frame_id']=='new';q.task_done()
        await asyncio.wait_for(q.join(),.1)
    asyncio.run(run())

def test_real_model_blank_frame_has_no_phone():
    result=detect(np.zeros((240,320,3),dtype=np.uint8))
    assert result['available'] and not result['boxes']

def test_invisible_pose_cannot_be_resting_or_phone():
    from app.analysis.analyzer import _legacy_action_state
    points=[NS(x=.5,y=.5,visibility=.1) for _ in range(33)]
    result=_legacy_action_state(NS(pose_landmarks=NS(landmark=points)))
    assert result[0]=='idle'

def test_no_face_cannot_reuse_old_fatigue_or_phone(monkeypatch):
    from app.analysis import analyzer
    monkeypatch.setattr(analyzer, 'cbph_ready', lambda:False)
    monkeypatch.setattr(analyzer.face_mesh, 'process', lambda rgb:NS(multi_face_landmarks=None))
    monkeypatch.setattr(analyzer.pose_model, 'process', lambda rgb:NS(pose_landmarks=None))
    state=analyzer._get_state('absence-regression')
    state['smoothed_fatigue']=.95
    state['prev_learning_state']='distracted_phone'
    result=analyzer.analyze_frame('absence-regression',np.zeros((240,320,3),dtype=np.uint8))
    assert result['learning_state']=='absent' and not result['person_present']
    assert result['fatigue_level']==0 and result['distraction_level']==0

def test_fatigue_requires_personal_baseline(monkeypatch):
    from app.analysis import analyzer
    from app.analysis import phone_detector
    monkeypatch.setattr(phone_detector,'detect',lambda image:{'available':True,'boxes':[]})
    monkeypatch.setattr(analyzer,'cbph_ready',lambda:False)
    monkeypatch.setattr(analyzer.face_mesh,'process',lambda rgb:NS(multi_face_landmarks=[object()]))
    monkeypatch.setattr(analyzer.pose_model,'process',lambda rgb:NS(pose_landmarks=None))
    monkeypatch.setattr(analyzer,'calc_gaze_direction',lambda *a:'screen')
    monkeypatch.setattr(analyzer,'calc_distraction',lambda *a:0.)
    monkeypatch.setattr(analyzer,'calc_fatigue',lambda *a,**k:{'fatigue_level':.9,'fatigue_sub':{}})
    device='calibration-regression';state=analyzer._get_state(device)
    state['ear_baseline']=None
    image=np.zeros((240,320,3),dtype=np.uint8)
    before=analyzer.analyze_frame(device,image,captured_at=10)
    assert before['fatigue_level']==0 and not before['evidence']['fatigue_calibrated']
    state['ear_baseline']=.3
    for time in (11,12,13):after=analyzer.analyze_frame(device,image,captured_at=time)
    assert after['learning_state']=='fatigued' and after['fatigue_level']==.9


def test_slow_analysis_can_confirm_but_never_carries_phone_forward():
    t=TemporalAnalysis()
    assert t.update('slow','distracted_phone',0)[0]=='thinking'
    assert t.update('slow','distracted_phone',3.5)[0]=='thinking'
    assert t.update('slow','distracted_phone',7)[0]=='distracted_phone'
    assert t.update('slow','engaged_computer',10.5)[0]=='thinking'
    assert t.update('slow','distracted_phone',20)[0]=='thinking'

def test_repeated_timestamp_is_not_new_phone_evidence():
    t=TemporalAnalysis()
    for _ in range(4):
        assert t.update('duplicate','distracted_phone',1)[0]=='thinking'

def test_hand_crop_boxes_map_back_and_need_visible_hand(monkeypatch):
    from app.analysis import phone_detector
    lm=[NS(x=.5,y=.6,visibility=0.) for _ in range(33)]
    lm[15].visibility=1
    pose=NS(pose_landmarks=NS(landmark=lm))
    monkeypatch.setattr(phone_detector,'detect',lambda frame,phone_threshold=.55:{'boxes':[{'box':[.4,.45,.6,.75],'confidence':.45}]})
    r=phone_detector.refine_hands(np.zeros((480,640,3),np.uint8),{'boxes':[]},pose)
    assert len(r['boxes'])==1 and r['hand_crops']==1
    assert all(0<=n<=1 for n in r['boxes'][0]['box'])
    lm[15].visibility=.1
    assert not phone_detector.refine_hands(np.zeros((480,640,3),np.uint8),{'boxes':[]},pose)['boxes']


def test_keyboard_near_wrist_is_not_keyboard_interaction():
    from app.analysis.phone_detector import touches_learning_object
    points=[NS(x=.1,y=.1,visibility=1.) for _ in range(33)]
    points[15].x=.5;points[15].y=.5
    pose=NS(pose_landmarks=NS(landmark=points))
    keyboard=[{'box':[.4,.4,.7,.7]}]
    assert not touches_learning_object(keyboard,pose)
    points[19].x=.5;points[19].y=.5
    assert touches_learning_object(keyboard,pose)

def test_background_person_hand_cannot_trigger_main_person_phone():
    points=[NS(x=.8,y=.8,visibility=1.) for _ in range(33)]
    pose=NS(pose_landmarks=NS(landmark=points))
    detections={'boxes':[{'box':[.75,.75,.9,.9]}],'people':[{'box':[.1,.1,.65,.9]},{'box':[.75,.7,.95,.95]}]}
    assert not held_by_person(detections,pose)

def test_ordinary_study_confirms_faster_without_alert_relaxation():
    t=TemporalAnalysis()
    assert t.update('study','engaged_reading',0)[0]=='thinking'
    assert t.update('study','engaged_reading',2)[0]=='engaged_reading'
    assert t.update('study','distracted_phone',4)[0]=='thinking'
    assert t.update('study','distracted_phone',6)[0]=='thinking'
    assert t.update('study','distracted_phone',8)[0]=='distracted_phone'


def test_duplicate_and_invalid_phone_boxes_do_not_accumulate():
    from app.analysis.phone_detector import merge_phone_boxes
    boxes=[{'box':[.1,.1,.3,.4],'confidence':.8},{'box':[.11,.1,.31,.4],'confidence':.5},{'box':[float('nan'),0,.5,.5],'confidence':.9}]
    assert merge_phone_boxes(boxes)==boxes[:1]

def test_hand_crop_failure_preserves_other_evidence(monkeypatch):
    from app.analysis import phone_detector
    points=[NS(x=.5,y=.6,visibility=0.) for _ in range(33)];points[15].visibility=1
    pose=NS(pose_landmarks=NS(landmark=points))
    monkeypatch.setattr(phone_detector,'detect',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('model unavailable')))
    source={'boxes':[],'objects':[{'kind':'book'}],'available':True}
    result=phone_detector.refine_hands(np.zeros((480,640,3),np.uint8),source,pose)
    assert result['objects']==source['objects'] and result['hand_crop_error']=='RuntimeError'
