from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from typing import Optional, List, Union
from module_xuzhou.annotation.pydantic_annotation import as_query
from module_xuzhou.entity.vo.alg_vo import AlgModel
import json


class SceneModel(BaseModel):
    """
    场景信息表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    scene_id: Optional[int] = Field(default=None, description='场景ID')
    scene_name: Optional[str] = Field(default=None, description='场景名称')
    scene_serial: Optional[str] = Field(default=None, description='场景序列号')
    scene_algorithm: Optional[str] = Field(default=None, description='保存列表形式算法id数据')
    scene_algorithm_name: Optional[str] = Field(default=None, description='保存列表形式算法名称数据')
    scene_update_time: Optional[datetime] = Field(default=None, description='更新时间')


class SceneQueryModel(SceneModel):
    """
    场景信息不分页查询模型
    """

    begin_time: Optional[str] = Field(default=None, description='开始时间')
    end_time: Optional[str] = Field(default=None, description='结束时间')


@as_query
class ScenePageQueryModel(SceneQueryModel):
    """
    场景信息分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class EditSceneModel(SceneModel):
    """
    编辑场景信息模型
    """

    type: Optional[str] = Field(default=None, description='操作类型')


class DeleteSceneModel(BaseModel):
    """
    删除场景信息模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    scene_ids: str = Field(description='需要删除的场景ID')


class SceneDetailModel(SceneModel):
    """
    场景详细信息模型，包含算法详细信息
    """

    scene_id: Optional[int] = Field(default=None, description='场景ID')
    scene_name: Optional[str] = Field(default=None, description='场景名称')
    scene_serial: Optional[str] = Field(default=None, description='场景序列号')
    scene_algorithm: Optional[str] = Field(default=None, description='保存列表形式算法id数据')
    scene_algorithm_name: Optional[str] = Field(default=None, description='保存列表形式算法名称数据')
    scene_update_time: Optional[datetime] = Field(default=None, description='更新时间')
    alg_details: Optional[List[AlgModel]] = Field(default=None, description='算法详细信息列表')
