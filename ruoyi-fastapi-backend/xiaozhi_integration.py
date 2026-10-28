from pathlib import Path
import json,time,secrets,hmac,hashlib
import httpx
from fastapi import APIRouter,Depends,HTTPException
from module_admin.service.login_service import LoginService
router=APIRouter(prefix='/integration/xiaozhi')
@router.get('/launch')
async def launch(user=Depends(LoginService.get_current_user)):
 f=Path(__file__).resolve().parents[2]/'employee-portal/.runtime/sso-secret.txt'
 if not f.exists():raise HTTPException(503,'小智单点登录配置缺失')
 raw=json.dumps({'username':user.user.user_name,'expires':int(time.time())+45,'nonce':secrets.token_urlsafe(24)},separators=(',',':'),ensure_ascii=False)
 sig=hmac.new(f.read_text(encoding='utf-8').strip().encode(),raw.encode(),hashlib.sha256).hexdigest()
 try:
  async with httpx.AsyncClient(trust_env=False,timeout=12) as c:r=await c.post('http://127.0.0.1:8000/api/portal/exchange',json={'payload':raw,'signature':sig})
  d=r.json()
  if not r.is_success:raise HTTPException(r.status_code,d.get('detail','小智账号连接失败'))
  return {'origin':'http://127.0.0.1:8000','token':d['access_token']}
 except httpx.HTTPError:raise HTTPException(503,'小智服务未连接，请确认后台已启动')
