import json
import asyncio
import time
from datetime import datetime
from typing import Any, Optional

import aio_pika
import cv2
from fastapi import APIRouter, Depends, Request
from fastapi import Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from algorithm.runtime_service import AlgorithmRuntimeService, algorithm_run_registry
from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.dao.alg_dao import AlgDao
from module_xuzhou.service.alarm_service import AlarmService
from module_xuzhou.service.box_network import build_box_base_urls
from module_xuzhou.service.video_service import VideoService
from utils.log_util import logger
from utils.message_util import RabbitMQService
from utils.response_util import ResponseUtil
from config.env import SRSConfig
from config.get_rabbitmq import RabbitMQUtil
from config.get_srs import SRSUtil

def _encode_jpeg(frame) -> bytes:
    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return jpeg.tobytes()


commandController = APIRouter(prefix='/xuzhou/command', dependencies=[Depends(unified_auth)])

# 公开路由 — 供 <img> 标签直连 MJPEG 流，不经过 unified_auth
localStreamController = APIRouter(prefix='/xuzhou/command')

# 存储接收到的消息
received_messages = {}

# 设备状态缓存 - 以vid_id为key存储
device_status_cache = {}
_vid_validated_at: dict[int, float] = {}  # vid_id -> 上次校验时间戳，定期重验防删除后残留
_warned_missing_vids: set[int] = set()  # 已警告过不存在的设备，避免重复刷屏
VID_REVALIDATE_INTERVAL = 60  # 已在缓存中的设备每60秒重新校验一次数据库

# 视频推送时间缓存
video_start_time = {}

# 盒子上线注册表 {serial: {box_name, host, capabilities, last_seen, status}}
box_registry: dict[str, dict] = {}
BOX_HEARTBEAT_TIMEOUT = 120  # 盒子心跳超时（秒），超时自动清理


def cleanup_stale_boxes():
    """清理心跳超时的盒子"""
    now = datetime.now()
    stale = []
    for serial, info in box_registry.items():
        try:
            last_seen = datetime.fromisoformat(info.get('last_seen', ''))
            if (now - last_seen).total_seconds() > BOX_HEARTBEAT_TIMEOUT:
                stale.append(serial)
        except (ValueError, TypeError):
            stale.append(serial)
    for serial in stale:
        logger.info(f'清理超时盒子: {serial}')
        del box_registry[serial]


