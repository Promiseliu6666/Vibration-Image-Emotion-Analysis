from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Optional, Dict, Any


class AlarmModel(BaseModel):
    """
    预警消息模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    alarm_id: Optional[int] = Field(default=None, description='预警ID')
    vid_id: Optional[int] = Field(default=None, description='视频ID')
    vid_name: Optional[str] = Field(default=None, description='视频名称')
    vid_serial: Optional[str] = Field(default=None, description='视频序列号')
    alarm_code: Optional[str] = Field(default=None, description='预警编码')
    alarm_time: Optional[datetime] = Field(default=None, description='预警时间')
    alarm_image: Optional[str] = Field(default=None, description='预警图片')
    alarm_content: Optional[str] = Field(default=None, description='预警内容JSON')
    push_result: Optional[str] = Field(default=None, description='推送结果JSON')
    create_time: Optional[datetime] = Field(default=None, description='创建时间')


from module_xuzhou.annotation.pydantic_annotation import as_query

@as_query
class AlarmPageQueryModel(BaseModel):
    """
    预警消息分页查询模型
    """
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')
    vid_id: Optional[int] = Field(default=None, description='视频ID')
    alarm_code: Optional[str] = Field(default=None, description='预警编码')
