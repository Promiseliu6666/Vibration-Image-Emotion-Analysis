from sqlalchemy.ext.asyncio import AsyncSession
from exceptions.exception import ServiceException
from module_admin.dao.callback_dao import CallbackDao
from module_admin.entity.vo.common_vo import CrudResponseModel
from module_admin.entity.vo.callback_vo import DeleteCallbackModel, CallbackModel, CallbackPageQueryModel


class CallbackService:
    """
    回调地址管理模块服务层
    """

    @classmethod
    async def get_callback_list_services(
        cls, query_db: AsyncSession, query_object: CallbackPageQueryModel, is_page: bool = False
    ):
        """
        获取回调列表信息service

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 回调列表信息对象
        """
        callback_list_result = await CallbackDao.get_callback_list(query_db, query_object, is_page)

        return callback_list_result

    @classmethod
    async def add_callback_services(cls, query_db: AsyncSession, page_object: CallbackModel):
        """
        新增回调信息service

        :param query_db: orm对象
        :param page_object: 新增回调对象
        :return: 新增回调校验结果
        """
        try:
            await CallbackDao.add_callback_dao(query_db, page_object)
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def edit_callback_services(cls, query_db: AsyncSession, page_object: CallbackModel):
        """
        编辑回调信息service

        :param query_db: orm对象
        :param page_object: 编辑回调对象
        :return: 编辑回调校验结果
        """
        edit_callback = page_object.model_dump(exclude_unset=True)
        callback_info = await cls.callback_detail_services(query_db, page_object.callback_id)
        if callback_info:
            try:
                await CallbackDao.edit_callback_dao(query_db, edit_callback)
                await query_db.commit()
                return CrudResponseModel(is_success=True, message='修改成功')
            except Exception as e:
                await query_db.rollback()
                raise e
        else:
            raise ServiceException(message='回调地址不存在')

    @classmethod
    async def delete_callback_services(cls, query_db: AsyncSession, page_object: DeleteCallbackModel):
        """
        删除回调信息service

        :param query_db: orm对象
        :param page_object: 删除回调对象
        :return: 删除回调校验结果
        """
        if page_object.callback_ids:
            callback_id_list = page_object.callback_ids.split(',')
            try:
                for callback_id in callback_id_list:
                    await CallbackDao.delete_callback_dao(query_db, DeleteCallbackModel(callback_ids=callback_id))
                await query_db.commit()
                return CrudResponseModel(is_success=True, message='删除成功')
            except Exception as e:
                await query_db.rollback()
                raise e
        else:
            raise ServiceException(message='传入回调ID为空')

    @classmethod
    async def callback_detail_services(cls, query_db: AsyncSession, callback_id: int):
        """
        获取回调详细信息service

        :param query_db: orm对象
        :param callback_id: 回调id
        :return: 回调详细信息对象
        """
        callback_info = await CallbackDao.get_callback_by_id(query_db, callback_id)
        return callback_info
