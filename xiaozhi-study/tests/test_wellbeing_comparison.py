from datetime import datetime, timedelta
from app.api.wellbeing_reports import comparison_bounds, change, summarize


def test_current_week_compares_equal_elapsed_observation_window():
    start=datetime(2026,10,11,16)
    end=start+timedelta(days=7)
    now=start+timedelta(days=1,hours=9)
    left,right=comparison_bounds(start,end,'week',now)
    assert left==start-timedelta(days=7)
    assert right-left==now-start


def test_leap_month_and_short_previous_month_are_bounded():
    start=datetime(2024,2,29,16) # March local calendar start
    end=datetime(2024,3,31,16)
    left,right=comparison_bounds(start,end,'month',end)
    assert left==datetime(2024,1,31,16)
    assert right==start


def test_no_prior_evidence_produces_no_change():
    assert change(40,None) is None
    assert change(None,40) is None
    assert change(12.3,15.8)==-3.5


def test_beijing_daily_totals_keep_non_assessable_samples_separate():
    r=summarize([{'timestamp':datetime(2026,10,12,16,1),'evidence_json':{'observations':{'screen_activity':True,'eye_assessable':False,'posture_assessable':False}}}])
    assert r['days'][0]['date']=='10-13'
    assert r['samples']==1 and r['screen_pct'] is None and r['tilted_pct'] is None
