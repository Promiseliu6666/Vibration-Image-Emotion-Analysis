import pytest
from app.core import wireless_setup, db


def test_new_mac_is_never_mapped_to_an_unrelated_single_device(monkeypatch):
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,sql,args=()):
            assert 'ORDER BY created_at' not in sql
            self.sql=sql
            if sql.startswith('INSERT INTO devices'):self.created=args[0]
        def fetchone(self):return None
    cur=Cursor()
    class Connection:
        def cursor(self):return cur
        def commit(self):pass
        def close(self):pass
    monkeypatch.setattr(db,'get_connection',lambda:Connection())
    device,key=wireless_setup.register('AA:BB:CC:DD:EE:01','新设备')
    assert device=='watcher-AABBCCDDEE01' and cur.created==device and key


@pytest.mark.parametrize('mac',['','00:00:00:00:00:00','not-a-device'])
def test_invalid_physical_identity_stops_before_registration(mac):
    with pytest.raises(RuntimeError):wireless_setup.register(mac,'新设备')