async def save_box_register(message: dict):
    """处理盒子上线注册/心跳消息"""
    serial = message.get('serial', '')
    if not serial:
        return
    box_registry[serial] = {
        'serial': serial,
        'box_name': message.get('box_name', f'box_{serial}'),
        'host': message.get('host', ''),
        'ip': message.get('ip', ''),
        'port': message.get('port', 9100),
        'capabilities': message.get('capabilities', []),
        'last_seen': datetime.now().isoformat(),
        'status': 'online',
    }


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

        # 过滤不存在的设备：盒子上报的 vid_id 必须在数据库中存在
        now_ts = datetime.now().timestamp()
        incoming_vid_ids = {d.get('vid_id') for d in devices if d.get('vid_id') is not None}
        need_check_ids = incoming_vid_ids - set(device_status_cache.keys())
        # 已在缓存中的设备，定期重验防止数据库删除后残留
        for vid_id in incoming_vid_ids & set(device_status_cache.keys()):
            last_check = _vid_validated_at.get(vid_id, 0)
            if now_ts - last_check > VID_REVALIDATE_INTERVAL:
                need_check_ids.add(vid_id)
        if need_check_ids:
            from config.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                for vid_id in list(need_check_ids):
                    try:
                        video = await VideoService.video_detail_services(session, vid_id)
                        if video:
                            _vid_validated_at[vid_id] = now_ts
                        else:
                            if vid_id not in _warned_missing_vids:
                                logger.warning(f"盒子 {message.get('serial')} 上报了数据库中不存在的设备 vid_id={vid_id}，已忽略（后续不再警告）")
                                _warned_missing_vids.add(vid_id)
                            need_check_ids.discard(vid_id)
                            # 同时清除缓存中的残留
                            device_status_cache.pop(vid_id, None)
                            _vid_validated_at.pop(vid_id, None)
                    except Exception:
                        need_check_ids.discard(vid_id)
            devices = [d for d in devices if d.get('vid_id') is None or d.get('vid_id') in device_status_cache or d.get('vid_id') in need_check_ids]

        box_serial = message.get('serial')
        if box_serial is not None:
            reported_vid_ids = {device.get('vid_id') for device in devices if device.get('vid_id') is not None}
            now_iso = datetime.now().isoformat()
            for cached_vid_id, cached_info in list(device_status_cache.items()):
                if cached_info.get('serial') == box_serial and cached_vid_id not in reported_vid_ids:
                    device_status_cache[cached_vid_id] = {
                        **cached_info,
                        'status': 'stopped',
                        'update_time': now_iso,
                        'start_time': None,
                        'error_message': '',
                    }
                    algorithm_run_registry.mark_camera_runs_status(cached_vid_id, 'stopped', runtime_type='external_box')
                    logger.info(f"盒子 {box_serial} 未上报设备 {cached_vid_id}，标记为 stopped")

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
                    'serial': message.get('serial'),
                    'error_message': device.get('error_message', ''),
                }
                logger.info(f"更新设备状态 - vid_id: {vid_id}, status: {status}")
                if status == 'running':
                    algorithm_run_registry.mark_camera_runs_status(vid_id, 'running', runtime_type='external_box')
                elif status in {'stopped', 'failed', 'error'}:
                    algorithm_run_registry.mark_camera_runs_status(vid_id, status, runtime_type='external_box')
            else:
                logger.warning(f"设备信息不完整: {device}")
        
        device_status_cache.update(new_device_status)
        if new_device_status:
            logger.info(f"缓存设备状态：{device_status_cache}")
        
        # 检查是否需要关闭流
        try:
            # 避免循环引用，在函数内部导入
            from module_task.inference_monitor import get_inference_monitor
            from config.database import AsyncSessionLocal
            monitor = get_inference_monitor()
            
            async with AsyncSessionLocal() as session:
                video_type_cache: dict[int, str] = {}
                for vid_id, info in new_device_status.items():
                    if info.get('status') != 'running':
                        continue

                    if time.time() - info.get('start_time', 0) < 40:
                        continue

                    if vid_id not in video_type_cache:
                        video_detail = await VideoService.video_detail_services(session, vid_id)
                        video_type_cache[vid_id] = (video_detail or {}).get('vidType') or (video_detail or {}).get('vid_type') or ''
                    if video_type_cache.get(vid_id) in {'local', 'usb'}:
                        continue

                    should_stop = True

                    # 获取该视频的定时任务配置
                    job_config = await monitor.get_video_job_config(session, vid_id)

                    # 构造任务对象用于检查
                    task = {'vid_id': vid_id, 'job_config': job_config}

                    current_time = datetime.now()
                    if await monitor.should_task_run_now(session, task, current_time.hour, current_time.weekday()):
                        should_stop = False

                    # 检查SRS是否有客户端连接 (SRS不可达时不自动停止)
                    client_count = await asyncio.to_thread(SRSUtil.check_stream_players, f'publish_{vid_id}')
                    if client_count < 0:
                        should_stop = False  # SRS不可达，不自动停止
                    elif client_count > 1:
                        should_stop = False  # 有观众，不停止

                    if time.time() - video_start_time.get(vid_id, 0) < 60:
                        should_stop = False

                    if should_stop:
                        box_serial = new_device_status.get(vid_id, {}).get('serial') or '0004'
                        logger.info(f"视频 {vid_id} 无监听者且不在任务时间，发送停止指令到盒子 {box_serial}")
                        # 发送停止消息
                        algorithm_service = f'algorithm_{box_serial}'
                        message_data = {
                            'vid_id': vid_id,
                            'serial': algorithm_service,
                            'action': 'stop',
                            'reason': 'auto_stop_no_listeners',
                            'stop_time': datetime.now().isoformat()
                        }
                        message_json = json.dumps(message_data, ensure_ascii=False)
                        await RabbitMQUtil.publish_message(algorithm_service, message_json)
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
    action: Optional[str] = Field(default=None, description='操作类型: start/update/stop，留空自动判断')


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
        elif received_messages.get('type') == 'box_register':
            await save_box_register(received_messages)
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

        vid_id = video_detail.get('vidId') or video_detail.get('vid_id')
        vid_serial = video_detail.get('vidSerial') or video_detail.get('vid_serial') or ''
        vid_type = video_detail.get('vidType') or video_detail.get('vid_type') or 'rtsp'
        vid_uri = video_detail.get('vidUri') or video_detail.get('vid_uri') or ''

        logger.info(video_detail)
        resolved_bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)
        external_bindings = [binding for binding in resolved_bindings if binding.runtime_type == 'external_box']
        runtime_bindings = []
        # 解析算法信息
        algorithms = []
        if external_bindings:
            for binding in external_bindings:
                algorithm_code = binding.algorithm_code
                if str(algorithm_code).isdigit():
                    try:
                        alg_detail = await AlgDao.get_alg_detail_by_id(db, int(algorithm_code))
                        if alg_detail and alg_detail.alg_serial:
                            algorithm_code = alg_detail.alg_serial
                    except Exception as e:
                        logger.warning(f"Query algorithm by ID {algorithm_code} failed: {e}")
                algorithm_info = {'code': algorithm_code}
                algorithm_info.update(binding.params)
                algorithms.append(algorithm_info)
                runtime_bindings.append(
                    AlgorithmRuntimeService.create_external_box_binding(
                        vid_id=binding.vid_id,
                        algorithm_code=algorithm_code,
                        algorithm_name=binding.algorithm_name,
                        params=binding.params,
                        priority=binding.priority,
                    )
                )
        elif video_detail.get('vidAlgorithm') or video_detail.get('vid_algorithm'):
            vid_algorithm = video_detail.get('vidAlgorithm') or video_detail.get('vid_algorithm')

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
        publish_path = f'publish_{vid_id}'

        # 构建SRS取流地址（FLV格式）
        # 获取客户端访问的服务器地址和协议
        host = request.headers.get('host', request.client.host if request.client else 'localhost')
        # 检测请求协议（HTTP或HTTPS）
        scheme = 'https' if request.url.scheme == 'https' else 'http'
        srs_flv_url = f'{scheme}://{SRSConfig.srs_flv_url}/live/{publish_path}.flv'

        vid_box_serial = video_detail.get('vidBoxSerial') or video_detail.get('vid_box_serial') or '0004'
        algorithm_service = f'algorithm_{vid_box_serial}'
        logger.info(f'camera {vid_id} → box {vid_box_serial} | {video_detail}')
        
        if push_request.action:
            action = push_request.action
        elif vid_id in device_status_cache:
            action = 'update'
        else:
            action = 'start'
            video_start_time[vid_id] = time.time()

        # 构建推送消息格式
        message_data = {
            'vid_id': vid_id,
            'vid_serial': vid_serial,
            'serial': algorithm_service,
            'action': action,
            'stream': vid_stream,
            'algorithms': algorithms,
            'stream_type': vid_type,
            'stream_url': vid_uri,
            'publish_path': publish_path,
        }

        # 转换为JSON字符串
        message_json = json.dumps(message_data, ensure_ascii=False)

        # 推送到消息队列
        await RabbitMQService.send_message(request.app, algorithm_service, message_json)
        if action in {'start', 'update'}:
            for binding in runtime_bindings:
                algorithm_run_registry.start_run(
                    binding,
                    external_task_id=f'{publish_path}_{binding.algorithm_code}',
                    status='waiting_box',
                    error_message='等待外接盒子设备状态回调'
                )
        elif action == 'stop':
            algorithm_run_registry.stop_camera_runs(vid_id)

        logger.info(f'成功推送视频配置到消息队列: {message_json}')

        # 构建接口返回数据，包含取流地址
        response_data = {
            'serial': vid_serial,
            'action': 'start',
            # "algorithms": algorithms,
            # "stream_type": video_detail.get('vidType', 'rtsp'),
            # "stream_url": video_detail.get('vidUri', ''),
            'publish_path': publish_path,
            'srs_flv_url': srs_flv_url,
            'runs': [
                {
                    'runId': run.run_id,
                    'vidId': run.vid_id,
                    'algorithmCode': run.algorithm_code,
                    'algorithmName': run.algorithm_name,
                    'runtimeType': run.runtime_type,
                    'status': run.status,
                    'externalTaskId': run.external_task_id,
                    'errorMessage': run.error_message,
                }
                for run in algorithm_run_registry.list_camera_runs(vid_id)
            ],
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


@commandController.get('/boxes', summary='获取在线盒子列表（含算法信息）')
@integration_log(
    title='获取在线盒子列表',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def get_boxes(request: Request, query_db: AsyncSession = Depends(get_db)):
    """获取已注册上线的盒子列表，在线盒子附带摄像头和算法信息"""
    cleanup_stale_boxes()
    now = datetime.now().timestamp()
    online = {}
    offline = {}
    for serial, info in box_registry.items():
        try:
            last_seen = datetime.fromisoformat(info['last_seen']).timestamp()
        except Exception:
            last_seen = 0
        if now - last_seen < 60:  # 60秒内有心跳视为在线
            online[serial] = info
        else:
            offline[serial] = info

    # 为在线盒子加载绑定的摄像头和算法信息
    online_list = []
    for serial, box_info in online.items():
        box_data = dict(box_info)
        try:
            cameras = await _get_box_cameras_with_algorithms(query_db, serial)
            box_data['cameras'] = cameras
            box_data['cameraCount'] = len(cameras)
        except Exception as e:
            logger.error(f'加载盒子 {serial} 摄像头信息失败: {e}')
            box_data['cameras'] = []
            box_data['cameraCount'] = 0
        online_list.append(box_data)

    return ResponseUtil.success(data={
        'online': online_list,
        'offline': list(offline.values()),
        'online_count': len(online_list),
        'total': len(box_registry),
    })


async def _get_box_cameras_with_algorithms(query_db: AsyncSession, box_serial: str) -> list[dict]:
    """查询绑定到指定盒子的摄像头及其算法配置和运行状态"""
    from sqlalchemy import select
    from module_xuzhou.entity.do.video_do import XuzhouVideo

    result = await query_db.execute(
        select(XuzhouVideo).where(XuzhouVideo.vid_box_serial == str(box_serial))
    )
    cameras = result.scalars().all()

    camera_list = []
    for cam in cameras:
        video_dict = {
            'vid_id': cam.vid_id,
            'vid_name': cam.vid_name,
            'vid_serial': cam.vid_serial,
            'vid_type': cam.vid_type,
            'vid_algorithm': cam.vid_algorithm,
        }
        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_dict)
        algorithms = []
        for b in bindings:
            run = algorithm_run_registry.get_run(b.vid_id, b.algorithm_code)
            alg_status = run.status if run else 'stopped'
            algorithms.append({
                'algorithmCode': b.algorithm_code,
                'algorithmName': b.algorithm_name,
                'runtimeType': b.runtime_type,
                'status': alg_status,
            })
        camera_list.append({
            'vidId': cam.vid_id,
            'vidName': cam.vid_name or f'摄像头{cam.vid_id}',
            'vidSerial': cam.vid_serial or '',
            'vidType': cam.vid_type or '',
            'algorithms': algorithms,
        })

    return camera_list


@commandController.get('/camera_stream_url/{vid_id}', summary='获取盒子摄像头实时流地址')
async def camera_stream_url(vid_id: int, query_db: AsyncSession = Depends(get_db)):
    """返回盒子本地 MJPEG 流地址，供前端 img 直接播放。"""
    from module_xuzhou.service.video_service import VideoService

    video = await VideoService.video_detail_services(query_db, vid_id)
    if not video:
        return ResponseUtil.error(msg='摄像头不存在')

    box_serial = video.get('vidBoxSerial') or video.get('vid_box_serial')
    if not box_serial:
        return ResponseUtil.error(msg='摄像头未绑定盒子')

    box = box_registry.get(str(box_serial))
    if not box:
        return ResponseUtil.error(msg='盒子不在线')

    base_urls = build_box_base_urls(box)
    if not base_urls:
        return ResponseUtil.error(msg='盒子IP未知')

    stream_urls = [f'{base_url}/cameras/{vid_id}/stream' for base_url in base_urls]
    return ResponseUtil.success(data={
        'vidId': vid_id,
        'boxSerial': box_serial,
        'streamUrl': stream_urls[0],
        'streamUrls': stream_urls,
    })


@commandController.get('/camera_snapshot/{vid_id}', summary='获取摄像头实时快照')
async def camera_snapshot(vid_id: int, query_db: AsyncSession = Depends(get_db)):
    """通过盒子本地API获取摄像头快照，返回JPEG图片"""
    from module_xuzhou.service.video_service import VideoService

    video = await VideoService.video_detail_services(query_db, vid_id)
    if not video:
        return ResponseUtil.error(msg='摄像头不存在')

    box_serial = video.get('vidBoxSerial') or video.get('vid_box_serial')
    if not box_serial:
        return ResponseUtil.error(msg='摄像头未绑定盒子')

    box = box_registry.get(str(box_serial))
    if not box:
        return ResponseUtil.error(msg='盒子不在线')

    base_urls = build_box_base_urls(box)
    if not base_urls:
        return ResponseUtil.error(msg='盒子IP未知')

    import httpx
    last_error = ''
    for base_url in base_urls:
        snapshot_url = f'{base_url}/cameras/{vid_id}/snapshot'
        logger.info(f'获取摄像头快照: vid_id={vid_id}, box_serial={box_serial}, url={snapshot_url}')
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(snapshot_url)
            if resp.status_code == 200:
                from starlette.responses import Response
                logger.info(f'获取摄像头快照成功: vid_id={vid_id}, box_serial={box_serial}, url={snapshot_url}')
                return Response(content=resp.content, media_type="image/jpeg")
            last_error = f'盒子返回错误: {resp.status_code}'
            logger.warning(f'获取摄像头快照失败: vid_id={vid_id}, box_serial={box_serial}, url={snapshot_url}, status={resp.status_code}, body={resp.text[:200]}')
        except Exception as e:
            last_error = str(e)
            logger.exception(f'连接盒子快照接口失败: vid_id={vid_id}, box_serial={box_serial}, url={snapshot_url}')

    return ResponseUtil.error(
        msg='无法连接盒子本地服务，请检查盒子服务、网络和端口',
        data={
            'vidId': vid_id,
            'boxSerial': box_serial,
            'triedUrls': [f'{base_url}/cameras/{vid_id}/snapshot' for base_url in base_urls],
            'detail': last_error,
        },
    )


# ── 本地服务器摄像头（无盒子）──────────────────────────────────────────

@commandController.get('/local_camera/start/{vid_id}', summary='启动本地摄像头采集')
async def local_camera_start(vid_id: int, query_db: AsyncSession = Depends(get_db)):
    """对未绑定盒子的摄像头启动 OpenCV 本地采集。"""
    from module_xuzhou.service.video_service import VideoService
    from module_xuzhou.service.local_camera_service import local_camera_manager

    video = await VideoService.video_detail_services(query_db, vid_id)
    if not video:
        return ResponseUtil.error(msg='摄像头不存在')

    vid_box_serial = video.get('vidBoxSerial') or video.get('vid_box_serial') or ''
    if vid_box_serial:
        return ResponseUtil.error(msg='盒子摄像头请使用 /push_video_config 启动')

    if local_camera_manager.running(vid_id):
        return ResponseUtil.success(data=local_camera_manager.get_status(vid_id), msg='摄像头已在运行')

    source = video.get('vidUri') or video.get('vid_uri') or '0'
    stream_type = video.get('vidType') or video.get('vid_type') or 'usb'
    err = local_camera_manager.start_camera(vid_id, str(source), stream_type)
    if err:
        return ResponseUtil.error(msg=err)

    return ResponseUtil.success(data=local_camera_manager.get_status(vid_id), msg='本地摄像头采集已启动')


@commandController.get('/local_camera/stop/{vid_id}', summary='停止本地摄像头采集')
async def local_camera_stop(vid_id: int):
    from module_xuzhou.service.local_camera_service import local_camera_manager
    local_camera_manager.stop_camera(vid_id)
    return ResponseUtil.success(msg='本地摄像头采集已停止')


@commandController.get('/local_camera/status/{vid_id}', summary='本地摄像头采集状态')
async def local_camera_status(vid_id: int):
    from module_xuzhou.service.local_camera_service import local_camera_manager
    return ResponseUtil.success(data=local_camera_manager.get_status(vid_id))


@commandController.get('/local_camera/runs', summary='本地算法运行记录')
async def local_camera_runs(vid_id: int, page_num: int = 1, page_size: int = 20):
    """查询指定摄像头的本地算法运行记录"""
    from module_xuzhou.dao.local_algorithm_run_log_dao import LocalAlgorithmRunLogDao
    from module_xuzhou.entity.vo.local_algorithm_run_log_vo import LocalAlgorithmRunLogQueryModel
    from config.database import AsyncSessionLocal

    query = LocalAlgorithmRunLogQueryModel(vid_id=vid_id, page_num=page_num, page_size=page_size)
    async with AsyncSessionLocal() as session:
        result = await LocalAlgorithmRunLogDao.list_by_vid(session, query, is_page=True)
    return ResponseUtil.success(data=result, msg='获取运行记录成功')


@commandController.get('/local_camera/snapshot/{vid_id}', summary='本地摄像头实时快照')
async def local_camera_snapshot(vid_id: int):
    """获取本地服务器摄像头的 JPEG 快照。"""
    from module_xuzhou.service.local_camera_service import local_camera_manager
    from starlette.responses import Response

    if not local_camera_manager.running(vid_id):
        return ResponseUtil.error(msg='本地摄像头未运行，请先启动')

    frame = local_camera_manager.get_snapshot(vid_id)
    if frame is None:
        return ResponseUtil.error(msg='摄像头暂未读取到画面')

    ok, jpeg = cv2.imencode(".jpg", frame)
    if not ok:
        return ResponseUtil.error(msg='快照编码失败')
    return Response(content=jpeg.tobytes(), media_type="image/jpeg",
                    headers={"Cache-Control": "no-cache"})


@commandController.get('/local_camera/stream_url/{vid_id}', summary='本地摄像头实时流地址')
async def local_camera_stream_url(vid_id: int, request: Request):
    """返回本地服务器摄像头的 MJPEG 流地址，供前端 img 直接播放。"""
    from module_xuzhou.service.local_camera_service import local_camera_manager

    if not local_camera_manager.running(vid_id):
        return ResponseUtil.error(msg='本地摄像头未运行，请先启动')

    scheme = 'https' if request.url.scheme == 'https' else 'http'
    host = request.headers.get('host', '127.0.0.1:9099')
    stream_url = f'{scheme}://{host}/xuzhou/command/local_camera/stream/{vid_id}'
    return ResponseUtil.success(data={
        'vidId': vid_id,
        'streamUrl': stream_url,
    })


@localStreamController.get('/local_camera/stream/{vid_id}', summary='本地摄像头MJPEG视频流')
async def local_camera_stream(vid_id: int):
    """MJPEG 流式输出本地摄像头画面。"""
    from module_xuzhou.service.local_camera_service import local_camera_manager
    from starlette.responses import StreamingResponse

    if not local_camera_manager.running(vid_id):
        return ResponseUtil.error(msg='本地摄像头未运行')

    async def generate():
        import asyncio as aio
        last_frame_idx = -1
        while local_camera_manager.running(vid_id):
            frame, idx = local_camera_manager.get_snapshot_with_idx(vid_id)
            if frame is not None and idx != last_frame_idx:
                last_frame_idx = idx
                data = await aio.to_thread(_encode_jpeg, frame)
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(data)).encode() +
                       b"\r\n\r\n" + data + b"\r\n")
            await aio.sleep(0.04)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )


