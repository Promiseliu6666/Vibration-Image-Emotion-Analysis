import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sub_applications.manager_api.api.deps import get_current_user
from sub_applications.manager_api.core.database import get_db
from sub_applications.manager_api.core.responses import ruoyi_error, ruoyi_ok
from sub_applications.manager_api.models import SysUser
from sub_applications.manager_api.schemas.auth import RuoyiLoginPayload
from sub_applications.manager_api.services.auth_service import authenticate_user, issue_token_for_user
from sub_applications.manager_api.services.menu_service import get_permissions, get_routers
from sub_applications.manager_api.services.user_service import build_ruoyi_user_profile, get_user_roles

router = APIRouter(tags=["ruoyi-compatible"])


@router.get("/captchaImage")
def captcha_image():
    pixel = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/w8AAn8B9L1bWQAAAABJRU5ErkJggg=="
    )
    return ruoyi_ok(
        data={
            "captchaEnabled": False,
            "img": "data:image/png;base64," + pixel,
            "uuid": str(uuid.uuid4()),
        }
    )


@router.post("/login")
def login(payload: RuoyiLoginPayload, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        return ruoyi_error("Invalid username or password")
    token_pack = issue_token_for_user(user)
    return ruoyi_ok(msg="Operation success", extra={"token": token_pack["token"]})


@router.get("/getInfo")
def get_info(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    roles = get_user_roles(db, int(current_user.user_id))
    permissions = get_permissions(db, int(current_user.user_id))
    user_data = build_ruoyi_user_profile(current_user)
    return ruoyi_ok(data={"user": user_data, "roles": roles, "permissions": permissions})


@router.get("/getRouters")
def get_routers_api(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    routers = get_routers(db, int(current_user.user_id))
    return ruoyi_ok(data=routers)


@router.post("/logout")
def logout():
    return ruoyi_ok(msg="Logout success")
