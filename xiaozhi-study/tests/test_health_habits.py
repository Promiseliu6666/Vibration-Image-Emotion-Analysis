from types import SimpleNamespace as NS
import numpy as np
import pytest
from pydantic import ValidationError
from app.api.health_api import Preferences,ReminderSettings,Action
from app.analysis.study_observations import observe

def test_preferences_have_personal_validated_limits():
    assert Preferences().break_minutes==45
    with pytest.raises(ValidationError):Preferences(break_minutes=1)
    with pytest.raises(ValidationError):Action(device_id='device',kind='diagnosis',response='done')

def test_device_reminder_settings_default_to_all_categories():
    settings=ReminderSettings(device_id='device-a')
    assert settings.reminders_enabled
    assert settings.phone_enabled and settings.eye_enabled and settings.fatigue_enabled
    assert settings.away_enabled and settings.quality_enabled and settings.posture_enabled
    assert settings.lying_enabled and settings.eye_interval_minutes==20
    assert settings.phone_trigger_seconds==4 and settings.eye_trigger_minutes==20
    assert settings.break_minutes==settings.break_repeat_minutes==45
    assert settings.break_minutes==45
    unrestricted=ReminderSettings(device_id='device-a',break_minutes=999,
                                   break_repeat_minutes=1,eye_interval_minutes=1,
                                   phone_trigger_seconds=1)
    assert unrestricted.break_minutes==999 and unrestricted.eye_interval_minutes==1
    with pytest.raises(ValidationError):ReminderSettings(device_id='device-a',phone_trigger_seconds=0)

def test_reminder_settings_are_saved_for_the_selected_device(monkeypatch):
    from app.api import health_api
    calls=[]
    class Cursor:
        sql=''
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,sql,args):self.sql=sql;calls.append((sql,args))
        def fetchone(self):return {'device_id':'device-a'}
    class Connection:
        def cursor(self):return Cursor()
        def commit(self):pass
        def close(self):pass
    monkeypatch.setattr(health_api,'get_connection',lambda:Connection())
    body=ReminderSettings(device_id='device-a',reminders_enabled=False,phone_enabled=False,
                          eye_enabled=True,break_enabled=False,posture_enabled=True,
                          fatigue_enabled=False,away_enabled=True,quality_enabled=False,
                          lying_enabled=False,break_minutes=30,eye_interval_minutes=35)
    saved=health_api.save_reminder_settings(body,username='alice')
    insert=next(args for sql,args in calls if 'INSERT INTO device_reminder_preferences' in sql)
    assert saved==body.model_dump()
    assert insert[:2]==('device-a','alice')
    assert insert[2]==False and insert[-1]==30
    assert 35 in insert

def test_presence_observation_does_not_require_confirmed_learning():
    state={};image=np.zeros((50,50,3),np.uint8);pose=NS(pose_landmarks=None);face=NS(multi_face_landmarks=None)
    for now in (0,2,4):r=observe(image,pose,face,True,'unknown',now,state,'thinking')
    assert r['presence_seconds']==4 and r['focus_seconds']==0
    assert observe(image,pose,face,False,'unknown',6,state,'absent')['presence_seconds']==0
    observe(image,pose,face,True,'unknown',8,state,'thinking')
    assert observe(image,pose,face,True,'unknown',30,state,'thinking')['presence_seconds']==0


def test_new_presence_segment_gets_new_reminder_anchor():
    state={};image=np.zeros((50,50,3),np.uint8);pose=NS(pose_landmarks=None);face=NS(multi_face_landmarks=None)
    first=observe(image,pose,face,True,'unknown',10,state,'thinking')
    next_frame=observe(image,pose,face,True,'unknown',12,state,'thinking')
    assert first['presence_started_at']==next_frame['presence_started_at']==10
    reset=observe(image,pose,face,True,'unknown',30,state,'thinking')
    assert reset['presence_started_at']==30 and reset['presence_seconds']==0


def test_feedback_duplicate_is_serialized_and_lock_released(monkeypatch):
    from app.api import health_api
    calls=[]
    class Cursor:
        sql=''
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,sql,args):self.sql=sql;calls.append((sql,args))
        def fetchone(self):return {'locked':1} if 'GET_LOCK' in self.sql else {'id':42}
    class Connection:
        closed=False
        def cursor(self):return Cursor()
        def commit(self):pass
        def close(self):self.closed=True
    c=Connection();monkeypatch.setattr(health_api,'get_connection',lambda:c)
    assert health_api.record_action(health_api.Action(device_id='device-a',kind='break',response='done'),username='alice')['saved']
    assert not any('INSERT INTO health_actions' in sql for sql,args in calls)
    assert any('RELEASE_LOCK' in sql for sql,args in calls) and c.closed
    assert next(args for sql,args in calls if 'SELECT id FROM health_actions' in sql)[0]=='alice'
