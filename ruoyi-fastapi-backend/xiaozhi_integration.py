"""Authenticated local SSO bridge with actionable, non-sensitive diagnostics."""
from pathlib import Path
import hashlib
import hmac
import json
import secrets
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from module_admin.service.login_service import LoginService

XIAOZHI_ORIGIN = 'http://127.0.0.1:8000'
SSO_SECRET_FILE = Path(__file__).resolve().parents[2] / 'employee-portal/.runtime/sso-secret.txt'
_bearer = HTTPBearer(auto_error=False)


def require_bearer(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)):
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(401, '请先登录健康监测平台')


router = APIRouter(prefix='/integration/xiaozhi', dependencies=[Depends(require_bearer)])


def _configured():
    try:
        return SSO_SECRET_FILE.is_file() and bool(SSO_SECRET_FILE.read_text(encoding='utf-8').strip())
    except (OSError, UnicodeError):
        return False


def _read_secret():
    try:
        secret = SSO_SECRET_FILE.read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError) as exc:
        raise HTTPException(503, '小智单点登录配置缺失或不可读取，请检查本机接入配置') from exc
    if not secret:
        raise HTTPException(503, '小智单点登录配置为空，请检查本机接入配置')
    return secret


def _upstream_json(response):
    try:
        data = response.json()
    except (ValueError, TypeError) as exc:
        raise HTTPException(502, '小智服务返回了无效响应，请检查服务版本与端口配置') from exc
    if not isinstance(data, dict):
        raise HTTPException(502, '小智服务返回了无效响应，请检查服务版本与端口配置')
    return data


def _login_error(response, data):
    status = response.status_code
    detail = data.get('detail', '')
    detail = detail if isinstance(detail, str) else ''
    if status in (401, 403):
        if '同名账号' in detail or '账号' in detail:
            message = '小智中没有已启用的同名账号，请由管理员检查账号授权'
        elif '签名' in detail:
            message = '小智登录签名不一致，请检查两个服务的单点登录配置'
        elif '过期' in detail:
            message = '小智登录凭据已过期，请检查系统时间后重新连接'
        elif '已使用' in detail:
            message = '小智登录凭据已使用，请重新连接'
        elif '本机' in detail:
            message = '小智拒绝了接入来源，请检查本机服务地址'
        else:
            message = '小智拒绝了登录接入，请检查账号授权与共享签名配置'
        raise HTTPException(status, message)
    if status == 503:
        message = ('小智单点登录尚未配置，请检查小智本机运行环境'
                   if '配置' in detail else '小智服务暂不可用，请检查后台服务和数据库连接')
        raise HTTPException(503, message)
    if status == 404:
        raise HTTPException(502, '小智服务缺少登录接入接口，请检查服务版本与端口配置')
    raise HTTPException(502, '小智登录接入失败，请检查小智后台服务状态')


@router.get('/launch')
async def launch(reply: Response, user=Depends(LoginService.get_current_user)):
    try:
        username = user.user.user_name
    except AttributeError as exc:
        raise HTTPException(401, '登录已失效，请重新登录健康监测平台') from exc
    if not isinstance(username, str) or not username.strip() or len(username) > 64:
        raise HTTPException(401, '登录已失效，请重新登录健康监测平台')
    secret = _read_secret()
    raw = json.dumps({'username': username, 'expires': int(time.time()) + 45,
                      'nonce': secrets.token_urlsafe(24)}, separators=(',', ':'), ensure_ascii=False)
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=12) as client:
            response = await client.post(XIAOZHI_ORIGIN + '/api/portal/exchange',
                                         json={'payload': raw, 'signature': signature})
    except httpx.TimeoutException as exc:
        raise HTTPException(504, '小智服务响应超时，请检查后台运行状态后重试') from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, '小智服务未连接，请先启动小智服务后重新连接') from exc
    data = _upstream_json(response)
    if not response.is_success:
        _login_error(response, data)
    token = data.get('access_token')
    if not isinstance(token, str) or not token.strip() or len(token) > 16384:
        raise HTTPException(502, '小智服务没有返回有效登录凭据，请检查接口版本')
    reply.headers['Cache-Control'] = 'no-store'
    return {'origin': XIAOZHI_ORIGIN, 'token': token}


@router.get('/status')
async def status(user=Depends(LoginService.get_current_user)):
    configured = _configured()
    result = {'online': False, 'sso_configured': configured, 'reason': ''}
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=4) as client:
            response = await client.get(XIAOZHI_ORIGIN + '/openapi.json')
        schema = response.json()
        paths = schema.get('paths') if isinstance(schema, dict) else None
        correct_service = response.is_success and isinstance(paths, dict) and all(
            path in paths for path in ('/api/portal/exchange', '/api/camera-source/devices'))
        if not correct_service:
            result['reason'] = '8000 端口未提供预期的小智接口，请检查服务版本或端口占用'
        else:
            result['online'] = True
            result['reason'] = '小智服务已连接' if configured else '小智服务已连接，但主系统单点登录配置缺失'
    except httpx.TimeoutException:
        result['reason'] = '小智服务响应超时，请检查后台运行状态'
    except httpx.RequestError:
        result['reason'] = '小智服务未启动，请先启动小智服务'
    except (ValueError, TypeError):
        result['reason'] = '8000 端口返回了无效响应，请检查小智服务版本'
    return {'code': 200, 'data': result}
