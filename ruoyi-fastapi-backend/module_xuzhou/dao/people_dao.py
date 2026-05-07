import json
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.entity.do.people_do import PeopleFace
from module_xuzhou.entity.vo.people_vo import PeoplePageQueryModel, PeopleModelWithFeatures
from utils.page_util import PageUtil


class PeopleDao:
    @classmethod
    async def get_people_detail_by_id(cls, db: AsyncSession, people_id: int) -> PeopleFace | None:
        return (await db.execute(select(PeopleFace).where(PeopleFace.id == people_id))).scalars().first()

    @classmethod
    async def get_people_details_by_ids(
        cls, db: AsyncSession, group_id: int, people_ids: list[int]
    ) -> Sequence[PeopleFace]:
        if not people_ids:
            return []
        return (
            (await db.execute(select(PeopleFace).where(PeopleFace.group_id == group_id, PeopleFace.id.in_(people_ids))))
            .scalars()
            .all()
        )

    @classmethod
    async def get_people_list(
        cls, db: AsyncSession, query_object: PeoplePageQueryModel, is_page: bool = False, include_deleted=False
    ):
        query = (
            select(PeopleFace)
            .where(
                PeopleFace.name.like(f'%{query_object.name}%') if query_object.name else True,
                PeopleFace.group_id == query_object.group if query_object.group else True,
                True if query_object.include_deleted else PeopleFace.is_deleted == False,
            )
            .order_by(PeopleFace.id)
            .distinct()
        )

        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def add_people_dao(cls, db: AsyncSession, people: PeopleModelWithFeatures):
        feature_str = json.dumps(people.features)
        db_people = PeopleFace(**{'features': feature_str}, **people.model_dump(exclude={'features'}))
        db.add(db_people)
        await db.flush()

        return db_people.id

    @classmethod
    async def edit_people_dao(cls, db: AsyncSession, people_dict: dict):
        await db.execute(update(PeopleFace), [people_dict])

    @classmethod
    async def delete_people_dao(cls, db: AsyncSession, people_id: int):
        await db.execute(
            update(PeopleFace).where(PeopleFace.id == people_id), {'is_deleted': True, 'deleted_time': datetime.now()}
        )

    @classmethod
    async def get_all_people_features(cls, db: AsyncSession) -> Sequence[PeopleFace]:
        """
        获取所有未删除人员的特征数据
        """
        return (await db.execute(select(PeopleFace).where(PeopleFace.is_deleted == False))).scalars().all()

    @classmethod
    async def get_people_features_by_group(cls, db: AsyncSession, group_id: int) -> Sequence[PeopleFace]:
        """
        按分组获取未删除人员特征数据。
        """
        return (
            await db.execute(
                select(PeopleFace).where(
                    PeopleFace.group_id == group_id,
                    PeopleFace.is_deleted == False,
                )
            )
        ).scalars().all()
