import json
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.entity.do.analysis_do import BinhuaAnalysis
from module_xuzhou.entity.vo.analysis_vo import BinhuaAnalysisPageQueryModel, BinhuaAnalysisModel
from utils.page_util import PageUtil


class BinhuaAnalysisDao:
    @classmethod
    async def get_analysis_detail_by_id(cls, db: AsyncSession, analysis_id: int) -> BinhuaAnalysis | None:
        """
        根据ID查询单个分析记录详情
        """
        return (await db.execute(select(BinhuaAnalysis).where(BinhuaAnalysis.id == analysis_id))).scalars().first()

    @classmethod
    async def get_analysis_list_by_person_id(
        cls, db: AsyncSession, person_id: int
    ) -> Sequence[BinhuaAnalysis]:
        """
        根据人员ID查询该人员的所有分析记录（按创建时间倒序）
        """
        return (
            await db.execute(
                select(BinhuaAnalysis)
                .where(BinhuaAnalysis.person_id == person_id)
                .order_by(BinhuaAnalysis.create_time.desc())
            )
        ).scalars().all()

    @classmethod
    async def get_analysis_list(
        cls, db: AsyncSession, query_object: BinhuaAnalysisPageQueryModel, is_page: bool = True
    ):
        """
        分页查询分析记录列表
        支持过滤：
          - person_id（精确匹配，仅当非 None 时生效）
          - source（模糊匹配，仅当去空格后非空时生效）
        排序：创建时间倒序（最新记录优先）
        """
        # === 优化 person_id 条件：仅当非 None 时添加 ===
        person_id_cond = True
        if query_object.person_id is not None:
            person_id_cond = (BinhuaAnalysis.person_id == query_object.person_id)

        # === 优化 source 条件：去空格后非空才进行模糊匹配，避免空字符串/纯空格干扰 ===
        source_cond = True
        if query_object.source and query_object.source.strip():
            source_cond = BinhuaAnalysis.source.like(f'%{query_object.source.strip()}%')

        query = (
            select(BinhuaAnalysis)
            .where(
                person_id_cond,
                source_cond,
            )
            .order_by(BinhuaAnalysis.create_time.desc())
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def add_analysis_dao(cls, db: AsyncSession, analysis: BinhuaAnalysisModel):
        """
        新增分析记录
        """
        db_analysis = BinhuaAnalysis(
            **analysis.model_dump(exclude={'id', 'create_time'})  # id 自增，create_time 有数据库默认值
        )
        db.add(db_analysis)
        await db.flush()

        return db_analysis.id

    @classmethod
    async def edit_analysis_dao(cls, db: AsyncSession, analysis_dict: dict):
        """
        更新分析记录（支持部分更新）
        修复了 people_dao 中 edit 的全表更新 bug，必须传入包含 'id' 的 dict
        """
        if 'id' not in analysis_dict:
            raise ValueError("更新分析记录时必须提供 'id'")

        analysis_id = analysis_dict.pop('id')
        await db.execute(
            update(BinhuaAnalysis)
            .where(BinhuaAnalysis.id == analysis_id)
            .values(analysis_dict)
        )

    @classmethod
    async def delete_analysis_dao(cls, db: AsyncSession, analysis_id: int):
        """
        单条物理删除分析记录（表中无软删除字段）
        """
        await db.execute(
            delete(BinhuaAnalysis).where(BinhuaAnalysis.id == analysis_id)
        )

    @classmethod
    async def batch_delete_analysis_dao(cls, db: AsyncSession, analysis_ids: list[int]):
        """
        批量物理删除分析记录（支持 DeleteBinhuaAnalysisModel 中的逗号分隔 IDs）
        """
        if not analysis_ids:
            return
        await db.execute(
            delete(BinhuaAnalysis).where(BinhuaAnalysis.id.in_(analysis_ids))
        )