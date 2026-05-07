from typing import Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from sub_applications.manager_api.core.config import get_settings
from sub_applications.manager_api.core.security import create_access_token, verify_password
from sub_applications.manager_api.models import SysUser

settings = get_settings()


def authenticate_user(db: Session, username: str, password: str) -> Optional[SysUser]:
    stmt = select(SysUser).where(and_(SysUser.user_name == username, SysUser.del_flag == "0"))
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        return None
    if user.status != "0":
        return None
    if not verify_password(password, user.password):
        return None
    return user


def issue_token_for_user(user: SysUser) -> Dict[str, str]:
    payload = {"user_id": str(user.user_id), "username": user.user_name}
    token = create_access_token(payload, settings.jwt_expire_seconds)
    return {"token": token, "expire": settings.jwt_expire_seconds}
