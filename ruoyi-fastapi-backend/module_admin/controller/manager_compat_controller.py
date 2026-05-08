import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import RedisInitKeyConfig
from config.env import AppConfig, JwtConfig
from config.get_db import get_db
from module_admin.entity.vo.login_vo import UserLogin
from module_admin.entity.vo.user_vo import CurrentUserModel, EditUserModel, ResetUserModel
from module_admin.service.login_service import LoginService
from module_admin.service.user_service import UserService

managerCompatController = APIRouter(prefix="/manager-api", tags=["manager-api-compat"])
server_secret_auth = HTTPBearer(auto_error=False)


class RuoyiLoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)
    code: str = ""
    uuid: str = ""


class XiaozhiLoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)
    captchaId: str = ""
    captcha: str = ""
    mobileCaptcha: str = ""


class ChangePasswordPayload(BaseModel):
    password: str = Field(min_length=1, max_length=255)
    newPassword: str = Field(min_length=1, max_length=255)


class AgentModelsPayload(BaseModel):
    macAddress: str = Field(min_length=1)
    clientId: str = Field(min_length=1)
    selectedModule: Dict[str, Any] = Field(default_factory=dict)


class CorrectWordsPayload(BaseModel):
    macAddress: str = Field(min_length=1)


class ChatHistoryReportPayload(BaseModel):
    macAddress: str = Field(min_length=1)
    sessionId: str = Field(min_length=1)
    chatType: int
    content: str = ""
    reportTime: Optional[str] = None
    audioBase64: Optional[str] = None


def _ruoyi_ok(
    data: Any = None,
    msg: str = "Operation success",
    code: int = 200,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"code": code, "msg": msg}
    if data is not None:
        body["data"] = data
    if extra:
        body.update(extra)
    return body


def _ruoyi_error(msg: str = "Operation failed", code: int = 500) -> Dict[str, Any]:
    return {"code": code, "msg": msg}


def _xz_ok(data: Any = None, msg: str = "success") -> Dict[str, Any]:
    return {"code": 0, "msg": msg, "data": data}


def _xz_error(code: int, msg: str, data: Any = None) -> Dict[str, Any]:
    return {"code": code, "msg": msg, "data": data}


def _get_exception_message(exc: Exception, default: str) -> str:
    return getattr(exc, "message", None) or str(exc) or default


async def _issue_login_token(request: Request, query_db: AsyncSession, username: str, password: str, code: str, uuid_: str):
    captcha_enabled = (
        True
        if await request.app.state.redis.get(f"{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.captchaEnabled")
        == "true"
        else False
    )
    login_user = UserLogin(
        user_name=username,
        password=password,
        code=code,
        uuid=uuid_,
        login_info={},
        captcha_enabled=captcha_enabled,
    )
    result = await LoginService.authenticate_user(request, query_db, login_user)

    access_token_expires = timedelta(minutes=JwtConfig.jwt_expire_minutes)
    session_id = str(uuid.uuid4())
    access_token = await LoginService.create_access_token(
        data={
            "user_id": str(result[0].user_id),
            "user_name": result[0].user_name,
            "dept_name": result[1].dept_name if result[1] else None,
            "session_id": session_id,
            "login_info": {},
        },
        expires_delta=access_token_expires,
    )
    if AppConfig.app_same_time_login:
        await request.app.state.redis.set(
            f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}",
            access_token,
            ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes),
        )
    else:
        await request.app.state.redis.set(
            f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{result[0].user_id}",
            access_token,
            ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes),
        )
    await UserService.edit_user_services(
        query_db, EditUserModel(userId=result[0].user_id, loginDate=datetime.now(), type="status")
    )
    return access_token


async def _verify_server_secret(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(server_secret_auth),
) -> str:
    server_secret = os.getenv("MANAGER_API_SERVER_SECRET", "manager-api-secret")
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid server secret")
    if credentials.credentials != server_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid server secret")
    return credentials.credentials


@managerCompatController.get("/health")
async def health():
    return {"status": "ok"}


@managerCompatController.get("/captchaImage")
async def captcha_image():
    pixel = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/w8AAn8B9L1bWQAAAABJRU5ErkJggg=="
    )
    return _ruoyi_ok(
        data={
            "captchaEnabled": False,
            "img": "data:image/png;base64," + pixel,
            "uuid": str(uuid.uuid4()),
        }
    )


@managerCompatController.post("/login")
async def ruoyi_login(payload: RuoyiLoginPayload, request: Request, query_db: AsyncSession = Depends(get_db)):
    try:
        token = await _issue_login_token(
            request=request,
            query_db=query_db,
            username=payload.username,
            password=payload.password,
            code=payload.code,
            uuid_=payload.uuid,
        )
        return _ruoyi_ok(msg="Operation success", extra={"token": token})
    except Exception as exc:
        return _ruoyi_error(_get_exception_message(exc, "Login failed"))


