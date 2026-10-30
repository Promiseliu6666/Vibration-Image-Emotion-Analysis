from datetime import datetime,timedelta
import pytest
from pydantic import ValidationError
from app.api import health_api
from app.analysis import rest_reminder

ROW={'id':7,'device_id':'dev','minutes':20,'started_at':datetime(2026,10,14,10,0,0),'status':'running','reminded_at':None,'remind_status':None,'remind_error':None}

def test_window_view_counts_down_from_server_deadline():
    view=health_api.window_view(ROW,datetime(2026,10,14,10,5,0))
    assert view['remaining_seconds']==900
    assert view['status']=='running' and view['reminded'] is False
    assert view['deadline_utc'].startswith('2026-10-14T10:20')
    assert health_api.window_view(ROW,datetime(2026,10,14,12,0,0))['remaining_seconds']==0

def test_window_view_of_missing_row():
    assert health_api.window_view(None) is None

def test_marked_reminder_is_reported():
    row=dict(ROW,status='done',reminded_at=datetime(2026,10,14,10,20,0),remind_status='played')
    view=health_api.window_view(row,datetime(2026,10,14,10,21,0))
    assert view['reminded'] is True and view['status']=='done'
    assert view['reminder_status']=='played'

def test_window_minutes_stay_within_10_to_90():
    with pytest.raises(ValidationError):health_api.WindowStart(device_id='dev',minutes=5)
    with pytest.raises(ValidationError):health_api.WindowStart(device_id='dev',minutes=120)
    assert health_api.WindowStart(device_id='dev',minutes=25).minutes==25

def test_rest_prompt_is_a_habit_action_not_a_diagnosis():
    assert '休息' in health_api.REST_ACTION_TEXT
    assert rest_reminder.VOICE_COMMAND=='study_eye_alert'
    assert rest_reminder.POLL_SECONDS>0
