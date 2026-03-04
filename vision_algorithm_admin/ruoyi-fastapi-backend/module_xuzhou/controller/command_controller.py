import json
import asyncio
import time
from datetime import datetime
from typing import Optional

import aio_pika
from fastapi import APIRouter, Depends, Request
from fastapi import Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.dao.alg_dao import AlgDao
from module_xuzhou.service.alarm_service import AlarmService
from module_xuzhou.service.video_service import VideoService
from utils.log_util import logger
from utils.message_util import RabbitMQService
from utils.response_util import ResponseUtil
from config.env import SRSConfig, RabbitMQConfig
from config.get_rabbitmq import RabbitMQUtil
from config.get_srs import SRSUtil

commandController = APIRouter(prefix='/xuzhou/command', dependencies=[Depends(unified_auth)])

# 存储接收到的消息
received_messages = {}

# 设备状态缓存 - 以vid_id为key存储
device_status_cache = {}

# 视频推送时间缓存
video_start_time = {}


async def save_cache_message(message: dict):
    """
    保存预警消息到数据库
    """
    await AlarmService.save_alarm_message(message)



async def save_device_status(message: dict):
    """
    保存设备状态信息到缓存 - 以vid_id为key
    :param message: 设备状态消息，格式如：{'serial': '0004', 'type': 'devices', 'devices': [{'vid_id': 4, 'status': 'running'}]}
    """
    try:
        # 检查消息时间戳，超过10秒的数据丢弃
        message_time = message.get('time')
        if message_time:
            current_time = datetime.now().timestamp()
            if current_time - message_time > 10:
                logger.warning(f"丢弃过期数据 - 消息时间: {message_time}, 当前时间: {current_time}, 差异: {current_time - message_time}秒")
                return
        
        devices = message.get('devices', [])
        # 更新每个设备的状态（以vid_id为key）
        new_device_status = {}
        for device in devices:
            vid_id = device.get('vid_id')
            status = device.get('status')
            start_time = device.get('start_time')
            
            if vid_id is not None and status:
                new_device_status[vid_id] = {
                    'status': status,
                    'update_time': datetime.now().isoformat(),
                    'start_time': start_time,
                    'vid_id': vid_id,
                    'serial': message.get('serial')  # 保留serial信息用于参考
                }
                logger.info(f"更新设备状态 - vid_id: {vid_id}, status: {status}")
            else:
                logger.warning(f"设备信息不完整: {device}")
        
        device_status_cache.clear()
        device_status_cache.update(new_device_status)
        logger.info(f"缓存设备状态：{device_status_cache}")
        
        # 检查是否需要关闭流
        try:
            # 避免循环引用，在函数内部导入
            from module_task.inference_monitor import get_inference_monitor
            from config.database import AsyncSessionLocal
            monitor = get_inference_monitor()
            
            async with AsyncSessionLocal() as session:
                for vid_id, info in new_device_status.items():
                    if info.get('status') == 'running':
                        if time.time() - info.get('start_time', 0) < 40:
                            continue
                            
                        should_stop = True
                        
                        # 获取该视频的定时任务配置
                        job_config = await monitor.get_video_job_config(session, vid_id)
                        
                        # 构造任务对象用于检查
                        task = {
                            'vid_id': vid_id,
                            'job_config': job_config
                        }
                        
                        current_time = datetime.now()
                        if await monitor.should_task_run_now(session, task, current_time.hour, current_time.weekday()):
                            should_stop = False
                            # logger.info(f"视频 {vid_id} 在任务时间范围内，保持运行")
                        
                        # 2. 如果不在时间范围内，检查是否有用户在观看
                    if should_stop:
                        # 检查SRS是否有客户端连接
                        # 使用publish_{vid_id}作为流名称
                        client_count = await asyncio.to_thread(SRSUtil.check_stream_players, f'publish_{vid_id}')
                        
                        if client_count > 1:  # 有人观看（大于1是因为包含推流端自己），不关闭
                            should_stop = False
                    
                    if should_stop:
                        video_start_time.get(vid_id, 0)
                        if time.time() - video_start_time.get(vid_id, 0) < 60:
                            should_stop = False
                            logger.info(f"视频 {vid_id} 最近10秒内有推流，保持运行")
                    
                    if should_stop:
                        logger.info(f"视频 {vid_id} 无监听者且不在任务时间，发送停止指令")
                        # 发送停止消息
                        algorithm_service = 'algorithm_0004'
                        message_data = {
                            'vid_id': vid_id,
                            'serial': algorithm_service,
                            'action': 'stop',
                            'reason': 'auto_stop_no_listeners',
                            'stop_time': datetime.now().isoformat()
                        }
                        message_json = json.dumps(message_data, ensure_ascii=False)
                        
                        connection = await RabbitMQUtil.create_rabbitmq_pool()
                        async with connection:
                            channel = await connection.channel()
                            exchange = await channel.declare_exchange(
                                RabbitMQConfig.rabbitmq_exchange, aio_pika.ExchangeType.DIRECT, durable=True
                            )
                            await exchange.publish(
                                aio_pika.Message(body=message_json.encode()), 
                                routing_key=algorithm_service
                            )
                            logger.info(f'成功发送停止消息: {message_json}')

        except Exception as e:
            logger.error(f"检查自动停止失败: {e}")
        
    except Exception as e:
        logger.error(f"保存设备状态失败: {e}, message: {message}")


