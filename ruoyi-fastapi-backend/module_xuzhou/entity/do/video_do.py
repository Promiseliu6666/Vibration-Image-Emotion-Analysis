from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from config.database import Base


class XuzhouVideo(Base):
    """
    视频信息表
    """

    __tablename__ = 'xuzhou_video'

    vid_id = Column(Integer, primary_key=True, autoincrement=True, comment='视频ID')
    vid_name = Column(String(100), nullable=True, default=None, comment='视频名称')
    vid_serial = Column(String(100), nullable=True, default=None, comment='视频序列号')
    vid_type = Column(String(100), nullable=True, default=None, comment='视频类型')
    vid_scene = Column(Integer, nullable=True, default=None, comment='场景ID')
    vid_scene_name = Column(String(100), nullable=True, default=None, comment='场景名称')
    vid_algorithm_name = Column(String(1000), nullable=True, default=None, comment='算法名称')
    vid_algorithm = Column(Text, nullable=True, default=None, comment='算法信息')
    vid_uri = Column(String(1000), nullable=True, default=None, comment='视频URI')
    vid_update_time = Column(DateTime, nullable=True, default=None, comment='更新时间')
