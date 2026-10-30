"""Authenticated LAN JPEG/heartbeat API, including Xiaozhi camera Explain protocol."""
import asyncio
import re
import time
import uuid
from collections import OrderedDict
from email.parser import BytesParser
from email.policy import default
from fastapi import APIRouter,Request,HTTPException
from app.core import access_control
from app.core import live_state

router=APIRouter()
_times=OrderedDict()
MAX_BODY=4*1024*1024

def identity(request):
    authorization=request.headers.get('authorization','')
    if not authorization.startswith('Bearer '):raise HTTPException(401,'需要设备接入密钥')
    row=access_control.device(authorization[7:])
    claimed=request.headers.get('device-id')
    if claimed and claimed.replace(':','').replace('-','').upper()!=row['hardware_id'].replace(':','').replace('-','').upper():
        raise HTTPException(403,'物理设备标识与接入密钥不匹配')
    supplied=request.query_params.get('device_id')
    if supplied and supplied!=row['device_id']:raise HTTPException(403,'不能使用本密钥上传另一台设备的数据')
    return row

async def jpeg_body(request):
    payload=bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload)>MAX_BODY:raise HTTPException(413,'单帧不能超过 4 MB')
    content_type=request.headers.get('content-type','image/jpeg')
    if '\r' in content_type or '\n' in content_type:raise HTTPException(400,'无效的图像类型')
    raw=bytes(payload)
    if content_type.lower().startswith('multipart/form-data'):
        message=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
        parts=[p for p in message.iter_parts() if p.get_param('name',header='content-disposition')=='file']
        if len(parts)!=1:raise HTTPException(400,'需要一个名为 file 的 JPEG 文件')
        raw=parts[0].get_payload(decode=True) or b''
    if not raw.startswith(b'\xff\xd8'):raise HTTPException(422,'请上传真实 JPEG 图像')
    return raw

async def accept(request,row):
    now=time.monotonic();device=row['device_id']
    if now-_times.get(device,0)<.5:raise HTTPException(429,'每台设备最多每 0.5 秒上传一帧')
    _times[device]=now;_times.move_to_end(device)
    while len(_times)>1024:_times.popitem(last=False)
    raw=await jpeg_body(request)
    from app.api.ws_handler import _process_frame
    request_id=uuid.uuid4().hex
    if not _process_frame(raw,device,request_id=request_id,link='wifi'):raise HTTPException(503,'图像无效或分析队列已满，请稍后重试')
    await asyncio.to_thread(access_control.seen,device,True)
    return request_id

@router.post('/api/device/heartbeat')
async def heartbeat(request:Request):
    row=await asyncio.to_thread(identity,request)
    await asyncio.to_thread(access_control.seen,row['device_id'])
    return {'status':'ok','device_id':row['device_id'],'server_time':time.time(),'camera_online':live_state.status(row['device_id'])['online']}

@router.post('/api/device/frame')
async def upload(request:Request):
    row=await asyncio.to_thread(identity,request);request_id=await accept(request,row)
    return {'status':'accepted','device_id':row['device_id'],'request_id':request_id,'analysis':'queued'}

@router.post('/vision/explain')
async def explain(request:Request):
    row=await asyncio.to_thread(identity,request);request_id=await accept(request,row)
    names={'engaged_screen':'正在看屏幕学习','engaged_reading':'正在阅读','engaged_writing':'正在书写','thinking':'正在思考','resting':'正在休息','distracted_phone':'可能正在使用手机','distracted_away':'视线暂时离开','fatigued':'出现疲劳迹象','absent':'暂未识别到使用者'}
    for _ in range(75):
        state=live_state.status(row['device_id']);result=state.get('result') or {}
        if result.get('request_id')==request_id:
            text=names.get(result.get('learning_state'),'图像分析已完成')+'。此结果是学习状态估计。'
            return {'text':text,'device_id':row['device_id'],'request_id':request_id,'analysis':'complete'}
        await asyncio.sleep(.2)
    return {'text':'画面已收到，正在后台分析。请稍后在学习工作台查看。','device_id':row['device_id'],'request_id':request_id,'analysis':'queued'}
