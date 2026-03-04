from typing import List

import sqlalchemy.orm as so
from sqlalchemy import Column, DateTime, Integer, String, Boolean

from config.database import Base


class PeopleGroup(Base):
    __tablename__ = 'xuzhou_people_group'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='组ID')
    name = Column(String(100), nullable=False, comment='组名称')
    members: so.Mapped[List['PeopleFace']] = so.relationship(back_populates='group')
    created_time = Column(DateTime, nullable=True, default=None, comment='创建时间')
    updated_time = Column(DateTime, nullable=True, default=None, comment='更新时间')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='是否删除')
    deleted_time = Column(DateTime, nullable=True, default=None, comment='删除时间')
