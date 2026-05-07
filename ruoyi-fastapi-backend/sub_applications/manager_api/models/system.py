from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from sub_applications.manager_api.core.database import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_name = Column(String(64), unique=True, nullable=False, index=True)
    nick_name = Column(String(64), default="")
    password = Column(String(255), nullable=False)
    status = Column(String(1), default="0")
    del_flag = Column(String(1), default="0")
    avatar = Column(String(255), default="")
    create_time = Column(DateTime, server_default=func.now())


class SysRole(Base):
    __tablename__ = "sys_role"

    role_id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_name = Column(String(64), nullable=False)
    role_key = Column(String(100), nullable=False, index=True)
    status = Column(String(1), default="0")
    del_flag = Column(String(1), default="0")
    create_time = Column(DateTime, server_default=func.now())


class SysUserRole(Base):
    __tablename__ = "sys_user_role"

    user_id = Column(BigInteger, primary_key=True)
    role_id = Column(BigInteger, primary_key=True)


class SysMenu(Base):
    __tablename__ = "sys_menu"

    menu_id = Column(BigInteger, primary_key=True, autoincrement=True)
    parent_id = Column(BigInteger, default=0, index=True)
    menu_name = Column(String(64), nullable=False)
    path = Column(String(200), default="")
    component = Column(String(255), default="")
    query = Column(String(255), default="")
    route_name = Column(String(100), default="")
    is_cache = Column(Integer, default=0)
    menu_type = Column(String(1), default="M")
    visible = Column(String(1), default="0")
    status = Column(String(1), default="0")
    perms = Column(String(100), default="")
    icon = Column(String(100), default="")
    order_num = Column(Integer, default=0)
    remark = Column(Text, default="")
    create_time = Column(DateTime, server_default=func.now())


class SysRoleMenu(Base):
    __tablename__ = "sys_role_menu"

    role_id = Column(BigInteger, primary_key=True)
    menu_id = Column(BigInteger, primary_key=True)
