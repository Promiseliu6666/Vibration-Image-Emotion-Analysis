from datetime import date, datetime, timezone
from app.api.record_scope import session_candidates


def test_today_uses_shanghai_midnight_and_bound_session_count():
    sql, params = session_candidates('device-a', 'today', limit=100,
                                     now=datetime(2026, 10, 14, 16, 10, tzinfo=timezone.utc))
    assert params == ('device-a', datetime(2026, 10, 14, 16), datetime(2026, 10, 15, 16), 100)
    assert 'EXISTS' in sql and 'v.person_present=1' in sql
    assert sql.endswith('LIMIT %s')


def test_week_includes_seven_calendar_days():
    _, params = session_candidates('a', 'week', now=datetime(2026, 10, 15, 0, tzinfo=timezone.utc))
    assert params[1:3] == (datetime(2026, 10, 8, 16), datetime(2026, 10, 15, 16))


def test_selected_day_overrides_period_and_device_is_parameterized():
    sql, params = session_candidates("device' OR 1=1", 'week', date(2026, 10, 1), 50)
    assert "device' OR" not in sql
    assert params[1:3] == (datetime(2026, 9, 30, 16), datetime(2026, 10, 1, 16))


def test_recent_records_do_not_apply_an_accidental_date_filter():
    sql, params = session_candidates('device-a')
    assert params == ('device-a', 50)
    assert 'sx.start_time>=' not in sql


def test_live_and_analysis_timestamp_have_the_same_clock():
    from app.core import live_state
    device = 'test-shared-clock'
    live_state.received(device, b'jpeg', captured_at=1000)
    live_state.analyzed(device, {'captured_at': 1000, 'person_present': True, 'frame_id': 'f'})
    state = live_state.status(device, now=1003)
    assert state['analysis_age_seconds'] == 3
    assert state['last_received'] == state['result']['captured_at']
    live_state.forget(device)


def test_record_route_bounds_are_validated_before_database_access():
    from fastapi.testclient import TestClient
    from app.server import app
    from app.api.api_router import get_current_user
    app.dependency_overrides[get_current_user] = lambda: 'test'
    try:
        client = TestClient(app)
        for query in ('limit=501', 'limit=0', 'period=broken', 'day=not-a-date', 'day=9999-12-31'):
            assert client.get('/api/sessions?' + query).status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)
