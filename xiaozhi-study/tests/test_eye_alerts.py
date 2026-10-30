import asyncio
from app.analysis.eye_alerts import EyeAlerts

def sample(seconds=1200,record=True,screen=True):return dict(record={'result_id':1} if record else None,evidence={'observations':dict(screen_seconds=seconds,screen_activity=screen)})
def test_never_speaks_without_commit_fresh_screen_evidence():
    a=EyeAlerts()
    for r,f in [(sample(record=False),True),(sample(screen=False),True),(sample(),False)]:
        a.observe('device',r,fresh=f)
    assert not a.tasks

def test_disabled_eye_reminder_never_starts_playback():
    a=EyeAlerts()
    result=a.observe('device',sample(),enabled=False)
    assert result['status']=='disabled'
    assert not a.tasks

def test_eye_reminder_uses_configured_interval(monkeypatch):
    async def run():
        from app.analysis import eye_alerts
        monkeypatch.setattr(eye_alerts,'play_usb',lambda *args:('played',None))
        a=EyeAlerts();a.observe('one',sample(1800),interval_seconds=30*60)
        await asyncio.gather(*list(a.tasks))
        assert a.devices['one']['next_seconds']==1800+1800
    asyncio.run(run())

def test_acknowledgment_not_candidate_controls_next_reminder(monkeypatch):
    async def run():
        from app.analysis import eye_alerts
        monkeypatch.setattr(eye_alerts,'play_usb',lambda *args:('played',None))
        a=EyeAlerts();a.observe('one',sample());await asyncio.gather(*list(a.tasks))
        assert a.devices['one']['next_seconds']==2400
        a.observe('one',sample(1202));assert not a.devices['one']['busy']
        a.observe('one',sample(0));assert a.devices['one']['next_seconds']==1200
    asyncio.run(run())
