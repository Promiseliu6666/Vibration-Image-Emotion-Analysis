from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from typing import Optional, List, Union, Any
from module_xuzhou.annotation.pydantic_annotation import as_query
import json


class VideoModel(BaseModel):
    """
    视频信息表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    vid_id: Optional[int] = Field(default=None, description='视频ID')
    vid_name: Optional[str] = Field(default=None, description='视频名称')
    vid_serial: Optional[str] = Field(default=None, description='视频序列号')
    vid_type: Optional[str] = Field(default=None, description='视频类型')
    vid_scene: Optional[int] = Field(default=None, description='场景ID')
    vid_scene_name: Optional[str] = Field(default=None, description='场景名称')
    vid_algorithm_name: Optional[Union[str, List[str]]] = Field(default=None, description='算法名称')
    vid_algorithm: Optional[Union[str, List[Any]]] = Field(default=None, description='算法信息')

    @field_validator('vid_algorithm_name', mode='before')
    @classmethod
    def validate_algorithm_name(cls, v):
        if v is None:
            return v
        if isinstance(v, list):
            return json.dumps(v, ensure_ascii=False)
        return v

    @field_validator('vid_algorithm', mode='before')
    @classmethod
    def validate_algorithm(cls, v):
        if v is None:
            return v
        if isinstance(v, list):
            return json.dumps(v, ensure_ascii=False)
        return v

    vid_uri: Optional[str] = Field(default=None, description='视频URI')
    vid_update_time: Optional[datetime] = Field(default=None, description='更新时间')


class VideoQueryModel(VideoModel):
    """
    视频信息不分页查询模型
    """

    begin_time: Optional[str] = Field(default=None, description='开始时间')
    end_time: Optional[str] = Field(default=None, description='结束时间')


@as_query
class VideoPageQueryModel(VideoQueryModel):
    """
    视频信息分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class EditVideoModel(VideoModel):
    """
    编辑视频信息模型
    """

    type: Optional[str] = Field(default=None, description='操作类型')


class DeleteVideoModel(BaseModel):
    """
    删除视频信息模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    vid_ids: str = Field(description='需要删除的视频ID')
