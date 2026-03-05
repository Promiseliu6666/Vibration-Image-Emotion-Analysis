from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from module_admin.entity.do.callback_do import SysCallback
from module_admin.entity.vo.callback_vo import CallbackModel, CallbackPageQueryModel
from utils.page_util import PageUtil


class CallbackDao:
    """
    回调地址管理模块数据库操作层
    """

    @classmethod
    async def get_callback_by_id(cls, db: AsyncSession, callback_id: int):
        """
        根据回调id获取回调详细信息

        :param db: orm对象
        :param callback_id: 回调id
        :return: 回调信息对象
        """
        callback_info = (await db.execute(select(SysCallback).where(SysCallback.callback_id == callback_id))).scalars().first()

        return callback_info

    @classmethod
    async def get_callback_list(cls, db: AsyncSession, query_object: CallbackPageQueryModel, is_page: bool = False):
        """
        根据查询参数获取回调列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 回调列表信息对象
        """
        query = (
            select(SysCallback)
            .where(
                SysCallback.url.like(f'%{query_object.url}%') if query_object.url else True,
                SysCallback.status == query_object.status if query_object.status else True,
                SysCallback.del_flag == '0'
            )
            .order_by(SysCallback.create_time.desc())
        )
        callback_list = await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

        return callback_list

    @classmethod
    async def add_callback_dao(cls, db: AsyncSession, callback: CallbackModel):
        """
        新增回调数据库操作

        :param db: orm对象
        :param callback: 回调对象
        :return:
        """
        db_callback = SysCallback(**callback.model_dump(exclude_unset=True))
        db.add(db_callback)
        await db.flush()

        return db_callback

    @classmethod
    async def edit_callback_dao(cls, db: AsyncSession, callback: dict):
        """
        编辑回调数据库操作

        :param db: orm对象
        :param callback: 回调字典
        :return:
        """
        await db.execute(
            update(SysCallback)
            .where(SysCallback.callback_id == callback.get('callback_id'))
            .values(**callback)
        )

    @classmethod
    async def delete_callback_dao(cls, db: AsyncSession, callback: CallbackModel):
        """
        删除回调数据库操作

        :param db: orm对象
        :param callback: 回调对象
        :return:
        """
        await db.execute(
            delete(SysCallback)
            .where(SysCallback.callback_id.in_(map(int, callback.callback_ids.split(','))))
        )
