from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.group_dao import GroupDao
from module_xuzhou.dao.people_dao import PeopleDao
from module_xuzhou.entity.vo.group_vo import GroupModel, GroupInfoModel, GroupPageQueryModel
from module_xuzhou.error.group_error import GroupNotFoundError
from module_xuzhou.error.people_error import PeopleNotFoundError
from module_xuzhou.service.people_service import PeopleService
from utils.common_util import CamelCaseUtil


class GroupService:
    @classmethod
    async def get_group_list_services(
        cls, query_db: AsyncSession, query_object: GroupPageQueryModel, is_page: bool = False, include_deleted=False
    ):
        group_list_result = await GroupDao.get_group_list(query_db, query_object, is_page, include_deleted)
        return group_list_result

    @classmethod
    async def group_detail_services(cls, query_db: AsyncSession, group_id: int):
        if group := await GroupDao.get_group_detail_by_id(query_db, group_id=group_id):
            result = GroupModel(**CamelCaseUtil.transform_result(group))
        else:
            raise GroupNotFoundError('人员组不存在')
        return result

    @classmethod
    async def group_details_services(cls, query_db: AsyncSession, group_ids: list[int]):
        result = []
        for group in await GroupDao.get_group_details_by_ids(query_db, group_ids=group_ids):
            result.append(CamelCaseUtil.transform_result(group))
        return result

    @classmethod
    async def add_group_services(cls, query_db: AsyncSession, group: GroupModel):
        group_info = GroupInfoModel(**group.model_dump())
        group_info.created_time = datetime.now()
        group_info.updated_time = datetime.now()
        await GroupDao.add_group_dao(query_db, group_info)
        await query_db.commit()

    @classmethod
    async def edit_group_services(cls, group_id: int, query_db: AsyncSession, group: GroupModel):
        await GroupDao.edit_group_dao(
            query_db, {**{'id': group_id, 'updated_time': datetime.now()}, **group.model_dump(include={'name'})}
        )
        await query_db.commit()

    @classmethod
    async def delete_group_services(cls, query_db: AsyncSession, group_id: int):
        if await GroupDao.get_group_detail_by_id(query_db, group_id=group_id):
            await GroupDao.delete_group_dao(query_db, group_id=group_id)
            await query_db.commit()
            return True
        return False

    @classmethod
    async def get_group_members_services(cls, query_db: AsyncSession, group_id: int):
        if not await GroupDao.get_group_detail_by_id(query_db, group_id=group_id):
            raise GroupNotFoundError('人员组不存在')
        result = []
        for member in await GroupDao.get_group_members(query_db, group_id=group_id):
            result.append(CamelCaseUtil.transform_result(member))
        return result

    @classmethod
    async def get_group_member_detail_services(cls, query_db: AsyncSession, group_id: int, member_id: int):
        if not await GroupDao.get_group_detail_by_id(query_db, group_id=group_id):
            raise GroupNotFoundError('人员组不存在')
        elif not await PeopleDao.get_people_detail_by_id(query_db, people_id=member_id):
            raise PeopleNotFoundError('成员不存在')
        else:
            return await PeopleService.people_detail_services(query_db, member_id)

    @classmethod
    async def add_member_to_group_services(cls, query_db: AsyncSession, member_id: int, group_id: int):
        if not await GroupDao.get_group_detail_by_id(query_db, group_id=group_id):
            raise GroupNotFoundError('人员组不存在')
        elif not await PeopleDao.get_people_detail_by_id(query_db, people_id=member_id):
            raise PeopleNotFoundError('成员不存在')
        else:
            await GroupDao.add_member_to_group(query_db, member_id=member_id, group_id=group_id)
            await query_db.commit()

    @classmethod
    async def remove_member_from_group_services(cls, query_db: AsyncSession, member_id: int, group_id: int):
        if not await GroupDao.get_group_detail_by_id(query_db, group_id=group_id):
            raise GroupNotFoundError('人员组不存在')
        elif not await PeopleDao.get_people_detail_by_id(query_db, people_id=member_id):
            raise PeopleNotFoundError('成员不存在')
        else:
            await GroupDao.remove_member_from_group(query_db, member_id=member_id, group_id=group_id)
            await query_db.commit()
