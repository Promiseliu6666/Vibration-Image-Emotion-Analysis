from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from config.database import Base


class XuzhouAlg(Base):
    """
    算法信息表
    """

    __tablename__ = 'xuzhou_alg'

    alg_id = Column(Integer, primary_key=True, autoincrement=True, comment='算法ID')
    alg_name = Column(String(100), nullable=True, default=None, comment='算法名称')
    alg_version = Column(String(100), nullable=True, default=None, comment='算法版本')
    alg_serial = Column(String(100), nullable=True, default=None, comment='算法序列号')
    alg_common = Column(String(1000), nullable=True, default=None, comment='算法通用字段')
    alg_default_conf = Column(String(2000), nullable=True, default=None, comment='算法默认配置(JSON字符串)')
    alg_update_time = Column(DateTime, nullable=True, default=None, comment='更新时间')
