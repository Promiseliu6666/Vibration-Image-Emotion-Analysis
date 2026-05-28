from datetime import datetime, timedelta
from typing import Sequence

from sqlalchemy import select, update, delete, func, text
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

    # ==================== 数据统计聚合 ====================

    @classmethod
    async def get_stats_7days(
        cls, db: AsyncSession
    ) -> dict:
        """近7天总体态势：总数、平均幸福指数、安全风险分布、日趋势"""
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        base = select(BinhuaAnalysis).where(BinhuaAnalysis.create_time >= week_ago)
        result = await db.execute(
            select(
                func.count(BinhuaAnalysis.id),
                func.coalesce(func.avg(BinhuaAnalysis.happiness_index), 0),
                func.coalesce(func.avg(BinhuaAnalysis.e1), 0),
                func.coalesce(func.avg(BinhuaAnalysis.e2), 0),
                func.coalesce(func.avg(BinhuaAnalysis.e3), 0),
                func.coalesce(func.avg(BinhuaAnalysis.e4), 0),
                func.coalesce(func.avg(BinhuaAnalysis.e12), 0),
                func.coalesce(func.avg(BinhuaAnalysis.e14), 0),
            ).select_from(base.subquery())
        )
        row = result.one()
        total, avg_happy, avg_e1, avg_e2, avg_e3, avg_e4, avg_e12, avg_e14 = row

        # 安全风险分布
        risk_result = await db.execute(
            select(
                BinhuaAnalysis.safety_risk,
                func.count(BinhuaAnalysis.id),
            ).where(
                BinhuaAnalysis.create_time >= week_ago,
                BinhuaAnalysis.safety_risk.isnot(None),
                BinhuaAnalysis.safety_risk != '',
            ).group_by(BinhuaAnalysis.safety_risk)
        )
        risk_dist = {row[0]: row[1] for row in risk_result.all()}

        # 日趋势（每天数量 + 平均幸福指数）
        daily_rows = await db.execute(
            select(
                func.date(BinhuaAnalysis.create_time),
                func.count(BinhuaAnalysis.id),
                func.coalesce(func.avg(BinhuaAnalysis.happiness_index), 0),
            ).where(
                BinhuaAnalysis.create_time >= week_ago,
            ).group_by(func.date(BinhuaAnalysis.create_time)).order_by(func.date(BinhuaAnalysis.create_time))
        )
        daily_trend = [
            {"date": str(row[0]), "count": row[1], "avg_happiness": round(float(row[2]), 1)}
            for row in daily_rows.all()
        ]

        return {
            "total": int(total),
            "avg_happiness": round(float(avg_happy), 1),
            "avg_e1_aggression": round(float(avg_e1), 1),
            "avg_e2_stress": round(float(avg_e2), 1),
            "avg_e3_anxiety": round(float(avg_e3), 1),
            "avg_e4_suspicion": round(float(avg_e4), 1),
            "avg_e12_happiness": round(float(avg_e12), 1),
            "avg_e14_stability": round(float(avg_e14), 1),
            "risk_distribution": risk_dist,
            "daily_trend": daily_trend,
        }

    @classmethod
    async def get_top3_high_risk(
        cls, db: AsyncSession, days: int = 7
    ) -> list[dict]:
        """高风险人员 TOP3：按出现次数和平均幸福指数排序"""
        since = datetime.now() - timedelta(days=days)
        rows = await db.execute(
            select(
                BinhuaAnalysis.person_name,
                BinhuaAnalysis.person_id,
                func.count(BinhuaAnalysis.id).label("count"),
                func.coalesce(func.avg(BinhuaAnalysis.happiness_index), 0).label("avg_happy"),
                func.coalesce(func.avg(BinhuaAnalysis.e4), 0).label("avg_e4"),
                func.coalesce(func.avg(BinhuaAnalysis.e2), 0).label("avg_e2"),
            ).where(
                BinhuaAnalysis.create_time >= since,
                BinhuaAnalysis.person_name.isnot(None),
                BinhuaAnalysis.person_name != '',
            ).group_by(
                BinhuaAnalysis.person_name, BinhuaAnalysis.person_id
            ).order_by(
                func.avg(BinhuaAnalysis.happiness_index).asc()
            ).limit(3)
        )
        return [
            {
                "person_name": row[0],
                "person_id": row[1],
                "analysis_count": int(row[2]),
                "avg_happiness": round(float(row[3]), 1),
                "avg_e4_suspicion": round(float(row[4]), 1),
                "avg_e2_stress": round(float(row[5]), 1),
            }
            for row in rows.all()
        ]

    @classmethod
    async def get_wow_comparison(
        cls, db: AsyncSession
    ) -> dict:
        """周环比变化：本周 vs 上周关键指标对比"""
        now = datetime.now()
        this_week_start = now - timedelta(days=7)
        last_week_start = now - timedelta(days=14)
        last_week_end = now - timedelta(days=7)

        async def _agg(start, end):
            result = await db.execute(
                select(
                    func.count(BinhuaAnalysis.id),
                    func.coalesce(func.avg(BinhuaAnalysis.happiness_index), 0),
                    func.coalesce(func.avg(BinhuaAnalysis.e1), 0),
                    func.coalesce(func.avg(BinhuaAnalysis.e2), 0),
                    func.coalesce(func.avg(BinhuaAnalysis.e3), 0),
                    func.coalesce(func.avg(BinhuaAnalysis.e12), 0),
                    func.coalesce(func.avg(BinhuaAnalysis.e14), 0),
                ).where(
                    BinhuaAnalysis.create_time >= start,
                    BinhuaAnalysis.create_time < end,
                )
            )
            return result.one()

        this_week = await _agg(this_week_start, now)
        last_week = await _agg(last_week_start, last_week_end)

        def _pct_change(curr, prev):
            if prev and prev != 0:
                return round((curr - prev) / prev * 100, 1)
            return None

        return {
            "this_week": {
                "total": int(this_week[0]),
                "avg_happiness": round(float(this_week[1]), 1),
                "avg_e1": round(float(this_week[2]), 1),
                "avg_e2": round(float(this_week[3]), 1),
                "avg_e3": round(float(this_week[4]), 1),
                "avg_e12": round(float(this_week[5]), 1),
                "avg_e14": round(float(this_week[6]), 1),
            },
            "last_week": {
                "total": int(last_week[0]),
                "avg_happiness": round(float(last_week[1]), 1),
                "avg_e1": round(float(last_week[2]), 1),
                "avg_e2": round(float(last_week[3]), 1),
                "avg_e3": round(float(last_week[4]), 1),
                "avg_e12": round(float(last_week[5]), 1),
                "avg_e14": round(float(last_week[6]), 1),
            },
            "changes": {
                "total_pct": _pct_change(this_week[0], last_week[0]),
                "happiness_pct": _pct_change(this_week[1], last_week[1]),
                "e1_pct": _pct_change(this_week[2], last_week[2]),
                "e2_stress_pct": _pct_change(this_week[3], last_week[3]),
                "e3_anxiety_pct": _pct_change(this_week[4], last_week[4]),
                "e12_pct": _pct_change(this_week[5], last_week[5]),
                "e14_stability_pct": _pct_change(this_week[6], last_week[6]),
            },
        }