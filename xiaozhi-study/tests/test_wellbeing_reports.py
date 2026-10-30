from datetime import datetime
import json
from app.api.wellbeing_reports import bounds,summarize

def row(**o):
    o.setdefault('eye_assessable',True)
    return {'timestamp':datetime(2026,10,12,1),'evidence_json':json.dumps({'observations':o})}
def test_old_data_and_unknown_posture_are_not_healthy_samples():
    r=summarize([row(posture_tilt=False),row(screen_activity=False,posture_assessable=False)])
    assert r['samples']==1 and r['posture_samples']==0 and r['tilted_pct'] is None

def test_ratios_use_different_valid_denominators():
    r=summarize([row(screen_activity=True,screen_seconds=120,posture_assessable=True,posture_tilt=True),row(screen_activity=False,posture_assessable=False)])
    assert r['screen_pct']==50 and r['tilted_pct']==100 and r['longest_screen_minutes']==2

def test_beijing_week_boundaries_and_leap_month():
    assert bounds('week','2024-02-29')==(datetime(2024,2,25,16),datetime(2024,3,3,16))
    assert bounds('month','2024-02-29')==(datetime(2024,1,31,16),datetime(2024,2,29,16))

def test_corrupt_legacy_json_does_not_break_report():
    assert summarize([{'timestamp':datetime.now(),'evidence_json':'bad'}])['samples']==0
