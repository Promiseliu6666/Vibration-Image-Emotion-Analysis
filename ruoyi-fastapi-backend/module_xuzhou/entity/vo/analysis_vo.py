from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_xuzhou.annotation.pydantic_annotation import as_query


class BinhuaAnalysisModel(BaseModel):
    """
    分析数据表对应pydantic模型（用于读取/返回）
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True  # ← 新增：允许通过 alias 填充字段
    )

    id: Optional[int] = Field(default=None, description='ID')
    source: str = Field(description='视频来源')
    person_name: str = Field(description='人名')
    person_id: Optional[int] = Field(default=None, description='人员ID')
    e1: float = Field(default=0.0, description='e1')
    e2: float = Field(default=0.0, description='e2')
    e3: float = Field(default=0.0, description='e3')
    e4: float = Field(default=0.0, description='e4')
    e5: float = Field(default=0.0, description='e5')
    e6: float = Field(default=0.0, description='e6')
    e7: float = Field(default=0.0, description='e7')
    e8: float = Field(default=0.0, description='e8')
    e9: float = Field(default=0.0, description='e9')
    e10: float = Field(default=0.0, description='e10')
    happiness_index: float = Field(default=0.0, description='幸福指数')
    happiness_level: Optional[str] = Field(default=None, description='幸福等级')
    safety_risk: Optional[str] = Field(default=None, description='安全风险')
    create_time: Optional[datetime] = Field(default=None, description='记录创建时间')


class BinhuaAnalysisUpdateModel(BaseModel):
    """
    更新分析数据模型（支持部分更新，所有字段可选）
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True  # ← 新增
    )

    source: Optional[str] = Field(default=None, description='视频来源')
    person_name: Optional[str] = Field(default=None, description='人名')
    person_id: Optional[int] = Field(default=None, description='人员ID')
    e1: Optional[float] = Field(default=None, description='e1')
    e2: Optional[float] = Field(default=None, description='e2')
    e3: Optional[float] = Field(default=None, description='e3')
    e4: Optional[float] = Field(default=None, description='e4')
    e5: Optional[float] = Field(default=None, description='e5')
    e6: Optional[float] = Field(default=None, description='e6')
    e7: Optional[float] = Field(default=None, description='e7')
    e8: Optional[float] = Field(default=None, description='e8')
    e9: Optional[float] = Field(default=None, description='e9')
    e10: Optional[float] = Field(default=None, description='e10')
    happiness_index: Optional[float] = Field(default=None, description='幸福指数')
    happiness_level: Optional[str] = Field(default=None, description='幸福等级')
    safety_risk: Optional[str] = Field(default=None, description='安全风险')


class DeleteBinhuaAnalysisModel(BaseModel):
    """
    删除分析数据模型（批量删除）
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True  # ← 新增
    )

    analysis_ids: str = Field(description='需要删除的分析记录ID，多个用逗号分隔，例如 "1,2,3"')


@as_query
class BinhuaAnalysisPageQueryModel(BaseModel):
    """
    分析数据分页查询
    支持前端直接传 camelCase 参数（pageNum、pageSize、personId、source）
    """

    model_config = ConfigDict(populate_by_name=True)  # ← 核心：允许 alias 填充

    page_num: int = Field(default=1, alias='pageNum', description='当前页码')  # ← 添加 alias
    page_size: int = Field(default=10, alias='pageSize', description='每页记录数')  # ← 添加 alias
    person_id: Optional[int] = Field(default=None, alias='personId', description='人员ID')  # ← 添加 alias
    source: Optional[str] = Field(default=None, description='视频来源')  # source 一致，无需 alias