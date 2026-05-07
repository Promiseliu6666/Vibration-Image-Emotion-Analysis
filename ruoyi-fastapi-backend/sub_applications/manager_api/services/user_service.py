from typing import Dict, List

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from sub_applications.manager_api.core.security import get_password_hash, verify_password
from sub_applications.manager_api.models import SysRole, SysUser, SysUserRole


def get_user_roles(db: Session, user_id: int) -> List[str]:
    stmt = (
        select(SysRole.role_key)
        .select_from(SysUserRole)
        .join(SysRole, SysRole.role_id == SysUserRole.role_id)
        .where(
            and_(
                SysUserRole.user_id == user_id,
                SysRole.status == "0",
                SysRole.del_flag == "0",
            )
        )
    )
    roles = [row[0] for row in db.execute(stmt).all() if row[0]]
    if not roles:
        return ["common"]
    return roles


def build_ruoyi_user_profile(user: SysUser) -> Dict[str, str]:
    return {
        "userId": user.user_id,
        "userName": user.user_name,
        "nickName": user.nick_name or user.user_name,
        "avatar": user.avatar or "",
        "status": user.status,
    }


def build_xiaozhi_user_profile(user: SysUser, token: str) -> Dict[str, str]:
    return {
        "id": user.user_id,
        "username": user.user_name,
        "superAdmin": 1 if user.user_name == "admin" else 0,
        "token": token,
        "status": 1 if user.status == "0" else 0,
    }


def change_password(db: Session, user: SysUser, old_password: str, new_password: str) -> bool:
    if not verify_password(old_password, user.password):
        return False
    user.password = get_password_hash(new_password)
    db.add(user)
    db.commit()
    return True
