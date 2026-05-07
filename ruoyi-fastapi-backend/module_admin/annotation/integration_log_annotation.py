import asyncio
import json
import time
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.log_annotation import (
    get_function_parameters_name_by_type,
    get_function_parameters_value_by_name,
)
from module_admin.entity.vo.log_vo import IntegrationLogModel
from module_admin.service.log_service import IntegrationLogService
from utils.log_util import logger


class IntegrationLog:
    """
    系统对接日志装饰器
    用于记录系统间接口调用的详细日志信息
    """

    def __init__(
        self,
        title: str = '',
        system_name: str = '',
        business_type: BusinessType = BusinessType.OTHER,
        is_save_request_data: bool = True,
        is_save_response_data: bool = True,
        exclude_param_names: Optional[list] = None,
    ):
        """
        初始化系统对接日志装饰器

        :param title: 操作标题
        :param system_name: 系统名称
        :param business_type: 业务类型
        :param is_save_request_data: 是否保存请求参数
        :param is_save_response_data: 是否保存响应数据
        :param exclude_param_names: 排除的参数名称列表（敏感信息）
        """
        self.title = title
        self.system_name = system_name
        self.business_type = business_type
        self.is_save_request_data = is_save_request_data
        self.is_save_response_data = is_save_response_data
        self.exclude_param_names = exclude_param_names or []
        self.max_request_param_length = 8000
        self.max_response_data_length = 8000
        self.max_error_msg_length = 2000

    @staticmethod
    def _truncate_text(value: Any, max_len: int) -> str:
        text = '' if value is None else str(value)
        if len(text) <= max_len:
            return text
        return f'{text[:max_len]}...[truncated {len(text) - max_len} chars]'

    def _sanitize_for_log(self, value: Any):
        if hasattr(value, 'model_dump') and callable(getattr(value, 'model_dump')):
            try:
                return self._sanitize_for_log(value.model_dump())
            except Exception:
                return self._truncate_text(str(value), 1024)
        if hasattr(value, 'dict') and callable(getattr(value, 'dict')):
            try:
                return self._sanitize_for_log(value.dict())
            except Exception:
                return self._truncate_text(str(value), 1024)
        if isinstance(value, dict):
            sanitized = {}
            for k, v in value.items():
                key_lower = str(k).lower()
                if key_lower in {'pics', 'pic', 'image', 'img', 'photo', 'file', 'files', 'avatar'}:
                    if isinstance(v, str) and (v.startswith('data:image/') or len(v) > 1024):
                        sanitized[k] = f'[omitted large field len={len(v)}]'
                    else:
                        sanitized[k] = self._sanitize_for_log(v)
                else:
                    sanitized[k] = self._sanitize_for_log(v)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_for_log(item) for item in value]
        if isinstance(value, str):
            if value.startswith('data:image/'):
                return f'[omitted base64 image len={len(value)}]'
            if 'data:image/' in value:
                return '[omitted embedded base64 image]'
            if len(value) > 4096:
                return self._truncate_text(value, 4096)
            return value
        # Last fallback for custom objects.
        fallback = str(value)
        if len(fallback) > 1024:
            return self._truncate_text(fallback, 1024)
        return fallback

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 记录开始时间
            start_time = time.time()

            # 获取请求对象和数据库会话
            request = None
            query_db = None

            # 使用正确的方式获取Request对象
            try:
                request_name_list = get_function_parameters_name_by_type(func, Request)
                if request_name_list:
                    request = get_function_parameters_value_by_name(func, request_name_list[0], *args, **kwargs)
            except Exception:
                # 如果获取失败，尝试从参数中查找
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                for key, value in kwargs.items():
                    if isinstance(value, Request):
                        request = value
                        break

            # 获取数据库会话
            try:
                session_name_list = get_function_parameters_name_by_type(func, AsyncSession)
                if session_name_list:
                    query_db = get_function_parameters_value_by_name(func, session_name_list[0], *args, **kwargs)
            except Exception:
                # 如果获取失败，尝试从参数中查找
                for key, value in kwargs.items():
                    if isinstance(value, AsyncSession):
                        query_db = value
                        break

            # 如果没有找到数据库会话，创建一个新的
            if query_db is None:
                async for db in get_db():
                    query_db = db
                    break

            # 准备日志数据
            log_data = {
                'systemName': self.system_name,
                'interfaceName': self.title or func.__name__,
                'interfaceUrl': str(request.url) if request else '',
                'requestMethod': request.method if request else 'UNKNOWN',
                'requestParams': '',
                'responseData': '',
                'status': 0,  # 0-正常 1-异常
                'errorMsg': '',
                'requestTime': datetime.now(),
                'responseTime': None,
                'costTime': 0,
                'requestIp': request.client.host
                if request and hasattr(request, 'client') and request.client
                else '127.0.0.1',
                'userAgent': request.headers.get('user-agent', '') if request else '',
                'traceId': getattr(request.state, 'trace_id', '') if request and hasattr(request, 'state') else '',
                'remark': '',
            }

            # 记录请求参数
            if self.is_save_request_data:
                try:
                    # 过滤敏感参数
                    filtered_kwargs = {
                        k: v
                        for k, v in kwargs.items()
                        if k not in self.exclude_param_names and not isinstance(v, (Request, AsyncSession))
                    }
                    sanitized_kwargs = self._sanitize_for_log(filtered_kwargs)
                    request_params_text = json.dumps(sanitized_kwargs, ensure_ascii=False, default=str)
                    log_data['requestParams'] = self._truncate_text(request_params_text, self.max_request_param_length)
                except Exception:
                    log_data['requestParams'] = '参数序列化失败'

            # 执行原函数
            result = None
            try:
                result = await func(*args, **kwargs)
                log_data['status'] = 0

                # 记录响应数据（修改：只保存概要）
                if self.is_save_response_data and result is not None:
                    try:
                        # 尝试获取响应 JSON（兼容 ResponseUtil.success 返回的格式）
                        response_json = {}
                        if hasattr(result, 'body') and hasattr(result.body, 'decode'):
                            try:
                                response_json = json.loads(result.body.decode('utf-8'))
                            except:
                                response_json = {"raw_body": str(result.body)}
                        elif hasattr(result, 'model_dump'):
                            response_json = result.model_dump()
                        elif isinstance(result, dict):
                            response_json = result
                        else:
                            response_json = {"result": str(result)}

                        # 构建小体积的响应概要
                        summary = {
                            "code": response_json.get("code", 0),
                            "msg": response_json.get("msg", ""),
                            "success": response_json.get("success", False),
                            "time": response_json.get("time"),
                            "response_length_bytes": len(json.dumps(response_json, ensure_ascii=False).encode('utf-8')),
                            "has_large_pics": False,
                            "data_summary": {},
                        }

                        # 针对“获取人员列表”接口的特殊处理
                        if self.title == '获取人员列表' or '人员列表' in self.title:
                            data = response_json.get("data", {})
                            rows = data.get("rows", [])
                            summary["data_summary"] = {
                                "rows_count": len(rows),
                                "total": data.get("total", 0),
                                "page_num": data.get("pageNum"),
                                "page_size": data.get("pageSize"),
                                "has_next": data.get("hasNext", False),
                            }

                            # 检查是否有大 base64 图片
                            for row in rows:
                                pics = row.get("pics", "")
                                if isinstance(pics, str) and pics.startswith("data:image/") and len(pics) > 10000:
                                    summary["has_large_pics"] = True
                                    break  # 找到一个就够了

                        # 存入日志的只有这个小的 summary JSON
                        response_data_text = json.dumps(summary, ensure_ascii=False, default=str)
                        log_data['responseData'] = self._truncate_text(
                            response_data_text, self.max_response_data_length
                        )

                    except Exception as e:
                        log_data['responseData'] = json.dumps({
                            "error": "响应概要生成失败",
                            "detail": str(e)[:500]
                        }, ensure_ascii=False)

            except Exception as e:
                log_data['status'] = 1
                log_data['errorMsg'] = self._truncate_text(str(e), self.max_error_msg_length)
                logger.error(f'系统对接日志记录异常: {e}')
                raise e
            finally:
                # 计算耗时
                end_time = time.time()
                log_data['costTime'] = int((end_time - start_time) * 1000)  # 毫秒
                log_data['responseTime'] = datetime.now()

                # 异步保存日志，使用新的数据库会话
                asyncio.create_task(self._save_log_async(log_data))

            return result

        return wrapper

    async def _save_log_async(self, log_data: dict):
        """
        异步保存日志到数据库，使用独立的数据库会话

        :param log_data: 日志数据
        """
        from config.database import AsyncSessionLocal

        try:
            # 创建新的数据库会话
            async with AsyncSessionLocal() as db_session:
                log_data['requestParams'] = self._truncate_text(
                    log_data.get('requestParams', ''), self.max_request_param_length
                )
                log_data['responseData'] = self._truncate_text(
                    log_data.get('responseData', ''), self.max_response_data_length
                )
                log_data['errorMsg'] = self._truncate_text(
                    log_data.get('errorMsg', ''), self.max_error_msg_length
                )
                # 调试日志：打印实际的log_data内容
                # logger.info(f"准备保存系统对接日志数据: {log_data}")

                integration_log = IntegrationLogModel(
                    interfaceName=log_data['interfaceName'],
                    systemName=log_data['systemName'],
                    interfaceUrl=log_data['interfaceUrl'],
                    requestMethod=log_data['requestMethod'],
                    requestParams=log_data['requestParams'],
                    responseData=log_data['responseData'],
                    status=log_data['status'],
                    errorMsg=log_data['errorMsg'],
                    costTime=log_data['costTime'],
                    requestIp=log_data['requestIp'],
                    requestTime=log_data['requestTime'],
                    responseTime=log_data['responseTime'],
                    userAgent=log_data['userAgent'],
                    traceId=log_data['traceId'],
                    remark=log_data['remark'],
                )

                # 调试日志：打印IntegrationLogModel的内容
                # logger.info(f"IntegrationLogModel内容: {integration_log.model_dump()}")

                await IntegrationLogService.add_integration_log_services(db_session, integration_log)
                logger.info(f'系统对接日志保存成功: {log_data["interfaceName"]}')
        except Exception as e:
            logger.error(f'保存系统对接日志失败: {e}')


# 便捷的装饰器函数
def integration_log(
    title: str = '',
    system_name: str = '',
    business_type: BusinessType = BusinessType.OTHER,
    is_save_request_data: bool = True,
    is_save_response_data: bool = True,
    exclude_param_names: Optional[list] = None,
):
    """
    系统对接日志装饰器的便捷函数

    使用示例:
    @integration_log(title="用户查询", system_name="用户管理系统", business_type=BusinessType.SELECT)
    async def get_user_info(request: Request, user_id: int, query_db: AsyncSession = Depends(get_db)):
        # 接口逻辑
        pass
    """
    return IntegrationLog(
        title=title,
        system_name=system_name,
        business_type=business_type,
        is_save_request_data=is_save_request_data,
        is_save_response_data=is_save_response_data,
        exclude_param_names=exclude_param_names,
    )