@managerCompatController.get("/getInfo")
async def ruoyi_get_info(current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    user = current_user.user
    user_payload = user.model_dump(by_alias=True) if user else {}
    return _ruoyi_ok(
        data={
            "user": user_payload,
            "roles": current_user.roles or ["common"],
            "permissions": current_user.permissions or ["*:*:*"],
        }
    )


@managerCompatController.get("/getRouters")
async def ruoyi_get_routers(
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
    query_db: AsyncSession = Depends(get_db),
):
    if not current_user.user:
        return _ruoyi_ok(data=[])
    routers = await LoginService.get_current_user_routers(current_user.user.user_id, query_db)
    return _ruoyi_ok(data=routers)


@managerCompatController.post("/logout")
async def ruoyi_logout(request: Request, current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        user_id = current_user.user.user_id if current_user.user else None
        if user_id:
            await request.app.state.redis.delete(f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{user_id}")
    except Exception:
        pass
    return _ruoyi_ok(msg="Logout success")


@managerCompatController.post("/xiaozhi/user/login")
async def xiaozhi_login(payload: XiaozhiLoginPayload, request: Request, query_db: AsyncSession = Depends(get_db)):
    try:
        token = await _issue_login_token(
            request=request,
            query_db=query_db,
            username=payload.username,
            password=payload.password,
            code=payload.captcha,
            uuid_=payload.captchaId,
        )
        return _xz_ok(data={"token": token, "expire": JwtConfig.jwt_expire_minutes * 60, "clientHash": ""})
    except Exception:
        return _xz_error(10001, "Invalid username or password")


@managerCompatController.get("/xiaozhi/user/info")
async def xiaozhi_info(current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    if not current_user.user:
        return _xz_error(10003, "Unauthorized")
    return _xz_ok(
        data={
            "id": current_user.user.user_id,
            "username": current_user.user.user_name,
            "superAdmin": 1 if current_user.user.user_id == 1 else 0,
            "token": "",
            "status": 1 if current_user.user.status == "0" else 0,
        }
    )


@managerCompatController.put("/xiaozhi/user/change-password")
async def xiaozhi_change_password(
    payload: ChangePasswordPayload,
    query_db: AsyncSession = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    if not current_user.user:
        return _xz_error(10003, "Unauthorized")
    try:
        result = await UserService.reset_user_services(
            query_db,
            ResetUserModel(
                userId=current_user.user.user_id,
                oldPassword=payload.password,
                password=payload.newPassword,
            ),
        )
        if result.is_success:
            return _xz_ok()
        return _xz_error(10002, result.message or "Change password failed")
    except Exception as exc:
        return _xz_error(10002, _get_exception_message(exc, "Invalid old password"))


@managerCompatController.get("/xiaozhi/user/pub-config")
async def xiaozhi_pub_config():
    config = {
        "enableMobileRegister": False,
        "version": "fastapi-embedded-1.0.0",
        "year": str(datetime.now().year),
        "allowUserRegister": False,
        "mobileAreaList": [],
        "beianIcpNum": "",
        "beianGaNum": "",
        "name": "manager-api-python-embedded",
        "sm2PublicKey": "not-required-in-fastapi-mode",
        "systemWebMenu": {
            "features": {
                "voiceprintRecognition": {"enabled": False},
                "voiceClone": {"enabled": False},
                "knowledgeBase": {"enabled": False},
                "mcpAccessPoint": {"enabled": False},
                "vad": {"enabled": False},
                "asr": {"enabled": False},
            }
        },
    }
    return _xz_ok(data=config)


@managerCompatController.post("/xiaozhi/config/server-base")
async def xiaozhi_config_server_base(_secret: str = Depends(_verify_server_secret)):
    return _xz_ok(data={"server": {"name": "xiaozhi-fastapi", "auth_enabled": True}})


@managerCompatController.post("/xiaozhi/config/agent-models")
async def xiaozhi_config_agent_models(payload: AgentModelsPayload, _secret: str = Depends(_verify_server_secret)):
    selected = payload.selectedModule or {}
    return _xz_ok(
        data={
            "macAddress": payload.macAddress,
            "clientId": payload.clientId,
            "selectedModule": selected,
            "models": selected,
        }
    )


@managerCompatController.post("/xiaozhi/config/correct-words")
async def xiaozhi_config_correct_words(
    _payload: CorrectWordsPayload, _secret: str = Depends(_verify_server_secret)
):
    return _xz_ok(data=[])


@managerCompatController.post("/xiaozhi/agent/chat-history/report")
async def xiaozhi_chat_history_report(
    _payload: ChatHistoryReportPayload, _secret: str = Depends(_verify_server_secret)
):
    return _xz_ok(data={"saved": True})


@managerCompatController.post("/xiaozhi/agent/chat-summary/{session_id}/save")
async def xiaozhi_chat_summary_save(session_id: str, _secret: str = Depends(_verify_server_secret)):
    return _xz_ok(data={"sessionId": session_id, "summary": ""})


@managerCompatController.post("/xiaozhi/agent/chat-title/{session_id}/generate")
async def xiaozhi_chat_title_generate(session_id: str, _secret: str = Depends(_verify_server_secret)):
    return _xz_ok(data={"sessionId": session_id, "title": "New chat"})
