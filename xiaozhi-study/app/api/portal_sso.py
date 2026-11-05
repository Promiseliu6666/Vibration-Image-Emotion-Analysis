"""Exchange a short-lived signed ticket for an enabled local Xiaozhi account."""

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from jose import jwt

from app.core import access_control
from app.core.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from app.core.paths import RUNTIME_DIR

router = APIRouter()
used = {}
lock = asyncio.Lock()


@router.post('/api/portal/exchange')
async def exchange(request: Request):
    if not request.client or request.client.host not in ('127.0.0.1', '::1') or request.headers.get('origin'):
        raise HTTPException(403, '仅允许本机统一门户连接')

    try:
        secret = (RUNTIME_DIR / 'portal-sso-secret.txt').read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError) as exc:
        raise HTTPException(503, '统一门户接入尚未配置') from exc
    if not secret:
        raise HTTPException(503, '统一门户接入尚未配置')

    try:
        body = await request.json()
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(400, '无效的登录凭据') from exc
    if not isinstance(body, dict):
        raise HTTPException(400, '无效的登录凭据')
    raw = body.get('payload')
    signature = body.get('signature')
    if (not isinstance(raw, str) or len(raw) > 2048
            or not isinstance(signature, str) or not re.fullmatch('[0-9a-f]{64}', signature)):
        raise HTTPException(400, '无效的登录凭据')
    try:
        encoded = raw.encode('utf-8')
    except UnicodeError as exc:
        raise HTTPException(400, '无效的登录凭据') from exc
    expected = hmac.new(secret.encode('utf-8'), encoded, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(403, '登录签名无效')

    try:
        claims = json.loads(raw)
        expires = claims['expires']
        nonce = claims['nonce']
        username = claims['username']
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, '登录凭据格式不正确') from exc
    if (type(expires) is not int or not isinstance(nonce, str) or not 24 <= len(nonce) <= 128
            or not isinstance(username, str) or not username.strip() or len(username) > 64):
        raise HTTPException(400, '登录凭据格式不正确')
    now = time.time()
    if expires < now or expires > now + 60:
        raise HTTPException(403, '登录凭据已过期')

    async with lock:
        for previous_nonce, expiration in list(used.items()):
            if expiration < now:
                del used[previous_nonce]
        if nonce in used:
            raise HTTPException(403, '登录凭据已使用')
        used[nonce] = expires

    account = await asyncio.to_thread(access_control.user, username)
    if not account or not account['enabled']:
        raise HTTPException(403, '小智中没有已启用的同名账号，请由管理员配置')
    token = jwt.encode(
        {'sub': username, 'ver': account['token_version'],
         'exp': datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return JSONResponse(
        {'access_token': token, 'token_type': 'bearer', 'role': account['role']},
        headers={'Cache-Control': 'no-store'},
    )
