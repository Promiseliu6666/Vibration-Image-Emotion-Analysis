from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from config.database import Base


class LocalAlgorithmRunLog(Base):
    """本地算法运行记录"""
    __tablename__ = 'local_algorithm_run_log'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    vid_id = Column(Integer, nullable=False, comment='摄像头ID')
    algorithm_code = Column(String(64), nullable=False, comment='算法编码')
    algorithm_name = Column(String(128), default='', comment='算法名称')
    status = Column(String(32), nullable=False, default='running', comment='running/completed/failed/stopped')
    start_time = Column(DateTime, nullable=False, comment='启动时间')
    end_time = Column(DateTime, nullable=True, comment='结束时间')
    error_message = Column(String(500), nullable=True, comment='错误信息')
    create_time = Column(DateTime, default=datetime.now, comment='创建时间')
