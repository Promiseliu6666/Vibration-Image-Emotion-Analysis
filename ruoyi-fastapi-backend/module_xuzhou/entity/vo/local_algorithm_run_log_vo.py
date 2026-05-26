from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class LocalAlgorithmRunLogModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
    )

    id: Optional[int] = Field(default=None, description='主键')
    vid_id: int = Field(description='摄像头ID')
    algorithm_code: str = Field(description='算法编码')
    algorithm_name: str = Field(default='', description='算法名称')
    status: str = Field(default='running', description='running/completed/failed/stopped')
    start_time: datetime = Field(description='启动时间')
    end_time: Optional[datetime] = Field(default=None, description='结束时间')
    error_message: Optional[str] = Field(default=None, description='错误信息')
    create_time: Optional[datetime] = Field(default=None, description='创建时间')


class LocalAlgorithmRunLogQueryModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    vid_id: int = Field(description='摄像头ID')
    page_num: int = Field(default=1, description='页码')
    page_size: int = Field(default=20, description='每页条数')
