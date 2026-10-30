from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from app.api import study_api

def test_gaze_alone_is_not_proof_of_learning():
    from app.analysis import analyzer
    assert analyzer.calc_learning_state('unknown-gaze','idle','screen',0)=='thinking'

def test_review_requires_matching_real_image(monkeypatch):
    monkeypatch.setattr(study_api.live_state,'status',lambda d:{'result':{'frame_id':'new'}})
    monkeypatch.setattr(study_api.live_state,'preview',lambda *args:None)
    with pytest.raises(HTTPException) as e:study_api.review_frame('device','old','user')
    assert e.value.status_code==409

def test_review_freezes_original_result_when_live_changes(monkeypatch):
    result={'frame_id':'same','learning_state':'thinking','evidence':{'source':'original'}}
    monkeypatch.setattr(study_api.live_state,'status',lambda d:{'result':result})
    monkeypatch.setattr(study_api.live_state,'preview',lambda *args:b'jpeg')
    item=study_api.review_frame('device','same','user')
    result['learning_state']='distracted_phone'
    assert study_api.REVIEWS[('user','device','same')]['result']['learning_state']=='thinking'
    assert item['image_url'].startswith('data:image/jpeg;base64,')
    assert ('another-user','device','same') not in study_api.REVIEWS

def test_keyboard_evidence_is_not_phone_evidence():
    from app.analysis.phone_detector import held_by_person
    pose=NS(pose_landmarks=NS(landmark=[NS(x=.5,y=.5,visibility=1) for _ in range(33)]))
    detections={'boxes':[],'objects':[{'kind':'keyboard','box':[.4,.4,.6,.6]}]}
    assert not held_by_person(detections,pose)