def cleanup_old_device_status():
    """
    清理过期的设备状态缓存（超过10秒的）
    """
    try:
        current_time = datetime.now().timestamp()
        expired_keys = []
        
        for vid_id, status_info in device_status_cache.items():
            update_time_str = status_info.get('update_time')
            if update_time_str:
                try:
                    update_time = datetime.fromisoformat(update_time_str).timestamp()
                    if current_time - update_time > 10:
                        expired_keys.append(vid_id)
                except (ValueError, AttributeError):
                    # 如果解析时间失败，认为该条目无效，也清理掉
                    expired_keys.append(vid_id)
        
        # 清理过期条目
        for vid_id in expired_keys:
            del device_status_cache[vid_id]
            logger.info(f"清理过期设备状态 - vid_id: {vid_id}")
            
        if expired_keys:
            logger.info(f"清理完成，共清理 {len(expired_keys)} 个过期状态")
            
    except Exception as e:
        logger.error(f"清理过期设备状态失败: {e}")


# 推送视频配置请求模型
class PushVideoConfigRequest(BaseModel):
    vid_id: Optional[int] = Field(default=None, description='视频ID')
    vid_serial: Optional[str] = Field(default=None, description='视频序列号')
    vid_stream: Optional[str] = Field(default=None, description='视频流地址')


async def message_callback(message: aio_pika.IncomingMessage):
    """消息回调处理函数"""
    async with message.process():
        msg = message.body.decode()
        global received_messages
        try:
            received_messages = json.loads(msg)
        except json.JSONDecodeError as e:
            logger.error(f"解析RabbitMQ消息失败 [tag:{message.delivery_tag}]: {e} - 原始内容: {msg}")
            return  # 退出，消息将被Ack（因为未抛出异常），避免死循环

        # logger.info(f"收到RabbitMQ消息[exchange:{message.exchange}][routing_key:{message.routing_key}]: {received_messages['type']}")
        if received_messages.get('type') == 'heartbeat':
            return
        elif received_messages.get('type') == 'alarm':
            # 创建消息副本用于日志打印（去除图片字段）
            log_msg = received_messages.copy()
            if 'data' in log_msg and isinstance(log_msg['data'], list):
                log_data = []
                for item in log_msg['data']:
                    if isinstance(item, dict):
                        item_copy = item.copy()
                        if 'image' in item_copy:
                            item_copy['image'] = f"[Base64 Image Length: {len(item_copy['image'])}]"
                        log_data.append(item_copy)
                log_msg['data'] = log_data
            
            logger.info(f"收到报警消息 [tag:{message.delivery_tag}] [id:{message.message_id}] [redelivered:{message.redelivered}] - 内容: {json.dumps(log_msg, ensure_ascii=False)}")
            
            await save_cache_message(received_messages)
            logger.info(f"报警消息处理完成 [tag:{message.delivery_tag}]")
            return
        elif received_messages.get('type') == 'devices':
            # 缓存视频推理状态
            # logger.info(f"收到设备状态消息: {received_messages}")
            await save_device_status(received_messages)
            return

        # logger.info(f"收到RabbitMQ消息[exchange:{message.exchange}][routing_key:{message.routing_key}]: {msg}")
        # print(f"收到消息: {msg}")


