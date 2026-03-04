from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from config.database import Base


class XuzhouScene(Base):
    """
    场景信息表
    """

    __tablename__ = 'xuzhou_scene'

    scene_id = Column(Integer, primary_key=True, autoincrement=True, comment='场景ID')
    scene_name = Column(String(100), nullable=True, default=None, comment='场景名称')
    scene_serial = Column(String(100), nullable=True, default=None, comment='场景序列号')
    scene_algorithm = Column(String(1000), nullable=True, default=None, comment='保存列表形式算法id数据')
    scene_algorithm_name = Column(String(1000), nullable=True, default=None, comment='保存列表形式算法名称数据')
    scene_update_time = Column(DateTime, nullable=True, default=None, comment='更新时间')
