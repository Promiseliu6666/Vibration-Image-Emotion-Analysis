from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import mapped_column, Mapped, relationship

from config.database import Base


class PeopleFace(Base):
    __tablename__ = 'xuzhou_people_face'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='人员ID')
    name = Column(String(100), nullable=True, default=None, comment='人员名称')
    group_id: Mapped[int] = mapped_column(ForeignKey('xuzhou_people_group.id'))
    group: Mapped['PeopleGroup'] = relationship(back_populates='members')
    features = Column(JSON, nullable=False, default='[]', comment='人员特征')
    created_time = Column(DateTime, nullable=True, default=None, comment='创建时间')
    updated_time = Column(DateTime, nullable=True, default=None, comment='更新时间')
    is_deleted = Column(Boolean, nullable=False, default=False, comment='是否已删除')
    deleted_time = Column(DateTime, nullable=True, default=None, comment='删除时间')
    pics = Column(LONGTEXT, nullable=False, default='', comment='图片')
