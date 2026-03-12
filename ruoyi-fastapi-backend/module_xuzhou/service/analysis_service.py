import io
import traceback
import pandas as pd
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
from module_xuzhou.error.analysis_error import AnalysisNotFoundError
from utils.common_util import CamelCaseUtil
from utils.excel_util import ExcelUtil
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
            return BinhuaAnalysisModel()

    @classmethod
    async def add_analysis_services(
            cls, query_db: AsyncSession, analysis: BinhuaAnalysisModel
    ) -> int:
        """
        新增分析记录
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
        更新分析记录
        """
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
        批量物理删除分析记录
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

    # ====================== 【已修复】导出方法 ======================
    @classmethod
    async def export_analysis_list_services(cls, analysis_list: List[Any]):
        """
        导出分析记录列表到Excel（最终稳定版）
        """

        # 1. ORM → dict（已确认是 dict，直接使用）
        converted_list: List[Dict[str, Any]] = []
        for item in analysis_list:
            dict_item = item if isinstance(item, dict) else CamelCaseUtil.transform_result(item)
            converted_list.append(dict_item)

        analysis_list = converted_list

        # ==================== 字段映射 ====================
        mapping_dict = {
            'id': 'ID',
            'source': '视频来源',
            'personName': '人名',
            'personId': '人员ID',
            'e1': '攻击性', 'e2': '压力', 'e3': '焦虑', 'e4': '可疑', 'e5': '平衡',
            'e6': '魅力', 'e7': '能量', 'e8': '自我调节', 'e9': '抑制', 'e10': '神经质',
            'e11': '抑郁', 'e12': '幸福', 'e13': '外向性', 'e14': '稳定性',
            'happinessIndex': '幸福指数',
            'happinessLevel': '幸福等级',
            'safetyRisk': '安全风险',
            'createTime': '创建时间',
        }

        # ==================== 关键修复：全部转为字符串 + 日期美化 ====================
        for item in analysis_list:
            for key in mapping_dict.keys():
                value = item.get(key)
                if value is None:
                    item[key] = ''
                elif isinstance(value, datetime):
                    item[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    item[key] = str(value)  # ← 强制转字符串，彻底解决显示问题

        # ==================== 生成 Excel ====================
        binary_data = ExcelUtil.export_list2excel(analysis_list, mapping_dict)

        return binary_data