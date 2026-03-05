from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_xuzhou.annotation.pydantic_annotation import as_query


class PeopleModel(BaseModel):
    """
    人脸模型表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    id: Optional[int] = Field(default=None, description='人员ID')
    name: Optional[str] = Field(default=None, description='人员编号')
    group_id: Optional[int] = Field(default=None, description='组id')
    created_time: Optional[datetime] = Field(default=None, description='创建时间')
    updated_time: Optional[datetime] = Field(default=None, description='更新时间')
    pics: Optional[str] = Field(default=None, description='图片')
    is_deleted: bool = Field(default=False, description='是否删除')
    deleted_time: Optional[datetime] = Field(default=None, description='删除时间')


class PeopleModelWithFeatures(PeopleModel):
    features: Optional[List] = Field(default_factory=list, description='特征值')


@as_query
class PeopleQueryModel(PeopleModel):
    """
    人脸模型分页查询
    """

    include_deleted: bool = False


@as_query
class PeoplePageQueryModel(PeopleQueryModel):
    """
    人脸模型分页查询
    """

    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')
    group: Optional[int] = Field(default=None, description='分组ID，为空表示查询全部分组')


class DeletePeopleModel(BaseModel):
    """
    删除人脸模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    people_ids: str = Field(description='需要删除的人员ID')


class FaceCompareModel(BaseModel):
    """
    人脸比对请求模型
    """

    group_id: int = Field(description='要查询的分组id')
    model_config = ConfigDict(alias_generator=to_camel)

    image: str = Field(description='base64编码的图片数据')
    threshold: Optional[float] = Field(default=0.3, description='相似度阈值，默认0.3', ge=0.0, le=1.0)
