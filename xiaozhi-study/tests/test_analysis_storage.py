def test_record_commit_and_image_archive(monkeypatch):
    import ast
    import sys
    import tempfile
    from pathlib import Path
    from datetime import datetime,timezone
    import os
    import time
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));from app.core import config
    module=ast.parse((root/'app'/'analysis'/'analysis_storage.py').read_text(encoding='utf-8'));fn=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='write_result_unlocked')
    class Cursor:
     lastrowid=321
     def __enter__(self):return self
     def __exit__(self,*a):pass
     def execute(self,sql,args):
      if 'INSERT INTO analysis_results' in sql:self.insert=args
     def fetchone(self):return {'id':42,'start_time':datetime(2026,10,12,12,38)}
    class Connection:
     def __init__(self,fail=False):self.cur=Cursor();self.fail=fail;self.committed=False
     def cursor(self):return self.cur
     def commit(self):
      if self.fail:raise RuntimeError('Simulated database failure')
      self.committed=True
     def close(self):pass
    ns={'os':os,'datetime':datetime,'timezone':timezone,'_time':time,'_absence_state':{}}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<writer-regression>','exec'),ns)
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
     monkeypatch.setattr(config,'FRAME_SAVE_DIR',folder)
     frame=Path(folder)/'2026-10-12'/'phone.jpg';frame.parent.mkdir();frame.write_bytes(b'original-phone-jpeg')
     result=dict(captured_at=datetime(2026,10,12,12,40,tzinfo=timezone.utc).timestamp(),person_present=True,learning_state='distracted_phone',fatigue_level=0,distraction_level=.7,difficulty_indicator=0,gaze_direction='down',action_state='playing_phone',evidence={})
     conn=Connection();ns['get_connection']=lambda:conn
     receipt=ns['write_result_unlocked']('device',result,str(frame))
     assert conn.committed and receipt['session_id']==42 and receipt['result_id']==321
     assert Path(receipt['frame_path']).read_bytes()==b'original-phone-jpeg'
     assert conn.cur.insert[6]=='distracted_phone' and conn.cur.insert[8]==receipt['frame_path']
     ns['get_connection']=lambda:Connection(True)
     try:ns['write_result_unlocked']('device',result,str(frame))
     except RuntimeError:pass
     else:raise AssertionError('Database failure returned success')
     print('PASS: phone record and original archive committed together; save failure cannot return a success receipt')
