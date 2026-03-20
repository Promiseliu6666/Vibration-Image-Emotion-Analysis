import traceback
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.entity.vo.analysis_vo import (
    BinhuaAnalysisModel,
    BinhuaAnalysisUpdateModel,
    DeleteBinhuaAnalysisModel,
    BinhuaAnalysisPageQueryModel,
)
from module_xuzhou.error.analysis_error import AnalysisNotFoundError  # 假设已定义，如需可新增
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class BinhuaAnalysisService:
    """
    分析记录服务层（对应 binahua_analysis 表）
    提供 CRUD 及常见查询业务逻辑，与 PeopleService 风格保持高度一致
    """

    @classmethod
    async def get_analysis_list_services(
        cls,
        query_db: AsyncSession,
        query_object: BinhuaAnalysisPageQueryModel,
        is_page: bool = True,
    ):
        """
        分页查询分析记录列表
        """
        analysis_list_result = await BinhuaAnalysisDao.get_analysis_list(
            query_db, query_object, is_page
        )
        return analysis_list_result

    @classmethod
    async def get_analysis_history_services(
        cls, query_db: AsyncSession, person_id: int
    ) -> List[Dict[str, Any]]:
        """
        根据人员ID获取该人员的所有分析记录（按创建时间倒序）
        对应人员分析历史场景
        """
        result = []
        for analysis in await BinhuaAnalysisDao.get_analysis_list_by_person_id(
            query_db, person_id=person_id
        ):
            result.append(CamelCaseUtil.transform_result(analysis))
        return result

    @classmethod
    async def get_analysis_detail_services(
        cls, query_db: AsyncSession, analysis_id: int
    ) -> BinhuaAnalysisModel:
        """
        根据ID查询单个分析记录详情
        """
        analysis = await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        )
        if analysis:
            return BinhuaAnalysisModel(**CamelCaseUtil.transform_result(analysis))
        else:
            return BinhuaAnalysisModel()  # 返回空模型，类似 PeopleService 处理

    @classmethod
    async def add_analysis_services(
        cls, query_db: AsyncSession, analysis: BinhuaAnalysisModel
    ) -> int:
        """
        新增分析记录（通常由视频分析后调用）
        create_time 使用数据库默认值
        """
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
        """
        更新分析记录（支持部分更新，如手动校正幸福指数、风险等）
        """
        # 检查记录是否存在
        if not await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        ):
            raise AnalysisNotFoundError('分析记录不存在')

        try:
            # 只更新传入的字段
            update_dict = analysis_update.model_dump(exclude_unset=True)
            if not update_dict:
                return  # 无需更新

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
        """
        单条物理删除分析记录
        """
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
        """
        批量物理删除分析记录（支持前端传入逗号分隔的ID字符串）
        """
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