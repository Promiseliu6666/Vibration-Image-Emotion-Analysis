from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_xuzhou.annotation.pydantic_annotation import as_query


class BinhuaAnalysisModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True
    )

    id: Optional[int] = Field(default=None, description='ID')
    source: str = Field(description='视频来源')
    person_name: str = Field(description='人名')
    person_id: Optional[int] = Field(default=None, description='人员ID')

    video_path: Optional[str] = Field(default=None, description='分析视频文件路径')
    box_serial: Optional[str] = Field(default=None, description='所属盒子序列号')

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
    e11: float = Field(default=0.0, description='e11')
    e12: float = Field(default=0.0, description='e12')
    e13: float = Field(default=0.0, description='e13')
    e14: float = Field(default=0.0, description='e14')
    happiness_index: float = Field(default=0.0, description='幸福指数')
    happiness_level: Optional[str] = Field(default=None, description='幸福等级')
    safety_risk: Optional[str] = Field(default=None, description='安全风险')
    create_time: Optional[datetime] = Field(default=None, description='记录创建时间')


class BinhuaAnalysisUpdateModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )

    source: Optional[str] = Field(default=None, description='视频来源')
    person_name: Optional[str] = Field(default=None, description='人名')
    person_id: Optional[int] = Field(default=None, description='人员ID')
    video_path: Optional[str] = Field(default=None, description='分析视频文件路径')
    box_serial: Optional[str] = Field(default=None, description='所属盒子序列号')
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
    e11: Optional[float] = Field(default=None, description='e11')
    e12: Optional[float] = Field(default=None, description='e12')
    e13: Optional[float] = Field(default=None, description='e13')
    e14: Optional[float] = Field(default=None, description='e14')
    happiness_index: Optional[float] = Field(default=None, description='幸福指数')
    happiness_level: Optional[str] = Field(default=None, description='幸福等级')
    safety_risk: Optional[str] = Field(default=None, description='安全风险')


class DeleteBinhuaAnalysisModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    analysis_ids: str = Field(description='需要删除的分析记录ID，多个用逗号分隔，例如 "1,2,3"')


class ExportPersonReportModel(BaseModel):
    """导出个人分析报告 PDF 请求体"""
    model_config = ConfigDict(populate_by_name=True)
    analysis_id: int = Field(alias='analysisId', description='分析记录ID')
    radar_image: str = Field(alias='radarImage', description='雷达图 base64 PNG')


@as_query
class BinhuaAnalysisPageQueryModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    page_num: int = Field(default=1, alias='pageNum', description='当前页码')
    page_size: int = Field(default=10, alias='pageSize', description='每页记录数')
    person_id: Optional[int] = Field(default=None, alias='personId', description='人员ID')
    person_name: Optional[str] = Field(default=None, alias='personName', description='人名（模糊搜索）')
    source: Optional[str] = Field(default=None, description='视频来源')
    start_time: Optional[datetime] = Field(default=None, alias='startTime', description='开始时间')
    end_time: Optional[datetime] = Field(default=None, alias='endTime', description='结束时间')