from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_xuzhou.annotation.pydantic_annotation import as_query


class GroupModel(BaseModel):
    """
    人员组表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    id: Optional[int] = Field(default=None, description='组ID')
    name: str = Field(default='', description='组名称')
    # members: Optional[List[PeopleModel]] = Field(default=None, description='组成员')


class GroupInfoModel(GroupModel):
    created_time: Optional[datetime] = Field(default=None, description='创建时间')
    updated_time: Optional[datetime] = Field(default=None, description='更新时间')
    is_deleted: bool = False
    deleted_time: Optional[datetime] = Field(default=None, description='删除时间')


@as_query
class GroupQueryModel(GroupModel):
    include_deleted: bool = False


@as_query
class GroupPageQueryModel(GroupQueryModel):
    """
    人员组分页查询
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class DeleteGroupModel(BaseModel):
    """
    删除人员组
    """

    model_config = ConfigDict(alias_generator=to_camel)

    group_ids: str = Field(description='需要删除的组ID')
