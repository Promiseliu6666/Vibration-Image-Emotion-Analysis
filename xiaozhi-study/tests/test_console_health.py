from app.api import console_health

def test_ui_snapshot_is_cached_but_commands_are_not(monkeypatch):
    calls=[]
    clock=[100.]
    monkeypatch.setattr(console_health.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(console_health.capture_control,'status',lambda:(calls.append(1) or {'running':True,'device_id':'real-a'}))
    monkeypatch.setattr(console_health,'_capture',None)
    monkeypatch.setattr(console_health,'_deadline',0)
    first=console_health.snapshot();first['device_id']='caller-mutation'
    assert console_health.snapshot()['device_id']=='real-a' and len(calls)==1
    console_health.capture_control.status()
    assert len(calls)==2
    console_health.invalidate();console_health.snapshot()
    assert len(calls)==3
    clock[0]+=2.1;console_health.snapshot()
    assert len(calls)==4

def test_quick_resume_rejects_changed_physical_device(monkeypatch):
    from types import SimpleNamespace
    from app.api import console_api
    from app.device import usb_identity
    from starlette.requests import Request
    from fastapi import HTTPException
    import pytest
    monkeypatch.setattr(usb_identity,'camera_ports',lambda:[SimpleNamespace(device='COM5',serial_number='NEW-PHYSICAL')])
    calls=[]
    monkeypatch.setattr(console_api.capture_control,'set_running',lambda *a,**kw:calls.append(1))
    request=Request({'type':'http','client':('127.0.0.1',1234)})
    with pytest.raises(HTTPException) as exc:
        console_api.capture('start',request,console_api.CaptureRequest(port='COM5',expected_usb_serial='OLD-PHYSICAL'))
    assert exc.value.status_code==409 and not calls
