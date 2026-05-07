from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from sub_applications.manager_api.core.config import Settings, get_settings
from sub_applications.manager_api.core.database import get_db
from sub_applications.manager_api.core.security import decode_access_token
from sub_applications.manager_api.models import SysUser

auth_scheme = HTTPBearer(auto_error=False)


def get_settings_dep() -> Settings:
    return get_settings()


def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> SysUser:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized") from exc

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    stmt = select(SysUser).where(
        and_(
            SysUser.user_id == int(user_id),
            SysUser.status == "0",
            SysUser.del_flag == "0",
        )
    )
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def verify_server_secret(
    settings: Settings = Depends(get_settings_dep),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid server secret")
    if credentials.credentials != settings.server_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid server secret")
    return credentials.credentials
