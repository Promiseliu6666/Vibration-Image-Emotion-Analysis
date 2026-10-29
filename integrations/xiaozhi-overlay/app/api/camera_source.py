"""Raw Xiaozhi camera frames for the local vibration service. No analysis forwarding."""
import time,hmac
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import Response
from app.core.paths import RUNTIME_DIR
from app.core import live_state
from app.core.db import get_connection
router=APIRouter(prefix='/api/camera-source')
def check(r):
 if not r.client or r.client.host not in ('127.0.0.1','::1'):raise HTTPException(403,'仅允许本机摄像头接入')
 f=RUNTIME_DIR/'camera-bridge-secret.txt'
 if not f.exists() or not hmac.compare_digest(r.headers.get('X-Camera-Bridge-Key',''),f.read_text(encoding='utf-8').strip()):raise HTTPException(403,'摄像头接入认证失败')
def devices():
 c=get_connection()
 try:
  with c.cursor() as q:q.execute('SELECT device_id,name FROM devices ORDER BY created_at DESC');rows=q.fetchall()
 finally:c.close()
 return [{**r,'online':live_state.status(r['device_id'])['online']} for r in rows if not r['device_id'].startswith(('vibration-','sim-','test-','reproduction-','e2e-'))]
@router.get('/devices')
def list_devices(request:Request):check(request);return {'devices':devices()}
@router.get('/frame')
def frame(request:Request,device_id:str=''):
 check(request);rows=devices()
 if device_id:
  row=next((x for x in rows if x['device_id']==device_id),None)
  if not row:raise HTTPException(404,'小智摄像头不存在或不是物理设备')
 else:row=next((x for x in rows if x['online']),rows[0] if rows else None)
 if not row:raise HTTPException(503,'尚未连接小智摄像头，请在设备管理中接入')
 live=live_state.status(row['device_id']);stamp=live.get('last_received',0)
 jpeg=live_state.preview(row['device_id'])
 if not jpeg or time.time()-stamp>5:raise HTTPException(503,'小智摄像头暂无新画面，请在小智设备管理中启动采集')
 return Response(jpeg,media_type='image/jpeg',headers={'Cache-Control':'no-store','X-Captured-At':str(stamp),'X-Frame-Sequence':str(stamp),'X-Device-Id':row['device_id']})
