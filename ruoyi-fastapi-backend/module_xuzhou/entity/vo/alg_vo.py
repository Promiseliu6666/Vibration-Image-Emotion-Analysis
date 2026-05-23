from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Optional
from module_xuzhou.annotation.pydantic_annotation import as_query


class AlgModel(BaseModel):
    """
    算法信息表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    alg_id: Optional[int] = Field(default=None, description='算法ID')
    alg_name: Optional[str] = Field(default=None, description='算法名称')
    alg_version: Optional[str] = Field(default=None, description='算法版本')
    alg_serial: Optional[str] = Field(default=None, description='算法序列号')
    alg_common: Optional[str] = Field(default=None, description='算法通用字段')
    alg_default_conf: Optional[str] = Field(default=None, description='算法默认配置(JSON字符串)')
    alg_weight_path: Optional[str] = Field(default=None, description='算法权重文件路径')
    alg_runtime_type: str = Field(default='external_box', description='运行位置: local/external_box')
    alg_enabled: bool = Field(default=True, description='是否启用')
    alg_update_time: Optional[datetime] = Field(default=None, description='更新时间')


class AlgQueryModel(AlgModel):
    """
    算法信息不分页查询模型
    """

    begin_time: Optional[str] = Field(default=None, description='开始时间')
    end_time: Optional[str] = Field(default=None, description='结束时间')


@as_query
class AlgPageQueryModel(AlgQueryModel):
    """
    算法信息分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class EditAlgModel(AlgModel):
    """
    编辑算法信息模型
    """

    type: Optional[str] = Field(default=None, description='操作类型')


class DeleteAlgModel(BaseModel):
    """
    删除算法信息模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    alg_ids: str = Field(description='需要删除的算法ID')
