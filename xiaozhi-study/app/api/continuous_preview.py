"""Authenticated continuous JPEG preview, independent from analysis cadence."""
import asyncio
import time
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.api.api_router import get_current_user
from app.core import live_state

router=APIRouter(prefix='/api/console')

def packet(device):
    with live_state._lock:
        value=live_state._devices.get(device,{})
        received=value.get('last_received',0)
        if time.time()-received>=live_state.TTL:return None
        jpeg=value.get('preview')
        return (received,jpeg) if jpeg else None

@router.get('/stream/{device_id}')
async def stream(device_id:str,request:Request,user:str=Depends(get_current_user)):
    token=request.headers.get('authorization','').partition(' ')[2]
    async def frames():
        last=None;checked=time.monotonic()
        while not await request.is_disconnected():
            if time.monotonic()-checked>=15:
                from app.core import access_control
                try:await asyncio.to_thread(access_control.decode,token)
                except Exception:return
                checked=time.monotonic()
            item=packet(device_id)
            if item and item[0]!=last:
                last,jpeg=item
                header=(f'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n'
                        f'X-Captured-At: {last}\r\n\r\n').encode('ascii')
                yield header+jpeg+b'\r\n'
            await asyncio.sleep(.025)
    return StreamingResponse(frames(),media_type='multipart/x-mixed-replace; boundary=frame',
                             headers={'Cache-Control':'no-store, no-transform','X-Accel-Buffering':'no'})
