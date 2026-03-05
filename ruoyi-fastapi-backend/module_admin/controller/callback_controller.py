from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.log_annotation import Log
from module_admin.service.login_service import LoginService
from module_admin.service.callback_service import CallbackService
from module_admin.entity.vo.callback_vo import DeleteCallbackModel, CallbackModel, CallbackPageQueryModel
from module_admin.entity.vo.user_vo import CurrentUserModel
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil


callbackController = APIRouter(
    prefix='/tool/callback', dependencies=[Depends(LoginService.get_current_user)]
)


@callbackController.get(
    '/list', response_model=PageResponseModel
)
async def get_callback_list(
    request: Request,
    callback_page_query: CallbackPageQueryModel = Depends(CallbackPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    # 获取分页数据
    callback_page_query_result = await CallbackService.get_callback_list_services(query_db, callback_page_query, is_page=True)

    return ResponseUtil.success(model_content=callback_page_query_result)


@callbackController.post('', summary='新增回调地址')
@Log(title='回调地址管理', business_type=BusinessType.INSERT)
async def add_callback(
    request: Request,
    add_callback: CallbackModel,
    query_db: AsyncSession = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    add_callback.create_by = current_user.user.user_name
    add_callback.update_by = current_user.user.user_name
    add_callback_result = await CallbackService.add_callback_services(query_db, add_callback)

    return ResponseUtil.success(msg=add_callback_result.message)


@callbackController.put('', summary='修改回调地址')
@Log(title='回调地址管理', business_type=BusinessType.UPDATE)
async def edit_callback(
    request: Request,
    edit_callback: CallbackModel,
    query_db: AsyncSession = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    edit_callback.update_by = current_user.user.user_name
    edit_callback_result = await CallbackService.edit_callback_services(query_db, edit_callback)

    return ResponseUtil.success(msg=edit_callback_result.message)


@callbackController.delete('/{callback_ids}', summary='删除回调地址')
@Log(title='回调地址管理', business_type=BusinessType.DELETE)
async def delete_callback(request: Request, callback_ids: str, query_db: AsyncSession = Depends(get_db)):
    delete_callback = DeleteCallbackModel(callback_ids=callback_ids)
    delete_callback_result = await CallbackService.delete_callback_services(query_db, delete_callback)

    return ResponseUtil.success(msg=delete_callback_result.message)


@callbackController.get(
    '/{callback_id}', response_model=CallbackModel, summary='获取回调地址详细信息'
)
async def query_detail_callback(request: Request, callback_id: int, query_db: AsyncSession = Depends(get_db)):
    callback_detail_result = await CallbackService.callback_detail_services(query_db, callback_id)

    return ResponseUtil.success(data=callback_detail_result)
