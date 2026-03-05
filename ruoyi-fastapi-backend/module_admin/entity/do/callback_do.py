from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from config.database import Base


class SysCallback(Base):
    """
    回调地址表
    """

    __tablename__ = 'sys_callback'

    callback_id = Column(Integer, primary_key=True, autoincrement=True, comment='回调ID')
    user_id = Column(Integer, nullable=True, comment='用户ID')
    url = Column(String(500), nullable=False, comment='回调地址')
    description = Column(String(200), nullable=True, default='', comment='描述')
    status = Column(String(1), default='0', comment='状态（0正常 1停用）')
    del_flag = Column(String(1), default='0', comment='删除标志（0代表存在 2代表删除）')
    create_by = Column(String(64), nullable=True, default='', comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_by = Column(String(64), nullable=True, default='', comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')
