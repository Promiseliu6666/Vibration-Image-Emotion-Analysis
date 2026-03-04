from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_admin.annotation.log_annotation import Log
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.log_vo import (
    DeleteLoginLogModel,
    DeleteOperLogModel,
    LoginLogPageQueryModel,
    OperLogPageQueryModel,
    UnlockUser,
    IntegrationLogPageQueryModel,
    DeleteIntegrationLogModel,
)
from module_admin.service.log_service import LoginLogService, OperationLogService, IntegrationLogService
from module_admin.service.login_service import LoginService
from utils.common_util import bytes2file_response
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

logController = APIRouter(
    prefix='/monitor', dependencies=[Depends(LoginService.get_current_user)], include_in_schema=False
)


@logController.get(
    '/operlog/list',
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth('monitor:operlog:list'))],
)
@integration_log(
    title='操作日志查询',
    system_name='日志管理系统',
    business_type=BusinessType.OTHER,
)
async def get_system_operation_log_list(
    request: Request,
    operation_log_page_query: OperLogPageQueryModel = Depends(OperLogPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    # 获取分页数据
    operation_log_page_query_result = await OperationLogService.get_operation_log_list_services(
        query_db, operation_log_page_query, is_page=True
    )
    logger.info('获取成功')

    return ResponseUtil.success(model_content=operation_log_page_query_result)


@logController.delete('/operlog/clean', dependencies=[Depends(CheckUserInterfaceAuth('monitor:operlog:remove'))])
@Log(title='操作日志', business_type=BusinessType.CLEAN)
@integration_log(
    title='清空操作日志',
    system_name='日志管理系统',
    business_type=BusinessType.CLEAN,
)
async def clear_system_operation_log(request: Request, query_db: AsyncSession = Depends(get_db)):
    clear_operation_log_result = await OperationLogService.clear_operation_log_services(query_db)
    logger.info(clear_operation_log_result.message)

    return ResponseUtil.success(msg=clear_operation_log_result.message)


@logController.delete('/operlog/{oper_ids}', dependencies=[Depends(CheckUserInterfaceAuth('monitor:operlog:remove'))])
@Log(title='操作日志', business_type=BusinessType.DELETE)
@integration_log(
    title='删除操作日志',
    system_name='日志管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_system_operation_log(request: Request, oper_ids: str, query_db: AsyncSession = Depends(get_db)):
    delete_operation_log = DeleteOperLogModel(operIds=oper_ids)
    delete_operation_log_result = await OperationLogService.delete_operation_log_services(
        query_db, delete_operation_log
    )
    logger.info(delete_operation_log_result.message)

    return ResponseUtil.success(msg=delete_operation_log_result.message)


@logController.post('/operlog/export', dependencies=[Depends(CheckUserInterfaceAuth('monitor:operlog:export'))])
@Log(title='操作日志', business_type=BusinessType.EXPORT)
@integration_log(
    title='导出操作日志',
    system_name='日志管理系统',
    business_type=BusinessType.EXPORT,
)
async def export_system_operation_log_list(
    request: Request,
    operation_log_page_query: OperLogPageQueryModel = Form(),
    query_db: AsyncSession = Depends(get_db),
):
    # 获取全量数据
    operation_log_query_result = await OperationLogService.get_operation_log_list_services(
        query_db, operation_log_page_query, is_page=False
    )
    operation_log_export_result = await OperationLogService.export_operation_log_list_services(
        request, operation_log_query_result
    )
    logger.info('导出成功')

    return ResponseUtil.streaming(data=bytes2file_response(operation_log_export_result))


@logController.get(
    '/logininfor/list',
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth('monitor:logininfor:list'))],
)
@integration_log(
    title='登录日志查询',
    system_name='日志管理系统',
    business_type=BusinessType.OTHER,
)
async def get_system_login_log_list(
    request: Request,
    login_log_page_query: LoginLogPageQueryModel = Depends(LoginLogPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    # 获取分页数据
    login_log_page_query_result = await LoginLogService.get_login_log_list_services(
        query_db, login_log_page_query, is_page=True
    )
    logger.info('获取成功')

    return ResponseUtil.success(model_content=login_log_page_query_result)


@logController.delete('/logininfor/clean', dependencies=[Depends(CheckUserInterfaceAuth('monitor:logininfor:remove'))])
@Log(title='登录日志', business_type=BusinessType.CLEAN)
@integration_log(
    title='清空登录日志',
    system_name='日志管理系统',
    business_type=BusinessType.CLEAN,
)
async def clear_system_login_log(request: Request, query_db: AsyncSession = Depends(get_db)):
    clear_login_log_result = await LoginLogService.clear_login_log_services(query_db)
    logger.info(clear_login_log_result.message)

    return ResponseUtil.success(msg=clear_login_log_result.message)


@logController.delete(
    '/logininfor/{info_ids}', dependencies=[Depends(CheckUserInterfaceAuth('monitor:logininfor:remove'))]
)
@Log(title='登录日志', business_type=BusinessType.DELETE)
@integration_log(
    title='删除登录日志',
    system_name='日志管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_system_login_log(request: Request, info_ids: str, query_db: AsyncSession = Depends(get_db)):
    delete_login_log = DeleteLoginLogModel(infoIds=info_ids)
    delete_login_log_result = await LoginLogService.delete_login_log_services(query_db, delete_login_log)
    logger.info(delete_login_log_result.message)

    return ResponseUtil.success(msg=delete_login_log_result.message)


@logController.get(
    '/logininfor/unlock/{user_name}', dependencies=[Depends(CheckUserInterfaceAuth('monitor:logininfor:unlock'))]
)
@Log(title='账户解锁', business_type=BusinessType.OTHER)
@integration_log(
    title='账户解锁',
    system_name='日志管理系统',
    business_type=BusinessType.OTHER,
)
async def unlock_system_user(request: Request, user_name: str, query_db: AsyncSession = Depends(get_db)):
    unlock_user = UnlockUser(userName=user_name)
    unlock_user_result = await LoginLogService.unlock_user_services(request, unlock_user)
    logger.info(unlock_user_result.message)

    return ResponseUtil.success(msg=unlock_user_result.message)


@logController.post('/logininfor/export', dependencies=[Depends(CheckUserInterfaceAuth('monitor:logininfor:export'))])
@Log(title='登录日志', business_type=BusinessType.EXPORT)
@integration_log(
    title='导出登录日志',
    system_name='日志管理系统',
    business_type=BusinessType.EXPORT,
)
async def export_system_login_log_list(
    request: Request,
    login_log_page_query: LoginLogPageQueryModel = Form(),
    query_db: AsyncSession = Depends(get_db),
):
    # 获取全量数据
    login_log_query_result = await LoginLogService.get_login_log_list_services(
        query_db, login_log_page_query, is_page=False
    )
    login_log_export_result = await LoginLogService.export_login_log_list_services(login_log_query_result)
    logger.info('导出成功')

    return ResponseUtil.streaming(data=bytes2file_response(login_log_export_result))


# 系统对接日志相关接口
@logController.get(
    '/integration/list',
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth('monitor:integration:list'))],
)
async def get_system_integration_log_list(
    request: Request,
    integration_log_page_query: IntegrationLogPageQueryModel = Depends(IntegrationLogPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    integration_log_query_result = await IntegrationLogService.get_integration_log_list_services(
        query_db, integration_log_page_query, is_page=True
    )
    logger.info('获取系统对接日志列表成功')

    return ResponseUtil.success(model_content=integration_log_query_result)


@logController.delete(
    '/integration/clean', dependencies=[Depends(CheckUserInterfaceAuth('monitor:integration:remove'))]
)
@Log(title='系统对接日志', business_type=BusinessType.CLEAN)
@integration_log(
    title='清空系统对接日志',
    system_name='日志管理系统',
    business_type=BusinessType.CLEAN,
)
async def clear_system_integration_log(request: Request, query_db: AsyncSession = Depends(get_db)):
    clear_integration_log_result = await IntegrationLogService.clear_integration_log_services(query_db)
    logger.info(clear_integration_log_result.message)

    return ResponseUtil.success(msg=clear_integration_log_result.message)


@logController.delete(
    '/integration/{log_ids}', dependencies=[Depends(CheckUserInterfaceAuth('monitor:integration:remove'))]
)
@Log(title='系统对接日志', business_type=BusinessType.DELETE)
@integration_log(
    title='删除系统对接日志',
    system_name='日志管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_system_integration_log(request: Request, log_ids: str, query_db: AsyncSession = Depends(get_db)):
    delete_integration_log = DeleteIntegrationLogModel(logIds=log_ids)
    delete_integration_log_result = await IntegrationLogService.delete_integration_log_services(
        query_db, delete_integration_log
    )
    logger.info(delete_integration_log_result.message)

    return ResponseUtil.success(msg=delete_integration_log_result.message)


@logController.post('/integration/export', dependencies=[Depends(CheckUserInterfaceAuth('monitor:integration:export'))])
@Log(title='系统对接日志', business_type=BusinessType.EXPORT)
@integration_log(
    title='导出系统对接日志',
    system_name='日志管理系统',
    business_type=BusinessType.EXPORT,
)
async def export_system_integration_log_list(
    request: Request,
    integration_log_page_query: IntegrationLogPageQueryModel = Form(),
    query_db: AsyncSession = Depends(get_db),
):
    # 获取全量数据
    integration_log_query_result = await IntegrationLogService.get_integration_log_list_services(
        query_db, integration_log_page_query, is_page=False
    )
    # 这里可以添加导出逻辑，暂时返回数据
    logger.info('导出系统对接日志成功')

    return ResponseUtil.success(data=integration_log_query_result)
