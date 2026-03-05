from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.entity.vo.scene_vo import SceneModel, ScenePageQueryModel, DeleteSceneModel, SceneDetailModel
from module_xuzhou.service.scene_service import SceneService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

sceneController = APIRouter(prefix='/xuzhou/scene', dependencies=[Depends(unified_auth)])


@sceneController.get('/list', response_model=PageResponseModel, summary='获取场景列表')
@integration_log(
    title='获取场景列表',
    system_name='徐州场景管理系统',
    business_type=BusinessType.OTHER,
)
async def get_scene_list(
    request: Request,
    scene_page_query: ScenePageQueryModel = Depends(ScenePageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    """
    获取场景列表
    """
    scene_list_result = await SceneService.get_scene_list_services(query_db, scene_page_query, is_page=True)
    return ResponseUtil.success(model_content=scene_list_result)


@sceneController.post('/', summary='添加场景', include_in_schema=False)
@integration_log(
    title='添加场景',
    system_name='徐州场景管理系统',
    business_type=BusinessType.INSERT,
)
async def add_scene(request: Request, scene: SceneModel, query_db: AsyncSession = Depends(get_db)):
    """
    添加场景
    """
    # 设置更新时间
    scene.scene_update_time = datetime.now()
    # 调用Service层添加场景
    result = await SceneService.add_scene_services(query_db, scene)
    await query_db.commit()
    return ResponseUtil.success(msg='添加成功')


@sceneController.get(
    '/{scene_id}', response_model=SceneDetailModel, summary='获取场景详细信息', include_in_schema=False
)
@integration_log(
    title='获取场景详细信息',
    system_name='徐州场景管理系统',
    business_type=BusinessType.OTHER,
)
async def get_scene_detail(request: Request, scene_id: int, query_db: AsyncSession = Depends(get_db)):
    """
    获取场景详细信息
    """
    scene_detail_result = await SceneService.scene_detail_services(query_db, scene_id)
    return ResponseUtil.success(data=scene_detail_result)


@sceneController.put('/', summary='编辑场景', include_in_schema=False)
@integration_log(
    title='编辑场景',
    system_name='徐州场景管理系统',
    business_type=BusinessType.UPDATE,
)
async def edit_scene(request: Request, scene: SceneModel, query_db: AsyncSession = Depends(get_db)):
    """
    编辑场景
    """
    # 设置更新时间
    scene.scene_update_time = datetime.now()
    # 调用Service层编辑场景
    result = await SceneService.edit_scene_services(query_db, scene)
    if result:
        await query_db.commit()
        return ResponseUtil.success(msg='编辑成功')
    else:
        await query_db.rollback()
        return ResponseUtil.error(msg='编辑失败，场景不存在')


@sceneController.delete('/', summary='删除场景', include_in_schema=False)
@integration_log(
    title='删除场景',
    system_name='徐州场景管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_scene(request: Request, delete_scene: DeleteSceneModel, query_db: AsyncSession = Depends(get_db)):
    """
    删除场景
    """
    scene_id = int(delete_scene.scene_ids)
    result = await SceneService.delete_scene_services(query_db, scene_id)
    if result:
        await query_db.commit()
        return ResponseUtil.success(msg='删除成功')
    else:
        await query_db.rollback()
        return ResponseUtil.error(msg='删除失败，场景不存在')
