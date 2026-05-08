from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sub_applications.manager_api.api.deps import get_current_user, verify_server_secret
from sub_applications.manager_api.core.database import get_db
from sub_applications.manager_api.core.responses import xz_error, xz_ok
from sub_applications.manager_api.models import SysUser
from sub_applications.manager_api.schemas.auth import ChangePasswordPayload, XiaozhiLoginPayload
from sub_applications.manager_api.schemas.xiaozhi import (
    AgentModelsPayload,
    ChatHistoryReportPayload,
    CorrectWordsPayload,
)
from sub_applications.manager_api.services.auth_service import authenticate_user, issue_token_for_user
from sub_applications.manager_api.services.user_service import build_xiaozhi_user_profile, change_password

router = APIRouter(tags=["xiaozhi-compatible"])


@router.post("/user/login")
def login(payload: XiaozhiLoginPayload, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        return xz_error(10001, "Invalid username or password")
    token_pack = issue_token_for_user(user)
    data = {
        "token": token_pack["token"],
        "expire": token_pack["expire"],
        "clientHash": "",
    }
    return xz_ok(data=data)


@router.get("/user/info")
def info(current_user: SysUser = Depends(get_current_user)):
    profile = build_xiaozhi_user_profile(current_user, token="")
    return xz_ok(data=profile)


@router.put("/user/change-password")
def change_password_api(
    payload: ChangePasswordPayload,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = change_password(db, current_user, payload.password, payload.newPassword)
    if not success:
        return xz_error(10002, "Invalid old password")
    return xz_ok()


@router.get("/user/pub-config")
def pub_config():
    config = {
        "enableMobileRegister": False,
        "version": "fastapi-1.0.0",
        "year": str(datetime.now().year),
        "allowUserRegister": False,
        "mobileAreaList": [],
        "beianIcpNum": "",
        "beianGaNum": "",
        "name": "manager-api-fastapi",
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
    return xz_ok(data=config)


@router.post("/config/server-base")
def config_server_base(
    _secret: str = Depends(verify_server_secret),
):
    return xz_ok(
        data={
            "server": {
                "name": "xiaozhi-fastapi",
                "auth_enabled": True,
            }
        }
    )


@router.post("/config/agent-models")
def config_agent_models(
    payload: AgentModelsPayload,
    _secret: str = Depends(verify_server_secret),
):
    selected = payload.selectedModule or {}
    return xz_ok(
        data={
            "macAddress": payload.macAddress,
            "clientId": payload.clientId,
            "selectedModule": selected,
            "models": selected,
        }
    )


@router.post("/config/correct-words")
def config_correct_words(
    _payload: CorrectWordsPayload,
    _secret: str = Depends(verify_server_secret),
):
    return xz_ok(data=[])


@router.post("/agent/chat-history/report")
def chat_history_report(
    _payload: ChatHistoryReportPayload,
    _secret: str = Depends(verify_server_secret),
):
    return xz_ok(data={"saved": True})


@router.post("/agent/chat-summary/{session_id}/save")
def chat_summary_save(session_id: str, _secret: str = Depends(verify_server_secret)):
    return xz_ok(data={"sessionId": session_id, "summary": ""})


@router.post("/agent/chat-title/{session_id}/generate")
def chat_title_generate(session_id: str, _secret: str = Depends(verify_server_secret)):
    return xz_ok(data={"sessionId": session_id, "title": "New chat"})
