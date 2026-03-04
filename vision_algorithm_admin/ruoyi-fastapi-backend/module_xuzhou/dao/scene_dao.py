from sqlalchemy import delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from module_xuzhou.entity.do.scene_do import XuzhouScene
from module_xuzhou.entity.vo.scene_vo import SceneModel, ScenePageQueryModel
from utils.page_util import PageUtil


class SceneDao:
    """
    场景管理模块数据库操作层
    """

    @classmethod
    async def get_scene_detail_by_id(cls, db: AsyncSession, scene_id: int):
        """
        根据场景id获取场景详细信息

        :param db: orm对象
        :param scene_id: 场景id
        :return: 场景信息对象
        """
        scene_info = (await db.execute(select(XuzhouScene).where(XuzhouScene.scene_id == scene_id))).scalars().first()

        return scene_info

    @classmethod
    async def get_scene_list(cls, db: AsyncSession, query_object: ScenePageQueryModel, is_page: bool = False):
        """
        根据查询参数获取场景列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 场景列表信息对象
        """
        query = (
            select(XuzhouScene)
            .where(
                XuzhouScene.scene_name.like(f'%{query_object.scene_name}%') if query_object.scene_name else True,
                XuzhouScene.scene_serial.like(f'%{query_object.scene_serial}%') if query_object.scene_serial else True,
            )
            .order_by(XuzhouScene.scene_id)
            .distinct()
        )
        scene_list = await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

        return scene_list

    @classmethod
    async def add_scene_dao(cls, db: AsyncSession, scene):
        """
        新增场景数据库操作

        :param db: orm对象
        :param scene: 场景对象
        :return:
        """
        db_scene = XuzhouScene(**scene.model_dump())
        db.add(db_scene)
        await db.flush()

        return db_scene

    @classmethod
    async def edit_scene_dao(cls, db: AsyncSession, scene: dict):
        """
        编辑场景数据库操作

        :param db: orm对象
        :param scene: 需要更新的场景字典
        :return:
        """
        await db.execute(update(XuzhouScene), [scene])

    @classmethod
    async def delete_scene_dao(cls, db: AsyncSession, scene_id: int):
        """
        删除场景数据库操作

        :param db: orm对象
        :param scene_id: 场景id
        :return:
        """
        await db.execute(delete(XuzhouScene).where(XuzhouScene.scene_id == scene_id))

    @classmethod
    async def get_scene_count(cls, db: AsyncSession):
        """
        获取场景总数量

        :param db: orm对象
        :return: 场景数量
        """
        result = await db.execute(select(func.count(XuzhouScene.scene_id)))
        return result.scalar()
