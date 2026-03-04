from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.entity.vo.group_vo import GroupPageQueryModel, GroupModel
from module_xuzhou.entity.vo.people_vo import PeoplePageQueryModel
from module_xuzhou.error.group_error import GroupNotFoundError
from module_xuzhou.service.group_service import GroupService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

group_controller = APIRouter(prefix='/group', dependencies=[Depends(unified_auth)], include_in_schema=False)


@group_controller.get('/list', response_model=PageResponseModel, summary='获取人员组列表')
@integration_log(
    title='获取人员组列表',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.OTHER,
)
async def get_group_list(
    request: Request,
    group_page_query: GroupPageQueryModel = Depends(GroupPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    group_list_result = await GroupService.get_group_list_services(
        query_db, group_page_query, is_page=True, include_deleted=group_page_query.include_deleted
    )
    return ResponseUtil.success(data=group_list_result)


@group_controller.post('/', summary='添加人员组')
@integration_log(
    title='添加人员组',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.INSERT,
)
async def add_group(request: Request, group: GroupModel, query_db: AsyncSession = Depends(get_db)):
    try:
        await GroupService.add_group_services(query_db, group)
        return ResponseUtil.success(msg='添加成功')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'添加失败: {str(e)}')


@group_controller.get('/{group_id}', response_model=GroupModel, summary='获取人员组详细信息')
@integration_log(
    title='获取人员组详细信息',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.OTHER,
)
async def get_group_detail(request: Request, group_id: int, query_db: AsyncSession = Depends(get_db)):
    try:
        group_detail_result = await GroupService.group_detail_services(query_db, group_id)
        return ResponseUtil.success(data=group_detail_result)
    except GroupNotFoundError as err:
        return ResponseUtil.error(msg=str(err))


@group_controller.put('/{group_id}', summary='编辑人员组')
@integration_log(
    title='编辑人员组',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.UPDATE,
)
async def edit_group(request: Request, group_id: int, group: GroupModel, query_db: AsyncSession = Depends(get_db)):
    try:
        await GroupService.edit_group_services(group_id, query_db, group)
        return ResponseUtil.success(msg='修改成功')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'修改失败: {str(e)}')


@group_controller.delete('/{group_id}', summary='删除人员组')
@integration_log(
    title='删除人员组',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_group(request: Request, group_id: int, query_db: AsyncSession = Depends(get_db)):
    try:
        result = await GroupService.delete_group_services(query_db, group_id)
        if result:
            return ResponseUtil.success(msg='删除成功')
        else:
            return ResponseUtil.error(msg='人员组不存在')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'删除失败: {str(e)}')


@group_controller.get('/{group_id}/members', summary='获取组内成员')
@integration_log(
    title='获取组内成员',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.OTHER,
)
async def get_group_members(request: Request, group_id: int, query_db: AsyncSession = Depends(get_db)):
    """
    获取指定组的成员列表
    """
    try:
        members = await GroupService.get_group_members_services(query_db, group_id)
        filtered_members = [PeoplePageQueryModel(**member) for member in members]
        return ResponseUtil.success(data=filtered_members)
    except GroupNotFoundError as err:
        return ResponseUtil.error(msg=str(err))


@group_controller.get('/{group_id}/members/{member_id}', summary='获取成员信息')
@integration_log(
    title='获取成员信息',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.OTHER,
)
async def get_group_member_details(
    request: Request, group_id: int, member_id: int, query_db: AsyncSession = Depends(get_db)
):
    return await GroupService.get_group_member_detail_services(query_db, group_id, member_id)


@group_controller.post('/{group_id}/members/{member_id}', summary='添加成员到组')
@integration_log(
    title='添加成员到组',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.INSERT,
)
async def add_member_to_group(
    request: Request, group_id: int, member_id: int, query_db: AsyncSession = Depends(get_db)
):
    """
    添加成员到指定组
    """
    try:
        await GroupService.add_member_to_group_services(query_db, member_id, group_id)
        return ResponseUtil.success(msg='添加成员成功')
    except GroupNotFoundError as err:
        return ResponseUtil.error(msg=str(err))
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'添加成员失败: {str(e)}')


@group_controller.delete('/{group_id}/members/{member_id}', summary='从组中移除成员')
@integration_log(
    title='从组中移除成员',
    system_name='徐州人员组管理系统',
    business_type=BusinessType.DELETE,
)
async def remove_member_from_group(
    request: Request, group_id: int, member_id: int, query_db: AsyncSession = Depends(get_db)
):
    """
    从指定组中移除成员
    """
    try:
        await GroupService.remove_member_from_group_services(query_db, member_id, group_id)
        return ResponseUtil.success(msg='移除成员成功')
    except GroupNotFoundError as err:
        return ResponseUtil.error(msg=str(err))
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'移除成员失败: {str(e)}')
