from sqlalchemy import select
from sqlalchemy.orm import Session

from sub_applications.manager_api.core.database import Base, engine
from sub_applications.manager_api.core.security import get_password_hash
from sub_applications.manager_api.models import SysMenu, SysRole, SysRoleMenu, SysUser, SysUserRole


def _seed_user_role_menu(db: Session) -> None:
    has_user = db.execute(select(SysUser.user_id).limit(1)).first()
    if has_user:
        return

    admin_user = SysUser(
        user_name="admin",
        nick_name="admin",
        password=get_password_hash("admin123"),
        status="0",
        del_flag="0",
    )
    db.add(admin_user)
    db.flush()

    admin_role = SysRole(
        role_name="admin",
        role_key="admin",
        status="0",
        del_flag="0",
    )
    db.add(admin_role)
    db.flush()

    db.add(SysUserRole(user_id=admin_user.user_id, role_id=admin_role.role_id))

    dashboard_menu = SysMenu(
        parent_id=0,
        menu_name="Dashboard",
        path="/",
        component="Layout",
        route_name="Dashboard",
        menu_type="M",
        visible="0",
        status="0",
        icon="dashboard",
        order_num=1,
    )
    home_menu = SysMenu(
        parent_id=0,
        menu_name="Home",
        path="home",
        component="home/index",
        route_name="Home",
        menu_type="C",
        visible="0",
        status="0",
        perms="system:dashboard:view",
        icon="home",
        order_num=2,
    )

    db.add(dashboard_menu)
    db.add(home_menu)
    db.flush()

    db.add(SysRoleMenu(role_id=admin_role.role_id, menu_id=dashboard_menu.menu_id))
    db.add(SysRoleMenu(role_id=admin_role.role_id, menu_id=home_menu.menu_id))
    db.commit()


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    db = Session(bind=engine, future=True)
    try:
        _seed_user_role_menu(db)
    finally:
        db.close()
