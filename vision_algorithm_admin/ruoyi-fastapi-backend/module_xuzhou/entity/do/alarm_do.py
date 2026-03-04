from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from config.database import Base


class XuzhouAlarm(Base):
    """
    预警消息表
    """

    __tablename__ = 'xuzhou_alarm'

    alarm_id = Column(Integer, primary_key=True, autoincrement=True, comment='预警ID')
    vid_id = Column(Integer, nullable=True, comment='视频ID')
    vid_name = Column(String(100), nullable=True, comment='视频名称')
    vid_serial = Column(String(100), nullable=True, comment='视频序列号')
    alarm_code = Column(String(100), nullable=True, comment='预警编码')
    alarm_time = Column(DateTime, nullable=True, default=datetime.now, comment='预警时间')
    alarm_image = Column(Text, nullable=True, comment='预警图片')
    alarm_content = Column(Text, nullable=True, comment='预警内容JSON')
    push_result = Column(Text, nullable=True, comment='推送结果JSON')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
