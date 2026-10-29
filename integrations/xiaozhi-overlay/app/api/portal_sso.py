"""Short-lived, signed local portal exchange; maps to enabled existing accounts."""
import asyncio,hashlib,hmac,json,secrets,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import APIRouter,Request,HTTPException
from jose import jwt
from app.core.paths import RUNTIME_DIR
from app.core.config import JWT_SECRET,JWT_ALGORITHM,JWT_EXPIRE_MINUTES
from app.core import access_control
router=APIRouter();used={};lock=asyncio.Lock()
@router.post('/api/portal/exchange')
async def exchange(r:Request):
 if not r.client or r.client.host not in ('127.0.0.1','::1') or r.headers.get('origin'):
  raise HTTPException(403,'仅允许本机统一门户连接')
 f=RUNTIME_DIR/'portal-sso-secret.txt'
 if not f.exists():raise HTTPException(503,'统一门户接入尚未配置')
 body=await r.json();raw=body.get('payload','');sig=body.get('signature','')
 if not isinstance(raw,str) or len(raw)>2048 or not isinstance(sig,str):raise HTTPException(400,'无效的登录凭据')
 expected=hmac.new(f.read_text(encoding='utf-8').strip().encode(),raw.encode(),hashlib.sha256).hexdigest()
 if not hmac.compare_digest(sig,expected):raise HTTPException(403,'登录签名无效')
 try:d=json.loads(raw);expires=int(d['expires']);nonce=str(d['nonce']);username=str(d['username'])
 except Exception:raise HTTPException(400,'登录凭据格式不正确')
 now=time.time()
 if expires<now or expires>now+60 or len(nonce)<24:raise HTTPException(403,'登录凭据已过期')
 async with lock:
  for k in list(used):
   if used[k]<now:used.pop(k,None)
  if nonce in used:raise HTTPException(403,'登录凭据已使用')
  used[nonce]=expires
 row=await asyncio.to_thread(access_control.user,username)
 if not row or not row['enabled']:raise HTTPException(403,'小智中没有已启用的同名账号，请由管理员配置')
 token=jwt.encode({'sub':username,'ver':row['token_version'],'exp':datetime.now(timezone.utc)+timedelta(minutes=JWT_EXPIRE_MINUTES)},JWT_SECRET,algorithm=JWT_ALGORITHM)
 return {'access_token':token,'token_type':'bearer','role':row['role']}
