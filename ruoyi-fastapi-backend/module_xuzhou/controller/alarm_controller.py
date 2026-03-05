from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.entity.vo.alarm_vo import AlarmPageQueryModel
from module_xuzhou.service.alarm_service import AlarmService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil


alarmController = APIRouter(prefix='/xuzhou/alarm', dependencies=[Depends(unified_auth)])


@alarmController.get('/list', response_model=PageResponseModel, summary='获取预警消息列表')
@integration_log(
    title='获取预警消息列表',
    system_name='徐州预警管理系统',
    business_type=BusinessType.OTHER,
)
async def get_alarm_list(
    request: Request,
    alarm_page_query: AlarmPageQueryModel = Depends(AlarmPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    """
    获取预警消息列表
    """
    alarm_list_result = await AlarmService.get_alarm_list(
        query_db=query_db,
        page_num=alarm_page_query.page_num,
        page_size=alarm_page_query.page_size,
        vid_id=alarm_page_query.vid_id,
        alarm_code=alarm_page_query.alarm_code
    )
    return ResponseUtil.success(dict_content=alarm_list_result)
