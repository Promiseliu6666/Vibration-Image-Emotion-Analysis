"""Shared vibration camera sources feed the existing Xiaozhi analysis queue."""
import asyncio,time
from pathlib import Path
import httpx
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from typing import Literal
from app.api.api_router import get_current_user,require_admin
from app.core.paths import RUNTIME_DIR
from app.core import live_state
router=APIRouter(prefix='/api/console/camera-bridge',dependencies=[Depends(get_current_user)])
states={};tasks={}
class SourceRequest(BaseModel):source:Literal['local','rtsp']='local'
def snapshot():
    return {k:{**v,'online':bool(v.get('last_frame_at') and time.time()-v['last_frame_at']<10)} for k,v in states.items()}
async def pump(source):
    device='vibration-'+source;last=None
    secret=(RUNTIME_DIR/'camera-bridge-secret.txt').read_text(encoding='utf-8').strip()
    try:
        async with httpx.AsyncClient(trust_env=False,timeout=9) as client:
            while True:
                try:
                    response=await client.get('http://127.0.0.1:9099/video/shared/frame',params={'source':source},headers={'X-Camera-Bridge-Key':secret})
                    if response.status_code==503:raise ValueError('摄像头未返回画面，请检查摄像头连接')
                    response.raise_for_status()
                    seq=response.headers.get('X-Frame-Sequence');captured=float(response.headers.get('X-Captured-At','0'))
                    if not captured or time.time()-captured>5:raise ValueError('视频画面已过期，正在等待新画面')
                    if seq!=last:
                        from app.api.ws_handler import _process_frame
                        if not _process_frame(response.content,device,link='shared-camera'):raise ValueError('画面解码失败或分析队列暂满')
                        last=seq;states[source].update(last_frame_at=captured,error=None,received=states[source]['received']+1)
                except asyncio.CancelledError:raise
                except Exception as e:
                    states[source]['error']=str(e) if isinstance(e,ValueError) else '共享摄像头连接中断，正在重试'
                await asyncio.sleep(.5)
    finally:states[source]['running']=False
@router.get('')
async def status():return snapshot()
@router.post('/start',dependencies=[Depends(require_admin)])
async def start(body:SourceRequest):
    source=body.source;device='vibration-'+source
    if not (RUNTIME_DIR/'camera-bridge-secret.txt').exists():raise HTTPException(503,'共享摄像头接入尚未配置')
    if source in tasks and not tasks[source].done():return {'device_id':device,'state':snapshot()[source]}
    from app.api.ws_handler import _ensure_device
    from app.core.db import get_connection
    await asyncio.to_thread(_ensure_device,device)
    def name_device():
        c=get_connection()
        try:
            with c.cursor() as q:q.execute('UPDATE devices SET name=%s WHERE device_id=%s',('共享摄像头 · '+('本地' if source=='local' else '海康 RTSP'),device))
            c.commit()
        finally:c.close()
    await asyncio.to_thread(name_device)
    states[source]={'device_id':device,'running':True,'received':0,'last_frame_at':None,'error':'正在连接摄像头'}
    tasks[source]=asyncio.create_task(pump(source))
    return {'device_id':device,'state':snapshot()[source]}
@router.post('/stop',dependencies=[Depends(require_admin)])
async def stop(body:SourceRequest):
    task=tasks.pop(body.source,None)
    if task:
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
    if body.source in states:states[body.source]['running']=False
    live_state.forget('vibration-'+body.source)
    return {'ok':True}
async def shutdown():
    pending=list(tasks.values())
    for task in pending:task.cancel()
    await asyncio.gather(*pending,return_exceptions=True)
    tasks.clear()
