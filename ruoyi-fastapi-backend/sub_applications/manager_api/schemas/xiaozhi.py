from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AgentModelsPayload(BaseModel):
    macAddress: str = Field(min_length=1)
    clientId: str = Field(min_length=1)
    selectedModule: Dict[str, Any] = Field(default_factory=dict)


class CorrectWordsPayload(BaseModel):
    macAddress: str = Field(min_length=1)


class ChatHistoryReportPayload(BaseModel):
    macAddress: str = Field(min_length=1)
    sessionId: str = Field(min_length=1)
    chatType: int
    content: str = ""
    reportTime: Optional[str] = None
    audioBase64: Optional[str] = None
