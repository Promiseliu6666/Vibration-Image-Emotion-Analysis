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
        return (await db.execute(select(BinhuaAnalysis).where(BinhuaAnalysis.id == analysis_id))).scalars().first()

    @classmethod
    async def get_analysis_list_by_person_id(
        cls, db: AsyncSession, person_id: int
    ) -> Sequence[BinhuaAnalysis]:
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
        person_id_cond = True
        if query_object.person_id is not None:
            person_id_cond = (BinhuaAnalysis.person_id == query_object.person_id)

        person_name_cond = True
        if query_object.person_name and query_object.person_name.strip():
            person_name_cond = BinhuaAnalysis.person_name.like(f'%{query_object.person_name.strip()}%')

        source_cond = True
        if query_object.source and query_object.source.strip():
            source_cond = BinhuaAnalysis.source.like(f'%{query_object.source.strip()}%')

        time_cond = True
        if query_object.start_time is not None and query_object.end_time is not None:
            time_cond = BinhuaAnalysis.create_time.between(query_object.start_time, query_object.end_time)
        elif query_object.start_time is not None:
            time_cond = BinhuaAnalysis.create_time >= query_object.start_time
        elif query_object.end_time is not None:
            time_cond = BinhuaAnalysis.create_time <= query_object.end_time

        query = (
            select(BinhuaAnalysis)
            .where(
                person_id_cond,
                person_name_cond,
                source_cond,
                time_cond,
            )
            .order_by(BinhuaAnalysis.create_time.desc())
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def add_analysis_dao(cls, db: AsyncSession, analysis: BinhuaAnalysisModel):
        db_analysis = BinhuaAnalysis(
            **analysis.model_dump(exclude={'id', 'create_time'})
        )
        db.add(db_analysis)
        await db.flush()

        return db_analysis.id

    @classmethod
    async def edit_analysis_dao(cls, db: AsyncSession, analysis_dict: dict):
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
        await db.execute(
            delete(BinhuaAnalysis).where(BinhuaAnalysis.id == analysis_id)
        )

    @classmethod
    async def batch_delete_analysis_dao(cls, db: AsyncSession, analysis_ids: list[int]):
        if not analysis_ids:
            return
        await db.execute(
            delete(BinhuaAnalysis).where(BinhuaAnalysis.id.in_(analysis_ids))
        )