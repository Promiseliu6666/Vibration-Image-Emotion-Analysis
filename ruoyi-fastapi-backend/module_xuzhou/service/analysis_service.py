import traceback
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.entity.vo.analysis_vo import (
    BinhuaAnalysisModel,
    BinhuaAnalysisUpdateModel,
    DeleteBinhuaAnalysisModel,
    BinhuaAnalysisPageQueryModel,
)
from module_xuzhou.error.analysis_error import AnalysisNotFoundError
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class BinhuaAnalysisService:
    @classmethod
    async def get_analysis_list_services(
        cls,
        query_db: AsyncSession,
        query_object: BinhuaAnalysisPageQueryModel,
        is_page: bool = True,
    ):
        analysis_list_result = await BinhuaAnalysisDao.get_analysis_list(
            query_db, query_object, is_page
        )
        # 自动补充 videoUrl 和 videoPath（更健壮）
        if isinstance(analysis_list_result, dict) and "records" in analysis_list_result:
            for item in analysis_list_result["records"]:
                video_path = item.get("videoPath") or item.get("video_path") or item.get("videoPath")
                if video_path and item.get("id"):
                    item["videoUrl"] = f"/analysis/video/{item['id']}"
                    item["videoPath"] = str(video_path).strip()
        return analysis_list_result

    @classmethod
    async def get_analysis_history_services(
        cls, query_db: AsyncSession, person_id: int
    ) -> List[Dict[str, Any]]:
        result = []
        for analysis in await BinhuaAnalysisDao.get_analysis_list_by_person_id(
            query_db, person_id=person_id
        ):
            item = CamelCaseUtil.transform_result(analysis)
            video_path = item.get("videoPath") or item.get("video_path")
            if video_path and item.get("id"):
                item["videoUrl"] = f"/analysis/video/{item['id']}"
                item["videoPath"] = str(video_path).strip()
            result.append(item)
        return result

    @classmethod
    async def get_analysis_detail_services(
        cls, query_db: AsyncSession, analysis_id: int
    ) -> BinhuaAnalysisModel:
        analysis = await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        )
        if analysis:
            item = CamelCaseUtil.transform_result(analysis)
            video_path = item.get("videoPath") or item.get("video_path")
            if video_path and item.get("id"):
                item["videoUrl"] = f"/analysis/video/{item['id']}"
                item["videoPath"] = str(video_path).strip()
            return BinhuaAnalysisModel(**item)
        return BinhuaAnalysisModel()

    @classmethod
    async def add_analysis_services(
        cls, query_db: AsyncSession, analysis: BinhuaAnalysisModel
    ) -> int:
        try:
            analysis_id = await BinhuaAnalysisDao.add_analysis_dao(query_db, analysis)
            await query_db.commit()
            logger.info(f'新增分析记录成功，ID: {analysis_id}')
            return analysis_id
        except Exception as e:
            await query_db.rollback()
            logger.error(f'新增分析记录失败: {e}')
            logger.error(traceback.format_exc())
            raise

    @classmethod
    async def edit_analysis_services(
        cls,
        query_db: AsyncSession,
        analysis_update: BinhuaAnalysisUpdateModel,
        analysis_id: int,
    ):
        if not await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        ):
            raise AnalysisNotFoundError('分析记录不存在')

        try:
            update_dict = analysis_update.model_dump(exclude_unset=True)
            if not update_dict:
                return
            update_dict["id"] = analysis_id
            await BinhuaAnalysisDao.edit_analysis_dao(query_db, update_dict)
            await query_db.commit()
            logger.info(f'更新分析记录成功，ID: {analysis_id}')
        except Exception as e:
            await query_db.rollback()
            logger.error(f'更新分析记录失败: {e}')
            logger.error(traceback.format_exc())
            raise

    @classmethod
    async def delete_analysis_services(
        cls, query_db: AsyncSession, analysis_id: int
    ) -> bool:
        if await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        ):
            try:
                await BinhuaAnalysisDao.delete_analysis_dao(query_db, analysis_id)
                await query_db.commit()
                logger.info(f'删除分析记录成功，ID: {analysis_id}')
                return True
            except Exception as e:
                await query_db.rollback()
                logger.error(f'删除分析记录失败: {e}')
                logger.error(traceback.format_exc())
                raise
        return False

    @classmethod
    async def batch_delete_analysis_services(
        cls, query_db: AsyncSession, delete_model: DeleteBinhuaAnalysisModel
    ):
        analysis_ids_str = delete_model.analysis_ids.strip()
        if not analysis_ids_str:
            return

        analysis_ids = [int(aid) for aid in analysis_ids_str.split(",") if aid.strip().isdigit()]
        if not analysis_ids:
            return

        try:
            await BinhuaAnalysisDao.batch_delete_analysis_dao(query_db, analysis_ids)
            await query_db.commit()
            logger.info(f'批量删除分析记录成功，IDs: {analysis_ids}')
        except Exception as e:
            await query_db.rollback()
            logger.error(f'批量删除分析记录失败: {e}')
            logger.error(traceback.format_exc())
            raise