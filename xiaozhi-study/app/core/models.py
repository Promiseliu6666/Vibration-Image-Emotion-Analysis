from sqlalchemy import Column, Integer, String, Float, DateTime, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session as _Session
from datetime import datetime, timezone
from app.core.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
from app.analysis.analysis_columns import col_comment as _c

DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(engine, class_=_Session, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), default="")
    bind_code = Column(String(8), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class LearningSession(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, index=True)
    start_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_time = Column(DateTime, nullable=True)
    status = Column(String(16), default="active")  # active / ended

class AnalysisResult(Base):
    """分析结果表。

    列注释统一取自 app/analysis/analysis_columns.py（单一事实来源），
    这样用 SQLAlchemy 建表时也能带上注释；已有库则由
    analysis_schema.ensure_schema() 在启动时按需补注释，Navicat 直接可见。
    """
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True, autoincrement=True, comment=_c('id'))
    session_id = Column(Integer, nullable=False, index=True, comment=_c('session_id'))
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment=_c('timestamp'))
    fatigue_level = Column(Float, default=0.0, comment=_c('fatigue_level'))
    distraction_level = Column(Float, default=0.0, comment=_c('distraction_level'))
    gaze_direction = Column(String(16), default="", comment=_c('gaze_direction'))
    action_state = Column(String(16), default="", comment=_c('action_state'))
    difficulty_indicator = Column(Float, default=0.0, comment=_c('difficulty_indicator'))
    learning_state = Column(String(32), default="", comment=_c('learning_state'))
    raw_frame_path = Column(String(256), default="", comment=_c('raw_frame_path'))
    person_present = Column(Integer, default=1, comment=_c('person_present'))
    # Vibraimage 心理状态参数 (Phase 5)
    e1_aggression = Column(Float, default=0.0, comment=_c('e1_aggression'))
    e2_stress = Column(Float, default=0.0, comment=_c('e2_stress'))
    e3_tension = Column(Float, default=0.0, comment=_c('e3_tension'))
    e4_suspiciousness = Column(Float, default=0.0, comment=_c('e4_suspiciousness'))
    e5_balance = Column(Float, default=0.0, comment=_c('e5_balance'))
    e6_charm = Column(Float, default=0.0, comment=_c('e6_charm'))
    e7_energy = Column(Float, default=0.0, comment=_c('e7_energy'))
    e8_self_regulation = Column(Float, default=0.0, comment=_c('e8_self_regulation'))
    e9_inhibition = Column(Float, default=0.0, comment=_c('e9_inhibition'))
    e10_neuroticism = Column(Float, default=0.0, comment=_c('e10_neuroticism'))
    e11_gloominess = Column(Float, default=0.0, comment=_c('e11_gloominess'))
    e12_happiness = Column(Float, default=0.0, comment=_c('e12_happiness'))
    e13_extraversion = Column(Float, default=0.0, comment=_c('e13_extraversion'))
    e14_stability = Column(Float, default=0.0, comment=_c('e14_stability'))
    happiness_index = Column(Float, default=0.0, comment=_c('happiness_index'))
    happiness_level = Column(String(8), default="", comment=_c('happiness_level'))
    safety_risk = Column(String(16), default="", comment=_c('safety_risk'))
    evidence_json = Column(Text, comment=_c('evidence_json'))

async def init_db():
    Base.metadata.create_all(engine)
