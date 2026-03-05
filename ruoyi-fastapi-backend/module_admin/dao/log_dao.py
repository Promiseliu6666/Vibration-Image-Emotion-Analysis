from datetime import datetime, time

from sqlalchemy import asc, delete, desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.entity.do.log_do import SysLogininfor, SysOperLog, SysIntegrationLog
from module_admin.entity.vo.log_vo import (
    LogininforModel,
    LoginLogPageQueryModel,
    OperLogModel,
    OperLogPageQueryModel,
    IntegrationLogModel,
    IntegrationLogPageQueryModel,
)
from utils.common_util import SnakeCaseUtil
from utils.page_util import PageUtil
from utils.time_format_util import TimeFormatUtil


class OperationLogDao:
    """
    操作日志管理模块数据库操作层
    """

    @classmethod
    async def get_operation_log_list(cls, db: AsyncSession, query_object: OperLogPageQueryModel, is_page: bool = False):
        """
        根据查询参数获取操作日志列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 操作日志列表信息对象
        """
        if query_object.is_asc == 'ascending':
            order_by_column = asc(getattr(SysOperLog, SnakeCaseUtil.camel_to_snake(query_object.order_by_column), None))
        elif query_object.is_asc == 'descending':
            order_by_column = desc(
                getattr(SysOperLog, SnakeCaseUtil.camel_to_snake(query_object.order_by_column), None)
            )
        else:
            order_by_column = desc(SysOperLog.oper_time)
        query = (
            select(SysOperLog)
            .where(
                SysOperLog.title.like(f'%{query_object.title}%') if query_object.title else True,
                SysOperLog.oper_name.like(f'%{query_object.oper_name}%') if query_object.oper_name else True,
                SysOperLog.business_type == query_object.business_type if query_object.business_type else True,
                SysOperLog.status == query_object.status if query_object.status else True,
                SysOperLog.oper_time.between(
                    datetime.combine(TimeFormatUtil.parse_date(query_object.begin_time), time(00, 00, 00)),
                    datetime.combine(TimeFormatUtil.parse_date(query_object.end_time), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .distinct()
            .order_by(order_by_column)
        )
        operation_log_list = await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

        return operation_log_list

    @classmethod
    async def add_operation_log_dao(cls, db: AsyncSession, operation_log: OperLogModel):
        """
        新增操作日志数据库操作

        :param db: orm对象
        :param operation_log: 操作日志对象
        :return: 新增校验结果
        """
        db_operation_log = SysOperLog(**operation_log.model_dump())
        db.add(db_operation_log)
        await db.flush()

        return db_operation_log

    @classmethod
    async def delete_operation_log_dao(cls, db: AsyncSession, operation_log: OperLogModel):
        """
        删除操作日志数据库操作

        :param db: orm对象
        :param operation_log: 操作日志对象
        :return:
        """
        await db.execute(delete(SysOperLog).where(SysOperLog.oper_id.in_([operation_log.oper_id])))

    @classmethod
    async def clear_operation_log_dao(cls, db: AsyncSession):
        """
        清除操作日志数据库操作

        :param db: orm对象
        :return:
        """
        await db.execute(delete(SysOperLog))


class LoginLogDao:
    """
    登录日志管理模块数据库操作层
    """

    @classmethod
    async def get_login_log_list(cls, db: AsyncSession, query_object: LoginLogPageQueryModel, is_page: bool = False):
        """
        根据查询参数获取登录日志列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 登录日志列表信息对象
        """
        if query_object.is_asc == 'ascending':
            order_by_column = asc(
                getattr(SysLogininfor, SnakeCaseUtil.camel_to_snake(query_object.order_by_column), None)
            )
        elif query_object.is_asc == 'descending':
            order_by_column = desc(
                getattr(SysLogininfor, SnakeCaseUtil.camel_to_snake(query_object.order_by_column), None)
            )
        else:
            order_by_column = desc(SysLogininfor.login_time)
        query = (
            select(SysLogininfor)
            .where(
                SysLogininfor.ipaddr.like(f'%{query_object.ipaddr}%') if query_object.ipaddr else True,
                SysLogininfor.user_name.like(f'%{query_object.user_name}%') if query_object.user_name else True,
                SysLogininfor.status == query_object.status if query_object.status else True,
                SysLogininfor.login_time.between(
                    datetime.combine(TimeFormatUtil.parse_date(query_object.begin_time), time(00, 00, 00)),
                    datetime.combine(TimeFormatUtil.parse_date(query_object.end_time), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .distinct()
            .order_by(order_by_column)
        )
        login_log_list = await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

        return login_log_list

    @classmethod
    async def add_login_log_dao(cls, db: AsyncSession, login_log: LogininforModel):
        """
        新增登录日志数据库操作

        :param db: orm对象
        :param login_log: 登录日志对象
        :return: 新增校验结果
        """
        db_login_log = SysLogininfor(**login_log.model_dump())
        db.add(db_login_log)
        await db.flush()

        return db_login_log

    @classmethod
    async def delete_login_log_dao(cls, db: AsyncSession, login_log: LogininforModel):
        """
        删除登录日志数据库操作

        :param db: orm对象
        :param login_log: 登录日志对象
        :return:
        """
        await db.execute(delete(SysLogininfor).where(SysLogininfor.info_id.in_([login_log.info_id])))

    @classmethod
    async def clear_login_log_dao(cls, db: AsyncSession):
        """
        清除登录日志数据库操作

        :param db: orm对象
        :return:
        """
        await db.execute(delete(SysLogininfor))


class IntegrationLogDao:
    """
    系统对接日志管理模块数据库操作层
    """

    @classmethod
    async def get_integration_log_list(
        cls, db: AsyncSession, query_object: IntegrationLogPageQueryModel, is_page: bool = False
    ):
        """
        根据查询参数获取系统对接日志列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 系统对接日志列表信息对象
        """
        if query_object.is_asc == 'ascending':
            order_by_column = asc(
                getattr(SysIntegrationLog, SnakeCaseUtil.camel_to_snake(query_object.order_by_column), None)
            )
        elif query_object.is_asc == 'descending':
            order_by_column = desc(
                getattr(SysIntegrationLog, SnakeCaseUtil.camel_to_snake(query_object.order_by_column), None)
            )
        else:
            order_by_column = desc(SysIntegrationLog.request_time)
        query = (
            select(SysIntegrationLog)
            .where(
                SysIntegrationLog.system_name.like(f'%{query_object.system_name}%')
                if query_object.system_name
                else True,
                SysIntegrationLog.interface_name.like(f'%{query_object.interface_name}%')
                if query_object.interface_name
                else True,
                SysIntegrationLog.status == query_object.status if query_object.status else True,
                SysIntegrationLog.request_time.between(
                    datetime.combine(TimeFormatUtil.parse_date(query_object.begin_time), time(00, 00, 00)),
                    datetime.combine(TimeFormatUtil.parse_date(query_object.end_time), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .distinct()
            .order_by(order_by_column)
        )
        integration_log_list = await PageUtil.paginate(
            db, query, query_object.page_num, query_object.page_size, is_page
        )

        return integration_log_list

    @classmethod
    async def add_integration_log_dao(cls, db: AsyncSession, integration_log: IntegrationLogModel):
        """
        新增系统对接日志数据库操作

        :param db: orm对象
        :param integration_log: 系统对接日志对象
        :return: 新增校验结果
        """
        db_integration_log = SysIntegrationLog(**integration_log.model_dump())
        db.add(db_integration_log)
        await db.flush()

        return db_integration_log

    @classmethod
    async def delete_integration_log_dao(cls, db: AsyncSession, integration_log: IntegrationLogModel):
        """
        删除系统对接日志数据库操作

        :param db: orm对象
        :param integration_log: 系统对接日志对象
        :return:
        """
        await db.execute(delete(SysIntegrationLog).where(SysIntegrationLog.log_id.in_([integration_log.log_id])))

    @classmethod
    async def clear_integration_log_dao(cls, db: AsyncSession):
        """
        清除系统对接日志数据库操作

        :param db: orm对象
        :return:
        """
        await db.execute(delete(SysIntegrationLog))

    @classmethod
    async def get_video_stream_count(cls, db: AsyncSession):
        """
        获取"启动视频推流"操作的数量

        :param db: orm对象
        :return: 启动视频推流操作数量
        """
        result = await db.execute(
            select(func.count(SysIntegrationLog.log_id)).where(SysIntegrationLog.interface_name == '推送视频配置')
        )
        return result.scalar()

    @classmethod
    async def get_video_stream_all(cls, db: AsyncSession):
        """
        获取所有"推送视频配置"操作的信息

        :param db: orm对象
        :return: 推送视频配置操作列表
        """
        result = await db.execute(
            select(SysIntegrationLog.log_id, SysIntegrationLog.request_params).where(
                SysIntegrationLog.interface_name == '推送视频配置'
            )
        )
        return result.all()
