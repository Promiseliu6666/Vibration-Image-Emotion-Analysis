from sqlalchemy import delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from module_xuzhou.entity.do.alg_do import XuzhouAlg
from module_xuzhou.entity.vo.alg_vo import AlgModel, AlgPageQueryModel
from utils.page_util import PageUtil


class AlgDao:
    """
    算法管理模块数据库操作层
    """

    @classmethod
    async def get_alg_detail_by_id(cls, db: AsyncSession, alg_id: int):
        """
        根据算法id获取算法详细信息

        :param db: orm对象
        :param alg_id: 算法id
        :return: 算法信息对象
        """
        alg_info = (await db.execute(select(XuzhouAlg).where(XuzhouAlg.alg_id == alg_id))).scalars().first()

        return alg_info

    @classmethod
    async def get_alg_by_serial_version(cls, db: AsyncSession, alg_serial: str, alg_version: str):
        """
        根据算法序列号和版本获取算法信息

        :param db: orm对象
        :param alg_serial: 算法序列号
        :param alg_version: 算法版本
        :return: 算法信息对象
        """
        alg_info = (
            await db.execute(
                select(XuzhouAlg).where(
                    XuzhouAlg.alg_serial == alg_serial,
                    XuzhouAlg.alg_version == alg_version,
                )
            )
        ).scalars().first()

        return alg_info

    @classmethod
    async def get_enabled_alg_by_id(cls, db: AsyncSession, alg_id: int):
        """
        根据算法id获取已启用算法信息

        :param db: orm对象
        :param alg_id: 算法id
        :return: 算法信息对象
        """
        alg_info = (
            await db.execute(
                select(XuzhouAlg).where(
                    XuzhouAlg.alg_id == alg_id,
                    XuzhouAlg.alg_enabled.is_(True),
                )
            )
        ).scalars().first()

        return alg_info

    @classmethod
    async def get_alg_details_by_ids(cls, db: AsyncSession, alg_ids: list):
        """
        根据算法id列表获取算法详细信息列表

        :param db: orm对象
        :param alg_ids: 算法id列表
        :return: 算法信息对象列表
        """
        if not alg_ids:
            return []
        alg_info_list = (await db.execute(select(XuzhouAlg).where(XuzhouAlg.alg_id.in_(alg_ids)))).scalars().all()

        return alg_info_list

    @classmethod
    async def get_alg_list(cls, db: AsyncSession, query_object: AlgPageQueryModel, is_page: bool = False):
        """
        根据查询参数获取算法列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 算法列表信息对象
        """
        query = (
            select(XuzhouAlg)
            .where(
                XuzhouAlg.alg_name.like(f'%{query_object.alg_name}%') if query_object.alg_name else True,
                XuzhouAlg.alg_version.like(f'%{query_object.alg_version}%') if query_object.alg_version else True,
            )
            .order_by(XuzhouAlg.alg_id)
            .distinct()
        )
        alg_list = await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

        return alg_list

    @classmethod
    async def add_alg_dao(cls, db: AsyncSession, alg):
        """
        新增算法数据库操作

        :param db: orm对象
        :param alg: 算法对象
        :return:
        """
        db_alg = XuzhouAlg(**alg.model_dump())
        db.add(db_alg)
        await db.flush()

        return db_alg

    @classmethod
    async def edit_alg_dao(cls, db: AsyncSession, alg: dict):
        """
        编辑算法数据库操作

        :param db: orm对象
        :param alg: 需要更新的算法字典
        :return:
        """
        alg_id = alg.pop('alg_id')
        await db.execute(update(XuzhouAlg).where(XuzhouAlg.alg_id == alg_id).values(alg))

    @classmethod
    async def delete_alg_dao(cls, db: AsyncSession, alg_id: int):
        """
        删除算法数据库操作

        :param db: orm对象
        :param alg_id: 算法id
        :return:
        """
        await db.execute(delete(XuzhouAlg).where(XuzhouAlg.alg_id == alg_id))

    @classmethod
    async def get_alg_by_serial(cls, db: AsyncSession, alg_serial: str):
        """根据算法序列号获取算法（任意版本）。"""
        return (await db.execute(
            select(XuzhouAlg).where(XuzhouAlg.alg_serial == alg_serial)
        )).scalars().first()

    @classmethod
    async def get_alg_by_name(cls, db: AsyncSession, alg_name: str):
        """根据算法名称获取算法。"""
        return (await db.execute(
            select(XuzhouAlg).where(XuzhouAlg.alg_name == alg_name)
        )).scalars().first()

    @classmethod
    async def create_alg(cls, db: AsyncSession, alg_dict: dict):
        """直接通过字典创建算法记录，返回新ID。"""
        db_alg = XuzhouAlg(**alg_dict)
        db.add(db_alg)
        await db.flush()
        return db_alg.alg_id

    @classmethod
    async def get_alg_count(cls, db: AsyncSession):
        """
        获取算法总数量

        :param db: orm对象
        :return: 算法数量
        """
        result = await db.execute(select(func.count(XuzhouAlg.alg_id)))
        return result.scalar()
