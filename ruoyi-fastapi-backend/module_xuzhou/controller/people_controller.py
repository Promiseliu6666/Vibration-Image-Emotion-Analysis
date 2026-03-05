import traceback

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.entity.vo.people_vo import (
    PeopleModel,
    PeopleModelWithFeatures,
    PeoplePageQueryModel,
    FaceCompareModel,
)
from module_xuzhou.service.people_service import PeopleService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

people_controller = APIRouter(prefix='/people', dependencies=[Depends(unified_auth)])


@people_controller.get('/list', response_model=PageResponseModel, summary='获取人员列表')
@integration_log(
    title='获取人员列表',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_group_list(
    request: Request,
    people_page_query: PeoplePageQueryModel = Depends(PeoplePageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    group_list_result = await PeopleService.get_people_list_services(
        query_db, people_page_query, is_page=True, include_deleted=people_page_query.include_deleted
    )
    return ResponseUtil.success(data=group_list_result)


@people_controller.post('/', summary='添加人员')
@integration_log(
    title='添加人员',
    system_name='徐州人员管理系统',
    business_type=BusinessType.INSERT,
)
async def add_people(request: Request, people: PeopleModelWithFeatures, query_db: AsyncSession = Depends(get_db)):
    try:
        features: list = await PeopleService.extract_features(people.pics)
        people.features = features
        new_id = await PeopleService.add_people_services(query_db, people)
        return ResponseUtil.success(data={"new_person_id": new_id})
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'添加失败: {str(e)}')


@people_controller.get('/{people_id}', response_model=PeopleModel, summary='获取人员详细信息')
@integration_log(
    title='获取人员详细信息',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_people_detail(request: Request, people_id: int, query_db: AsyncSession = Depends(get_db)):
    people_detail_result = await PeopleService.people_detail_services(query_db, people_id)
    return ResponseUtil.success(data=people_detail_result)


@people_controller.put('/{people_id}', summary='编辑人员')
@integration_log(
    title='编辑人员',
    system_name='徐州人员管理系统',
    business_type=BusinessType.UPDATE,
)
async def edit_people(
    request: Request, people_id: int, people: PeopleModelWithFeatures, query_db: AsyncSession = Depends(get_db)
):
    try:
        if people.pics:
            features: list = await PeopleService.extract_features(people.pics)
            people.features = features
        await PeopleService.edit_people_services(query_db, people, people_id=people_id)
        return ResponseUtil.success(msg='修改成功')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'修改失败: {str(e)}')


@people_controller.delete('/{people_id}', summary='删除人员')
@integration_log(
    title='删除人员',
    system_name='徐州人员管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_people(request: Request, people_id: int, query_db: AsyncSession = Depends(get_db)):
    try:
        result = await PeopleService.delete_people_services(query_db, people_id)
        if result:
            return ResponseUtil.success(msg='删除成功')
        else:
            return ResponseUtil.error(msg='人员不存在')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'删除失败: {str(e)}')


@people_controller.post('/face-compare', summary='人脸比对')
@integration_log(
    title='人脸比对',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def face_compare(request: Request, face_data: FaceCompareModel, query_db: AsyncSession = Depends(get_db)):
    """
    人脸比对接口

    Args:
        request: 请求对象
        face_data: 包含图片数据和阈值的请求模型
        query_db: 数据库会话

    Returns:
        匹配结果列表，按相似度降序排列
    """

    try:
        result: list[dict] = await PeopleService.face_compare_services(
            query_db, face_data.image, face_data.group_id, face_data.threshold
        )

        if result:
            logger.info(f'有最匹配的结果')
            return ResponseUtil.success(data=result[0], msg=f'人脸匹配成功')
        else:
            logger.info('人脸比对完成，未找到匹配的人员')
            return ResponseUtil.success(data={}, msg='未找到匹配的人员')

    except Exception as e:
        logger.error(f'人脸比对失败: {str(e)}')
        logger.error(f'Traceback: {traceback.format_exc()}')
        return ResponseUtil.error(msg=f'人脸比对失败: {str(e)}')


@people_controller.post('/face-compare-all', summary='人脸比对')
@integration_log(
    title='人脸比对所有结果',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def face_compare_all(request: Request, face_data: FaceCompareModel, query_db: AsyncSession = Depends(get_db)):
    """
    人脸比对接口

    Args:
        request: 请求对象
        face_data: 包含图片数据和阈值的请求模型
        query_db: 数据库会话

    Returns:
        匹配结果列表，按相似度降序排列
    """

    try:
        result: list[dict] = await PeopleService.face_compare_services(
            query_db, face_data.image, face_data.group_id, face_data.threshold
        )

        if result:
            logger.info(f'有最匹配的结果')
            return ResponseUtil.success(data=result, msg=f'人脸匹配成功')
        else:
            logger.info('人脸比对完成，未找到匹配的人员')
            return ResponseUtil.success(data={}, msg='未找到匹配的人员')

    except Exception as e:
        logger.error(f'人脸比对失败: {str(e)}')
        logger.error(f'Traceback: {traceback.format_exc()}')
        return ResponseUtil.error(msg=f'人脸比对失败: {str(e)}')
