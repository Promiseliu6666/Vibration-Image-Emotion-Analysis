from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.entity.do.group_do import PeopleGroup
from module_xuzhou.entity.do.people_do import PeopleFace
from module_xuzhou.entity.vo.group_vo import GroupModel, GroupPageQueryModel, GroupInfoModel
from utils.page_util import PageUtil


class GroupDao:
    @classmethod
    async def get_group_detail_by_id(cls, db: AsyncSession, group_id: int):
        return (await db.execute(select(PeopleGroup).where(PeopleGroup.id == group_id))).scalars().first()

    @classmethod
    async def get_group_details_by_ids(cls, db: AsyncSession, group_ids: list):
        if not group_ids:
            return []
        return (await db.execute(select(PeopleGroup).where(PeopleGroup.id.in_(group_ids)))).scalars().all()

    @classmethod
    async def get_group_list(
        cls, db: AsyncSession, query_object: GroupPageQueryModel, is_page: bool = False, include_deleted: bool = False
    ) -> list[GroupModel]:
        query = (
            select(PeopleGroup)
            .where(
                PeopleGroup.name.like(f'%{query_object.name}%') if query_object.name else True,
                True if include_deleted else PeopleGroup.is_deleted == False,
            )
            .order_by(PeopleGroup.id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def add_group_dao(cls, db: AsyncSession, group: GroupInfoModel):
        db_group = PeopleGroup(**group.model_dump())
        db.add(db_group)
        await db.flush()

        return db_group

    @classmethod
    async def edit_group_dao(cls, db: AsyncSession, group: dict):
        await db.execute(update(PeopleGroup), [group])

    @classmethod
    async def delete_group_dao(cls, db: AsyncSession, group_id: int):
        await db.execute(
            update(PeopleGroup).where(PeopleGroup.id == group_id), {'is_deleted': True, 'deleted_time': datetime.now()}
        )

    @classmethod
    async def get_group_members(cls, db: AsyncSession, group_id: int):
        """
        获取组内所有成员

        Args:
            db: 数据库会话
            group_id: 组ID

        Returns:
            组内所有成员列表
        """
        query = select(PeopleFace).where(PeopleFace.group_id == group_id, PeopleFace.is_deleted == False)
        result = await db.execute(query)
        return result.scalars().all()

    @classmethod
    async def add_member_to_group(cls, db: AsyncSession, member_id: int, group_id: int):
        """
        将成员添加到组

        Args:
            db: 数据库会话
            member_id: 成员ID
            group_id: 组ID
        """
        query = update(PeopleFace).where(PeopleFace.id == member_id).values(group_id=group_id)
        await db.execute(query)

    @classmethod
    async def remove_member_from_group(cls, db: AsyncSession, member_id: int, group_id: int):
        """
        从组中移除成员

        Args:
            db: 数据库会话
            member_id: 成员ID
            group_id: 组ID
        """
        query = (
            update(PeopleFace).where(PeopleFace.id == member_id, PeopleFace.group_id == group_id).values(group_id=None)
        )
        await db.execute(query)
