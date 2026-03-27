# agent_message.py
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, JSON, Boolean, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import mapped_column, Mapped, relationship

from config.database import Base


class AgentMessage(Base):
    """AI Agent 消息记录表"""
    __tablename__ = 'xuzhou_agent_message'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='消息ID')

    # 会话标识（同一个对话链用同一个 conversation_id）
    conversation_id = Column(String(64), nullable=False, index=True, comment='会话ID')

    # 可关联具体用户或 Agent 实例
    user_id = Column(String(64), nullable=True, index=True, comment='用户ID')
    agent_id = Column(String(64), nullable=True, index=True, comment='Agent ID')

    # 消息角色
    role = Column(String(20), nullable=False, comment='角色: user / assistant / system / tool')

    # 消息内容
    content = Column(LONGTEXT, nullable=False, default='', comment='消息内容')

    # 额外元数据（模型名称、token数、工具调用、情绪等）
    metadata_json = Column(JSON, nullable=False, default='{}', comment='元数据')

    # 如果使用了工具调用，可单独记录
    tool_calls = Column(JSON, nullable=True, default=None, comment='工具调用记录')

    # 时间字段（保持和你项目一致的风格）
    created_time = Column(DateTime, nullable=True, default=None, comment='创建时间')
    updated_time = Column(DateTime, nullable=True, default=None, comment='更新时间')

    # 软删除
    is_deleted = Column(Boolean, nullable=False, default=False, comment='是否已删除')
    deleted_time = Column(DateTime, nullable=True, default=None, comment='删除时间')

    # 可选：和人员表建立关联（如果你的Agent需要关联具体人员）
    # people_id = Column(Integer, ForeignKey('xuzhou_people_face.id'), nullable=True)
    # people: Mapped['PeopleFace'] = relationship('PeopleFace')

    __table_args__ = (
        {'comment': 'AI Agent 消息记录表'},
    )