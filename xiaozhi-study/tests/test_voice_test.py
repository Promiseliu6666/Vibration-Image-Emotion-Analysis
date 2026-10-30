import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import console_api
from app.analysis import phone_alerts


def local_request():
    return SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'),query_params={})


def test_voice_test_plays_without_recording_a_phone_event(monkeypatch):
    monkeypatch.setattr(console_api.capture_control, 'status',
                        lambda: {'running': True, 'device_id': 'device-a'})
    monkeypatch.setattr(phone_alerts, 'play_test_usb', lambda device, kind: ('played', None))
    result = asyncio.run(console_api.voice_test('device-a', local_request()))
    assert result['status'] == 'played'
    assert '已播放完成' in result['message']


def test_voice_test_requires_local_usb_session(monkeypatch):
    remote = SimpleNamespace(client=SimpleNamespace(host='10.0.0.8'),query_params={})
    with pytest.raises(HTTPException) as error:
        asyncio.run(console_api.voice_test('device-a', remote))
    assert error.value.status_code == 403

    monkeypatch.setattr(console_api.capture_control, 'status',
                        lambda: {'running': True, 'device_id': 'device-b'})
    with pytest.raises(HTTPException) as error:
        asyncio.run(console_api.voice_test('device-a', local_request()))
    assert error.value.status_code == 409


def test_voice_test_reports_speaker_failure(monkeypatch):
    monkeypatch.setattr(console_api.capture_control, 'status',
                        lambda: {'running': True, 'device_id': 'device-a'})
    monkeypatch.setattr(phone_alerts, 'play_test_usb', lambda device, kind: ('muted', '小智当前静音'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(console_api.voice_test('device-a', local_request()))
    assert error.value.status_code == 409
    assert error.value.detail == '小智当前静音'


def test_voice_test_rejects_unknown_reminder_kind():
    request = local_request()
    request.query_params = {'kind': 'unknown'}
    with pytest.raises(HTTPException) as error:
        asyncio.run(console_api.voice_test('device-a', request))
    assert error.value.status_code == 400
