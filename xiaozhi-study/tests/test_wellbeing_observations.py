from types import SimpleNamespace as NS
import numpy as np
from app.analysis.study_observations import observe
FRAME=np.random.default_rng(5).integers(0,180,(80,80,3),dtype=np.uint8)
FACE=NS(multi_face_landmarks=[1]);POSE=NS(pose_landmarks=None)
def run(state,t,label='engaged_computer',present=True,gaze='screen'):
    return observe(FRAME,POSE,FACE,present,gaze,t,state,label)

def test_screen_exposure_follows_gaze_not_state_label():
    """屏幕暴露只看视线与画面可用性，不再要求"状态已确认成电脑/手机"。

    原因：状态分类要过连续确认，长期可能停在"活动未确认"；若把用眼时长挂在它上面，
    累积量会一直是 0。改用视线判定后，无论标签是否确认，都能得到真实的用眼时长。
    """
    s={};run(s,0);assert run(s,2)['screen_seconds']==2
    assert run(s,4,'engaged_screen')['screen_seconds']==4      # 标签不同也照常累积
    assert run(s,6,'thinking')['screen_activity'] is True      # 未确认标签同样计入

def test_near_work_covers_reading_and_screen():
    s={};run(s,0,gaze='down');assert run(s,2,gaze='down')['near_work_seconds']==2
    assert run(s,4,gaze='down')['screen_seconds']==0           # 低头看书算近距离用眼，不算屏幕暴露
    run(s,6,gaze='screen')
    assert run(s,8,gaze='screen')['screen_seconds']==2         # 连续两帧朝屏幕才开始累计

def test_away_gaze_does_not_accumulate():
    s={};run(s,0,gaze='away');assert run(s,2,gaze='away')['near_work_seconds']==0
    assert run(s,4,gaze='away')['screen_seconds']==0

def test_gap_and_absence_reset_run_without_counting_gap():
    s={};run(s,0);run(s,2);assert run(s,10)['screen_seconds']==0
    run(s,12);assert run(s,14,present=False)['screen_seconds']==0

def test_duplicate_cannot_increase_or_reset_evidence():
    s={};run(s,0);a=run(s,2);assert run(s,2)==a
    assert run(s,1)==a

def test_body_not_visible_is_unknown_not_normal():
    assert run({},1)['posture_assessable'] is False
    assert run({},1)['posture_reason']

def test_short_glance_pauses_but_sustained_break_resets():
    s={};run(s,0);run(s,2)
    assert run(s,4,gaze='away')['screen_seconds']==2       # 短暂移开：暂停但不清零
    assert run(s,6)['screen_seconds']==2
    assert run(s,8)['screen_seconds']==4                   # 回到屏幕：继续累积
    for t in range(10,31,2):r=run(s,t,gaze='away')         # 持续离开 20 秒 → 清零
    assert r['screen_seconds']==0

def test_posture_assessable_when_keypoints_only_barely_visible():
    """关键点可见度 0.7：旧门槛 0.75 会判不可评估，新门槛 0.60 应可评估。"""
    def lm(x,y,v):return NS(x=x,y=y,z=0.0,visibility=v)
    pts=[lm(0.5,0.5,0.7) for _ in range(33)]
    pts[11]=lm(0.42,0.50,0.7);pts[12]=lm(0.58,0.52,0.7)
    pts[23]=lm(0.45,0.75,0.7);pts[24]=lm(0.55,0.75,0.7)
    pose=NS(pose_landmarks=NS(landmark=pts))
    s={}
    observe(FRAME,pose,FACE,True,'screen',0,s,'thinking')
    o=observe(FRAME,pose,FACE,True,'screen',2,s,'thinking')
    assert o['posture_assessable'] is True and o['posture_reason'] is None
