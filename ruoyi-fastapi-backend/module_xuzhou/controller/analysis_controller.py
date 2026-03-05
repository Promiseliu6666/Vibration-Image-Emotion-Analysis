import traceback

from fastapi import APIRouter, Depends, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.entity.vo.analysis_vo import (
    BinhuaAnalysisModel,
    BinhuaAnalysisUpdateModel,
    DeleteBinhuaAnalysisModel,
    BinhuaAnalysisPageQueryModel,
)
from module_xuzhou.service.analysis_service import BinhuaAnalysisService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

analysis_controller = APIRouter(prefix='/analysis', dependencies=[Depends(unified_auth)])


@analysis_controller.get('/list', response_model=PageResponseModel, summary='获取分析记录列表')
@integration_log(
    title='获取分析记录列表',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_analysis_list(
    request: Request,
    query: BinhuaAnalysisPageQueryModel = Depends(BinhuaAnalysisPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    """
    分页查询分析记录列表
    支持 person_id、source 过滤
    """
    result = await BinhuaAnalysisService.get_analysis_list_services(
        query_db, query, is_page=True
    )
    return ResponseUtil.success(data=result)


@analysis_controller.get('/person/{person_id}', summary='获取指定人员的所有分析历史记录')
@integration_log(
    title='获取人员分析历史',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_analysis_history(
    request: Request,
    person_id: int,
    query_db: AsyncSession = Depends(get_db),
):
    """
    获取某人员的所有分析记录（按创建时间倒序）
    """
    result = await BinhuaAnalysisService.get_analysis_history_services(query_db, person_id)
    return ResponseUtil.success(data=result)


@analysis_controller.get('/{analysis_id}', response_model=BinhuaAnalysisModel, summary='获取分析记录详细信息')
@integration_log(
    title='获取分析记录详细信息',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_analysis_detail(
    request: Request,
    analysis_id: int,
    query_db: AsyncSession = Depends(get_db),
):
    result = await BinhuaAnalysisService.get_analysis_detail_services(query_db, analysis_id)
    return ResponseUtil.success(data=result)


@analysis_controller.post('/', summary='新增分析记录')
@integration_log(
    title='新增分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.INSERT,
)
async def add_analysis(
    request: Request,
    analysis: BinhuaAnalysisModel,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        new_id = await BinhuaAnalysisService.add_analysis_services(query_db, analysis)
        return ResponseUtil.success(data={"new_analysis_id": new_id}, msg='新增成功')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'新增分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'新增失败: {str(e)}')


@analysis_controller.put('/{analysis_id}', summary='编辑分析记录')
@integration_log(
    title='编辑分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.UPDATE,
)
async def edit_analysis(
    request: Request,
    analysis_id: int,
    analysis_update: BinhuaAnalysisUpdateModel,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        await BinhuaAnalysisService.edit_analysis_services(query_db, analysis_update, analysis_id)
        return ResponseUtil.success(msg='修改成功')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'编辑分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'修改失败: {str(e)}')


@analysis_controller.delete('/{analysis_id}', summary='删除分析记录')
@integration_log(
    title='删除分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_analysis(
    request: Request,
    analysis_id: int,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        result = await BinhuaAnalysisService.delete_analysis_services(query_db, analysis_id)
        if result:
            return ResponseUtil.success(msg='删除成功')
        else:
            return ResponseUtil.error(msg='分析记录不存在')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'删除分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'删除失败: {str(e)}')


@analysis_controller.post('/batch-delete', summary='批量删除分析记录')
@integration_log(
    title='批量删除分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.DELETE,
)
async def batch_delete_analysis(
    request: Request,
    delete_model: DeleteBinhuaAnalysisModel,
    query_db: AsyncSession = Depends(get_db),
):
    try:
        await BinhuaAnalysisService.batch_delete_analysis_services(query_db, delete_model)
        return ResponseUtil.success(msg='批量删除成功')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'批量删除分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'批量删除失败: {str(e)}')