# ── 摄像头列表模型 ──────────────────────────────────────────────────────

class CameraListItem(BaseModel):
    vid_id: Optional[int] = Field(default=None, description='视频/摄像头ID')
    vid_name: Optional[str] = Field(default=None, description='名称')
    vid_serial: Optional[str] = Field(default=None, description='序列号')
    vid_type: Optional[str] = Field(default=None, description='类型')
    vid_scene_name: Optional[str] = Field(default=None, description='场景名称')
    vid_algorithm_name: Optional[list[str]] = Field(default_factory=list, description='算法名称列表')
    vid_uri: Optional[str] = Field(default=None, description='视频流地址')
    status: str = Field(default='stopped', description='运行状态: running/stopped/error')
    start_time: Optional[Any] = Field(default=None, description='启动时间')
    update_time: Optional[str] = Field(default=None, description='状态更新时间')
    srs_flv_url: Optional[str] = Field(default=None, description='SRS FLV拉流地址')


class CameraListResponse(BaseModel):
    total: int = Field(default=0, description='总数')
    running_count: int = Field(default=0, description='运行中数量')
    stopped_count: int = Field(default=0, description='已停止数量')
    cameras: list[CameraListItem] = Field(default_factory=list, description='摄像头列表')


@commandController.get('/camera_list', summary='获取摄像头列表（含运行状态）')
@integration_log(
    title='获取摄像头列表',
    system_name='徐州指令管理系统',
    business_type=BusinessType.OTHER,
)
async def get_camera_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """获取所有配置的摄像头及其运行状态，供多路并行操作选择"""
    try:
        cleanup_old_device_status()

        from module_xuzhou.entity.vo.video_vo import VideoPageQueryModel
        from module_xuzhou.dao.video_dao import VideoDao
        from config.env import SRSConfig

        query_model = VideoPageQueryModel(page_num=1, page_size=9999)
        video_list_result = await VideoDao.get_video_list(db, query_model, is_page=False)

        video_rows: list[dict[str, Any]] = []
        if hasattr(video_list_result, 'rows'):
            video_rows = video_list_result.rows
        elif isinstance(video_list_result, list):
            video_rows = video_list_result

        scheme = 'https' if request.url.scheme == 'https' else 'http'
        running_count = 0
        stopped_count = 0
        cameras: list[dict[str, Any]] = []

        for v in video_rows:
            vid_id = v.get('vidId') or v.get('vid_id')
            vid_serial = v.get('vidSerial') or v.get('vid_serial')

            # 解析算法名列表
            alg_names: list[str] = []
            raw_alg = v.get('vidAlgorithmName') or v.get('vid_algorithm_name') or ''
            if isinstance(raw_alg, str):
                try:
                    parsed = json.loads(raw_alg)
                    alg_names = parsed if isinstance(parsed, list) else [raw_alg]
                except (json.JSONDecodeError, TypeError):
                    alg_names = [raw_alg]
            elif isinstance(raw_alg, list):
                alg_names = raw_alg

            # 获取运行状态
            device_info = device_status_cache.get(vid_id, {})
            status = device_info.get('status', 'stopped')
            start_time = device_info.get('start_time')
            update_time = device_info.get('update_time')

            if status == 'running':
                running_count += 1
            else:
                stopped_count += 1

            srs_flv_url = f'{scheme}://{SRSConfig.srs_flv_url}/live/publish_{vid_id}.flv'

            cameras.append({
                'vidId': vid_id,
                'vidName': v.get('vidName') or v.get('vid_name'),
                'vidSerial': vid_serial,
                'vidType': v.get('vidType') or v.get('vid_type'),
                'vidSceneName': v.get('vidSceneName') or v.get('vid_scene_name'),
                'vidAlgorithmName': alg_names,
                'vidUri': v.get('vidUri') or v.get('vid_uri'),
                'status': status,
                'startTime': start_time,
                'updateTime': update_time,
                'srsFlvUrl': srs_flv_url,
            })

        return ResponseUtil.success(
            data={
                'total': len(cameras),
                'runningCount': running_count,
                'stoppedCount': stopped_count,
                'cameras': cameras,
            },
            msg='获取摄像头列表成功',
        )

    except Exception as e:
        logger.error(f'获取摄像头列表失败: {str(e)}')
        return ResponseUtil.error(msg=f'获取摄像头列表失败: {str(e)}')
