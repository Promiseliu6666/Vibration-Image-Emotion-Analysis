# module_xuzhou/entity/vo/agent_vo.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class SaveAgentMessageModel(BaseModel):
    conversation_id: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    role: str
    content: str
    metadata_json: Dict = Field(default_factory=dict)
    tool_calls: Optional[Dict] = None


class AgentMessageModel(BaseModel):   # 如果你有这个用于返回的模型
    id: int
    conversation_id: str
    user_id: Optional[str]
    agent_id: Optional[str]
    role: str
    content: str
    metadata_json: Dict
    tool_calls: Optional[Dict]
    created_time: datetime
    updated_time: Optional[datetime]
    is_deleted: bool = False
    deleted_time: Optional[datetime]

    class Config:
        from_attributes = True   # 方便从 ORM 对象转换


class AgentMessagePageQueryModel(BaseModel):
    page_num: int = 1
    page_size: int = 20
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    role: Optional[str] = None
    include_deleted: bool = False
    order_by: Optional[str] = "created_time"