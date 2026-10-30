import asyncio
import json
from datetime import datetime
import pytest
from fastapi import HTTPException
from app.api.wellbeing_reports import bounds, summarize
from app.analysis.agent import BehaviorBuffer
from app.analysis.eye_alerts import EyeAlerts


@pytest.mark.parametrize('duration', ['broken', float('nan'), float('inf'), [], -10])
def test_bad_duration_keeps_valid_report_samples(duration):
    rows=[dict(timestamp=datetime(2026,10,13),evidence_json=json.dumps({'observations':{
        'screen_activity':True,'eye_assessable':True,'screen_seconds':duration,'presence_seconds':duration}}))]
    report=summarize(rows)
    assert report['screen_samples']==1
    assert report['longest_screen_minutes']==report['longest_presence_minutes']==0
    json.dumps(report,allow_nan=False)


def test_malformed_observation_and_date_are_ignored():
    assert summarize([dict(timestamp=None,evidence_json={'observations':{'screen_activity':False}}),
                      dict(timestamp=datetime.now(),evidence_json={'observations':['screen_activity']})])['samples']==0


@pytest.mark.parametrize('anchor',['0001-01-01','9999-12-31'])
def test_report_extreme_dates_are_validation_errors(anchor):
    with pytest.raises(HTTPException) as exc:bounds('month',anchor)
    assert exc.value.status_code==422


def test_assistant_expires_old_records_even_when_no_new_frames(monkeypatch):
    import app.analysis.agent as agent
    clock=[100.0];monkeypatch.setattr(agent.time,'monotonic',lambda:clock[0])
    b=BehaviorBuffer(window_sec=60)
    b.push({'learning_state':'distracted_phone'})
    clock[0]=130;b.push({'learning_state':'engaged_reading'})
    assert b.get_summary()['duration_min']==.5
    clock[0]=160
    assert [r['state'] for r in b.get_snapshot()]==['engaged_reading']
    clock[0]=190
    assert b.get_snapshot()==[] and b.get_summary()['total_frames']==0


def test_late_eye_ack_does_not_delay_new_screen_run(monkeypatch):
    async def run():
        import app.analysis.eye_alerts as eye_alerts
        started=asyncio.Event();finish=asyncio.Event()
        async def playback(*args):
            started.set();await finish.wait();return ('played',None)
        monkeypatch.setattr(eye_alerts.asyncio,'to_thread',playback)
        monkeypatch.setattr(eye_alerts.time,'monotonic',lambda:1000)
        a=EyeAlerts()
        def sample(seconds):return {'record':{'result_id':1},'evidence':{'observations':{'screen_activity':True,'screen_seconds':seconds}}}
        a.observe('device',sample(1200));await started.wait()
        a.observe('device',sample(0));finish.set();await asyncio.gather(*list(a.tasks))
        assert a.devices['device']['next_seconds']==1200
        assert a.devices['device']['status']=='waiting' and not a.devices['device']['busy']
    asyncio.run(run())
