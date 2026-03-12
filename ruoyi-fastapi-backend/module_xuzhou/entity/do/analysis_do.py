from datetime import datetime


from sqlalchemy import Column, Integer, String, Text, DateTime,ForeignKey,Float
from config.database import Base


class BinhuaAnalysis(Base):
    """分析数据的列表"""
    __tablename__ = 'binhua_analysis'
    id=Column(Integer, autoincrement=True, primary_key=True,comment='ID')
    source=Column(String(100),nullable=False,comment='视频来源')
    person_name=Column(String(100),nullable=False,comment='人名')
    person_id = Column(Integer, ForeignKey('xuzhou_people_face.id', ondelete='SET NULL'), nullable=True, comment='人员ID')
    e1=Column(Float,default=0,comment='e1')
    e2=Column(Float,default=0,comment='e2')
    e3=Column(Float,default=0,comment='e3')
    e4=Column(Float,default=0,comment='e4')
    e5=Column(Float,default=0,comment='e5')
    e6=Column(Float,default=0,comment='e6')
    e7=Column(Float,default=0,comment='e7')
    e8=Column(Float,default=0,comment='e8')
    e9=Column(Float,default=0,comment='e9')
    e10=Column(Float,default=0,comment='e10')
    e11=Column(Float,default=0,comment='e11')
    e12=Column(Float,default=0,comment='e12')
    e13=Column(Float,default=0,comment='e13')
    e14=Column(Float,default=0,comment='e14')
    happiness_index = Column(Float, default=0.0, comment='幸福指数')
    happiness_level = Column(String(50), nullable=True, comment='幸福等级')  # 字符串类型
    safety_risk = Column(String(100), nullable=True, comment='安全风险')  # 字符串类型
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='记录创建时间')