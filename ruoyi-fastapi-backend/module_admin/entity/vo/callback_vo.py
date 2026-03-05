from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Literal, Optional
from module_admin.annotation.pydantic_annotation import as_query


class CallbackModel(BaseModel):
    """
    回调地址信息表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    callback_id: Optional[int] = Field(default=None, description='回调ID')
    user_id: Optional[int] = Field(default=None, description='用户ID')
    url: Optional[str] = Field(default=None, description='回调地址')
    description: Optional[str] = Field(default=None, description='描述')
    status: Optional[Literal['0', '1']] = Field(default=None, description='状态（0正常 1停用）')
    create_by: Optional[str] = Field(default=None, description='创建者')
    create_time: Optional[datetime] = Field(default=None, description='创建时间')
    update_by: Optional[str] = Field(default=None, description='更新者')
    update_time: Optional[datetime] = Field(default=None, description='更新时间')


class CallbackQueryModel(CallbackModel):
    """
    回调地址管理不分页查询模型
    """

    begin_time: Optional[str] = Field(default=None, description='开始时间')
    end_time: Optional[str] = Field(default=None, description='结束时间')


@as_query
class CallbackPageQueryModel(CallbackQueryModel):
    """
    回调地址管理分页查询模型
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteCallbackModel(BaseModel):
    """
    删除回调地址模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    callback_ids: str = Field(description='需要删除的回调ID')
