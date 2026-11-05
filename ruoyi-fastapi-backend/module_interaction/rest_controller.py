"""Interactive rest-room endpoints use the platform's original bearer login."""
from __future__ import annotations
import asyncio
import time
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from module_admin.service.login_service import LoginService
from module_interaction.rest_service import RestError, RestService

_bearer = HTTPBearer(auto_error=False)
def require_bearer(credentials: HTTPAuthorizationCredentials|None = Depends(_bearer)):
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(401,'请先登录健康监测平台')

rest_controller = APIRouter(prefix='/interaction/rest', tags=['互动休息室'], dependencies=[Depends(require_bearer)])
_default_service = RestService()
def get_rest_service():return _default_service

class StartRestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: Literal['breathing','eyes','stretch']
    source: str = Field(default='local',min_length=1,max_length=73)
    device_label: str|None = Field(default=None,max_length=80)
class RestActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['pause','resume','finish','cancel']
    method: Literal['button','gesture'] = 'button'

def _owner(user):
    try:return RestService._user_key(user.user.user_id)
    except (AttributeError,RestError):raise HTTPException(401,'请重新登录健康监测平台')
async def _call(function,*args):
    try:return await asyncio.to_thread(function,*args)
    except RestError as exc:raise HTTPException(exc.status_code,exc.message) from exc

@rest_controller.get('/catalog')
async def rest_catalog(user=Depends(LoginService.get_current_user)):
    _owner(user)
    return {'code':200,'data':{'projects':RestService.catalog()}}
@rest_controller.get('/state')
async def rest_state(user=Depends(LoginService.get_current_user),service:RestService=Depends(get_rest_service)):
    return {'code':200,'data':await _call(service.get_state,_owner(user))}
@rest_controller.post('/sessions')
async def start_rest(body:StartRestRequest,user=Depends(LoginService.get_current_user),service:RestService=Depends(get_rest_service)):
    return {'code':200,'data':{'session':await _call(service.create_session,_owner(user),body.project_id,body.source,body.device_label)}}
@rest_controller.post('/sessions/{session_id}/action')
async def rest_action(session_id:str,body:RestActionRequest,user=Depends(LoginService.get_current_user),service:RestService=Depends(get_rest_service)):
    if len(session_id)>64:raise HTTPException(404,'休息记录不存在')
    return {'code':200,'data':{'session':await _call(service.act,_owner(user),session_id,body.action,body.method)}}

async def read_camera_frame(source):
    """Reuse the CameraHub without recording images or opening a second capture."""
    try:canonical=RestService.validate_source(source)
    except RestError as exc:raise HTTPException(exc.status_code,exc.message) from exc
    import cv2
    from hik_vision.hik_vision import camera_hubs, resolve_registered_camera_source
    if canonical.startswith('xiaozhi:'):
        canonical = await resolve_registered_camera_source('xiaozhi', canonical.split(':', 1)[1])
    hub=camera_hubs.get(canonical)
    if hub is None:raise HTTPException(400,'摄像头来源不存在')
    deadline=time.monotonic()+2.0
    while time.monotonic()<deadline:
        frame,sequence,captured_at=hub.latest()
        if frame is not None:
            def encode():
                height,width=frame.shape[:2]
                image=cv2.resize(frame,(640,max(1,round(height*640/width)))) if width>640 else frame
                ok,jpeg=cv2.imencode('.jpg',image,[int(cv2.IMWRITE_JPEG_QUALITY),85])
                return jpeg.tobytes() if ok else None
            content=await asyncio.to_thread(encode)
            if content is not None:
                return Response(content,media_type='image/jpeg',headers={
                    'Cache-Control':'no-store, no-cache','X-Content-Type-Options':'nosniff',
                    'X-Frame-Sequence':str(sequence),'X-Frame-Captured-At':str(captured_at),'X-Captured-At':str(captured_at)})
        await asyncio.sleep(.08)
    raise HTTPException(503,'摄像头暂无有效画面，请检查所选设备或切换摄像头')
@rest_controller.get('/frame')
async def rest_frame(source:str=Query(default='local',max_length=73),user=Depends(LoginService.get_current_user)):
    _owner(user)
    return await read_camera_frame(source)