@commandController.post('/send_message', summary='发送RabbitMQ消息', include_in_schema=False)
@integration_log(
    title='发送RabbitMQ消息',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def send_message(request: Request, message: str = Body(...)):
    """
    发送消息到RabbitMQ测试队列
    """
    await RabbitMQService.send_message(request.app, 'test_queue', message)
    return {'code': 200, 'msg': '消息发送成功', 'data': message}


@commandController.get('/receive_messages', summary='获取接收到的RabbitMQ消息', include_in_schema=False)
@integration_log(
    title='获取接收到的RabbitMQ消息',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def get_received_messages(request: Request):
    """
    获取已接收的RabbitMQ消息列表
    """
    return {'code': 200, 'msg': '操作成功', 'data': received_messages}


@commandController.post('/start_consumer', summary='启动消息消费者', include_in_schema=False)
@integration_log(
    title='启动消息消费者',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def start_consumer(request: Request):
    """
    启动RabbitMQ消息消费者
    """
    await RabbitMQService.consume_messages(request.app, 'test_queue', message_callback)
    return {'code': 200, 'msg': '消费者已启动'}


@commandController.get('/running/clients', summary='启动消息消费者', include_in_schema=False)
@integration_log(
    title='获取运行中的客户端',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def running_clients(request: Request):
    logger.info(received_messages)

    return {'code': 200, 'msg': '', 'data': received_messages}


@commandController.post('/push_video_config', summary='推送视频配置，启动推理并返回视频流地址')
@integration_log(
    title='推送视频配置',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def push_video_config(request: Request, push_request: PushVideoConfigRequest, db: AsyncSession = Depends(get_db)):
    """
    根据视频ID获取视频流配置详细信息，格式化后推送到消息队列

    :param request: 请求对象
    :param push_request: 推送请求参数
    :param db: 数据库会话
    :return: 推送结果
    """
    try:
        # 从数据库获取视频详细信息
        if push_request.vid_id:
            video_detail = await VideoService.video_detail_services(db, push_request.vid_id)
        elif push_request.vid_serial:
            video_detail = await VideoService.video_detail_by_serial_services(db, push_request.vid_serial)
        else:
            return ResponseUtil.error(msg='请提供视频ID或视频序列号')
        
        if push_request.vid_stream:
            vid_stream = push_request.vid_stream
        else:
            vid_stream = 'open'

        if not video_detail:
            msg = f'未找到ID为{push_request.vid_id}的视频信息' if push_request.vid_id else f'未找到序列号为{push_request.vid_serial}的视频信息'
            return ResponseUtil.error(msg=msg)

        logger.info(video_detail)
        # 解析算法信息
        algorithms = []
        if video_detail.get('vid_algorithm'):
            vid_algorithm = video_detail['vid_algorithm']

            # 如果是字符串，尝试解析为JSON
            if isinstance(vid_algorithm, str):
                try:
                    vid_algorithm = json.loads(vid_algorithm)
                except json.JSONDecodeError:
                    logger.error(f'解析视频算法信息失败: {vid_algorithm}')
                    vid_algorithm = []

            # 格式化算法信息
            if isinstance(vid_algorithm, list):
                for alg in vid_algorithm:
                    if isinstance(alg, dict):
                        # 获取算法ID
                        alg_id = alg.get('algId')
                        if not alg_id:
                            continue

                        # Determine alg_serial
                        alg_serial = str(alg_id)

                        # Check if alg_id is a number (ID) or string (Serial)
                        if str(alg_id).isdigit():
                            # 从数据库查询算法详细信息获取序列号
                            try:
                                alg_detail = await AlgDao.get_alg_detail_by_id(db, int(alg_id))
                                if alg_detail and alg_detail.alg_serial:
                                    alg_serial = alg_detail.alg_serial
                            except Exception as e:
                                logger.warning(f"Query algorithm by ID {alg_id} failed: {e}")

                        # 获取算法配置信息
                        alg_config = alg.get('algDefaultConf', {})

                        # 如果配置是字符串，尝试解析为JSON
                        if isinstance(alg_config, str):
                            try:
                                alg_config = json.loads(alg_config)
                            except json.JSONDecodeError:
                                alg_config = {}

                        # 构建算法信息
                        algorithm_info = {
                            'code': alg_serial,  # 使用算法序列号作为code
                        }

                        # 动态添加所有配置字段
                        if isinstance(alg_config, dict):
                            algorithm_info.update(alg_config)
                        algorithms.append(algorithm_info)

        # 生成随机字符串作为publish_path
        # import uuid

        # publish_path = str(uuid.uuid4()).replace('-', '')
        publish_path = f'publish_{video_detail.get("vid_id")}'

        # 构建SRS取流地址（FLV格式）
        # 获取客户端访问的服务器地址和协议
        host = request.headers.get('host', request.client.host if request.client else 'localhost')
        # 检测请求协议（HTTP或HTTPS）
        scheme = 'https' if request.url.scheme == 'https' else 'http'
        srs_flv_url = f'{scheme}://{SRSConfig.srs_flv_url}/live/{publish_path}.flv'

        algorithm_service = 'algorithm_0004'
        logger.info(f'{video_detail}')
        
        if video_detail.get("vid_id") in device_status_cache:
            action = 'update'
        else:
            action = 'start'
            video_start_time[video_detail.get("vid_id")] = time.time()

        # 构建推送消息格式
        message_data = {
            'vid_id': video_detail.get("vid_id"),
            'vid_serial': video_detail.get('vid_serial', ''),
            'serial': algorithm_service,
            'action': action,
            'stream': vid_stream,
            'algorithms': algorithms,
            'stream_type': video_detail.get('vid_type', 'rtsp'),
            'stream_url': video_detail.get('vid_uri', ''),
            'publish_path': publish_path,
        }

        # 转换为JSON字符串
        message_json = json.dumps(message_data, ensure_ascii=False)

        # 推送到消息队列
        await RabbitMQService.send_message(request.app, algorithm_service, message_json)

        logger.info(f'成功推送视频配置到消息队列: {message_json}')

        # 构建接口返回数据，包含取流地址
        response_data = {
            'serial': video_detail.get('vidSerial', ''),
            'action': 'start',
            # "algorithms": algorithms,
            # "stream_type": video_detail.get('vidType', 'rtsp'),
            # "stream_url": video_detail.get('vidUri', ''),
            'publish_path': publish_path,
            'srs_flv_url': srs_flv_url,
        }

        return ResponseUtil.success(data=response_data, msg='视频配置推送成功')

    except Exception as e:
        logger.error(f'推送视频配置失败: {str(e)}')
        return ResponseUtil.error(msg=f'推送视频配置失败: {str(e)}')


@commandController.get('/cache_messages/{key}', summary='根据key获取预警消息')
async def get_cache_messages_by_key(request: Request, key: str):
    """
    根据key获取缓存消息数据

    :param key: 消息key
    :return: 对应key的缓存消息列表
    """
    return ResponseUtil.success(data=[], msg=f'未找到key为{key}的缓存消息')
    # try:
    #     logger.info(f'获取缓存消息: {cache_messages.keys()}')
    #     if key in cache_messages:
    #         return ResponseUtil.success(data=cache_messages[key], msg='获取缓存消息成功')
    #     else:
    #         return ResponseUtil.success(data=[], msg=f'未找到key为{key}的缓存消息')
    # except Exception as e:
    #     logger.error(f'获取缓存消息失败: {str(e)}')
    #     return ResponseUtil.error(msg=f'获取缓存消息失败: {str(e)}')
    # finally:
    #     if key in cache_messages:
    #         del cache_messages[key]


@commandController.get('/device_status', summary='获取设备状态缓存')
@integration_log(
    title='获取设备状态缓存',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def get_device_status_cache(request: Request, vid_id: int = None):
    """
    获取设备状态缓存信息 - 以vid_id为key
    
    :param vid_id: 视频ID（可选）
    :return: 设备状态信息
    """
    try:
        # 先清理过期数据
        cleanup_old_device_status()
        
        if vid_id:
            # 获取指定vid_id的状态
            if vid_id in device_status_cache:
                return ResponseUtil.success(
                    data=device_status_cache[vid_id],
                    msg='获取设备状态成功'
                )
            else:
                return ResponseUtil.success(
                    data=None,
                    msg='未找到指定设备状态'
                )
        else:
            # 获取所有设备状态
            return ResponseUtil.success(
                data=device_status_cache,
                msg='获取所有设备状态成功'
            )
    except Exception as e:
        logger.error(f'获取设备状态失败: {str(e)}')
        return ResponseUtil.error(msg=f'获取设备状态失败: {str(e)}')
