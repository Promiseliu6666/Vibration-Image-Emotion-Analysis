from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.entity.vo.alg_vo import AlgModel, AlgPageQueryModel
from module_xuzhou.service.alg_service import AlgService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

algorithmController = APIRouter(prefix='/xuzhou/algorithm', dependencies=[Depends(unified_auth)])


@algorithmController.get('/statistics', summary='获取统计信息', include_in_schema=False)
async def get_statistics(request: Request, query_db: AsyncSession = Depends(get_db)):
    """
    获取算法、场景、视频统计信息
    """
    statistics_result = await AlgService.get_statistics_services(query_db)
    return ResponseUtil.success(data=statistics_result)


@algorithmController.get('/charts', summary='获取表格统计信息', include_in_schema=False)
async def get_charts(request: Request, query_db: AsyncSession = Depends(get_db)):
    """
    获取表格统计信息
    """
    statistics_result = await AlgService.get_charts_services(query_db)
    return ResponseUtil.success(data=statistics_result)


@algorithmController.get('/list', response_model=PageResponseModel, summary='获取算法列表')
@integration_log(
    title='获取算法列表',
    system_name='徐州算法管理系统',
    business_type=BusinessType.OTHER,
)
async def get_algorithm_list(
    request: Request,
    alg_page_query: AlgPageQueryModel = Depends(AlgPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    """
    获取算法列表
    """
    alg_list_result = await AlgService.get_alg_list_services(query_db, alg_page_query, is_page=True)
    return ResponseUtil.success(model_content=alg_list_result)


@algorithmController.post('/', summary='添加算法', include_in_schema=False)
@integration_log(
    title='添加算法',
    system_name='徐州算法管理系统',
    business_type=BusinessType.INSERT,
)
async def add_algorithm(request: Request, alg: AlgModel, query_db: AsyncSession = Depends(get_db)):
    """
    添加算法
    """
    try:
        await AlgService.add_alg_services(query_db, alg)
        return ResponseUtil.success(msg='添加成功')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'添加失败: {e}')


@algorithmController.post('/upload-weight', summary='上传算法权重并创建版本')
@integration_log(
    title='上传算法权重',
    system_name='徐州算法管理系统',
    business_type=BusinessType.INSERT,
)
async def upload_algorithm_weight(
    request: Request,
    alg_name: str = Form(...),
    alg_serial: str = Form(...),
    alg_version: str = Form(...),
    alg_runtime_type: str = Form('external_box'),
    alg_default_conf: str = Form('{}'),
    file: UploadFile = File(...),
    query_db: AsyncSession = Depends(get_db),
):
    try:
        db_alg = await AlgService.upload_weight_services(
            query_db,
            alg_name=alg_name,
            alg_serial=alg_serial,
            alg_version=alg_version,
            alg_runtime_type=alg_runtime_type,
            alg_default_conf=alg_default_conf,
            upload_file=file,
        )
        return ResponseUtil.success(data=AlgModel.model_validate(db_alg).model_dump(by_alias=True), msg='上传成功')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'上传失败: {e}')


@algorithmController.get('/{alg_id}', response_model=AlgModel, summary='获取算法详细信息', include_in_schema=False)
@integration_log(
    title='获取算法详细信息',
    system_name='徐州算法管理系统',
    business_type=BusinessType.OTHER,
)
async def get_algorithm_detail(request: Request, alg_id: int, query_db: AsyncSession = Depends(get_db)):
    """
    获取算法详细信息
    """
    alg_detail_result = await AlgService.alg_detail_services(query_db, alg_id)
    return ResponseUtil.success(data=alg_detail_result)


@algorithmController.put('/', summary='编辑算法', include_in_schema=False)
@integration_log(
    title='编辑算法',
    system_name='徐州算法管理系统',
    business_type=BusinessType.UPDATE,
)
async def edit_algorithm(request: Request, alg: AlgModel, query_db: AsyncSession = Depends(get_db)):
    """
    编辑算法
    """
    await AlgService.edit_alg_services(query_db, alg)
    return ResponseUtil.success(msg='编辑成功')


@algorithmController.delete('/{alg_id}', summary='删除算法', include_in_schema=False)
@integration_log(
    title='删除算法',
    system_name='徐州算法管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_algorithm(request: Request, alg_id: int, query_db: AsyncSession = Depends(get_db)):
    """
    删除算法
    """
    result = await AlgService.delete_alg_services(query_db, alg_id)
    if result:
        return ResponseUtil.success(msg='删除成功')
    else:
        return ResponseUtil.error(msg='算法不存在')
