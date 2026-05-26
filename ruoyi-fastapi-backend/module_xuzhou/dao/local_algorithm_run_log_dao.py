from datetime import datetime

from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.entity.do.local_algorithm_run_log_do import LocalAlgorithmRunLog
from module_xuzhou.entity.vo.local_algorithm_run_log_vo import LocalAlgorithmRunLogModel, LocalAlgorithmRunLogQueryModel
from utils.page_util import PageUtil


class LocalAlgorithmRunLogDao:

    @classmethod
    async def create(cls, db: AsyncSession, model: LocalAlgorithmRunLogModel) -> int:
        record = LocalAlgorithmRunLog(
            vid_id=model.vid_id,
            algorithm_code=model.algorithm_code,
            algorithm_name=model.algorithm_name,
            status=model.status,
            start_time=model.start_time,
            end_time=model.end_time,
            error_message=model.error_message,
        )
        db.add(record)
        await db.flush()
        return record.id

    @classmethod
    async def update_status(
        cls,
        db: AsyncSession,
        run_id: int,
        status: str,
        end_time: datetime = None,
        error_message: str = None,
    ):
        values = {"status": status}
        if end_time is not None:
            values["end_time"] = end_time
        if error_message is not None:
            values["error_message"] = error_message
        await db.execute(
            update(LocalAlgorithmRunLog)
            .where(LocalAlgorithmRunLog.id == run_id)
            .values(values)
        )

    @classmethod
    async def list_by_vid(
        cls, db: AsyncSession, query: LocalAlgorithmRunLogQueryModel, is_page: bool = True
    ):
        stmt = (
            select(LocalAlgorithmRunLog)
            .where(LocalAlgorithmRunLog.vid_id == query.vid_id)
            .order_by(desc(LocalAlgorithmRunLog.start_time))
        )
        return await PageUtil.paginate(db, stmt, query.page_num, query.page_size, is_page)

    @classmethod
    async def get_latest_running(cls, db: AsyncSession, vid_id: int) -> LocalAlgorithmRunLog | None:
        result = await db.execute(
            select(LocalAlgorithmRunLog)
            .where(
                LocalAlgorithmRunLog.vid_id == vid_id,
                LocalAlgorithmRunLog.status == "running",
            )
            .order_by(desc(LocalAlgorithmRunLog.start_time))
            .limit(1)
        )
        return result.scalars().first()
