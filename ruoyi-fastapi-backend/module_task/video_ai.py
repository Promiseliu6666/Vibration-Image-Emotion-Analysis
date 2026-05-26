import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import AsyncSessionLocal
from config.get_rabbitmq import RabbitMQUtil
from module_xuzhou.service.video_service import VideoService
from module_xuzhou.dao.alg_dao import AlgDao
from module_xuzhou.controller.command_controller import device_status_cache
from utils.log_util import logger



async def process_single_video(db: AsyncSession, vid_serial):
    try:
        # 根据序列号查询视频详情
        # 尝试作为序列号查询
        video_detail = await VideoService.video_detail_by_serial_services(db, str(vid_serial))
        
        # 如果找不到，尝试作为ID查询 (如果是数字字符串)
        if not video_detail and str(vid_serial).isdigit():
                video_detail = await VideoService.video_detail_services(db, int(vid_serial))

        if not video_detail:
            logger.warning(f"未找到视频信息: {vid_serial}")
            return
        
        vid_id = video_detail.get('vid_id')
        
        # 检查设备是否正在运行
        if vid_id in device_status_cache and device_status_cache[vid_id].get('status') == 'running':
            logger.info(f"视频 {vid_id} ({vid_serial}) 正在运行中，跳过启动")
            return
        
        logger.info(f"视频 {vid_id} ({vid_serial}) 未运行，准备启动推理，{device_status_cache}")
        
        # 解析算法信息
        algorithms = []
        if video_detail.get('vid_algorithm'):
            vid_algorithm = video_detail['vid_algorithm']
            
            # 如果是字符串，尝试解析为JSON
            if isinstance(vid_algorithm, str):
                try:
                    vid_algorithm = json.loads(vid_algorithm)
                except json.JSONDecodeError:
                        vid_algorithm = []
            
            # 格式化算法信息
            if isinstance(vid_algorithm, list):
                for alg in vid_algorithm:
                    if isinstance(alg, dict):
                        alg_id = alg.get('algId')
                        if not alg_id:
                            continue
                        
                        # Determine alg_serial
                        alg_serial = str(alg_id)
                        
                        # Check if alg_id is a number (ID) or string (Serial)
                        if str(alg_id).isdigit():
                            # From database query algorithm detail to get serial
                            try:
                                alg_detail = await AlgDao.get_alg_detail_by_id(db, int(alg_id))
                                if alg_detail and alg_detail.alg_serial:
                                    alg_serial = alg_detail.alg_serial
                            except Exception as e:
                                logger.warning(f"Query algorithm by ID {alg_id} failed: {e}")
                        
                        alg_config = alg.get('algDefaultConf', {})
                        if isinstance(alg_config, str):
                            try:
                                alg_config = json.loads(alg_config)
                            except json.JSONDecodeError:
                                alg_config = {}
                                
                        algorithm_info = {
                            'code': alg_serial,
                        }
                        if isinstance(alg_config, dict):
                            algorithm_info.update(alg_config)
                        algorithms.append(algorithm_info)

        algorithm_service = 'algorithm_0004'
        publish_path = f'publish_{vid_id}'
        
        # 构建消息数据
        message_data = {
            'vid_id': vid_id,
            'vid_serial': video_detail.get('vid_serial', ''),
            'serial': algorithm_service,
            'action': 'start',
            'stream': 'close', # 关闭流，只进行后台推理
            'algorithms': algorithms,
            'stream_type': video_detail.get('vid_type', 'rtsp'),
            'stream_url': video_detail.get('vid_uri', ''),
            'publish_path': publish_path,
        }
        
        message_json = json.dumps(message_data, ensure_ascii=False)

        # 发送消息到RabbitMQ
        await RabbitMQUtil.publish_message(algorithm_service, message_json)
        logger.info(f'成功推送视频配置到消息队列: {message_json}')

    except Exception as e:
        logger.error(f"处理视频 {vid_serial} 失败: {e}")


async def run(*args, **kwargs):
    """
    定时任务执行异步函数示例
    args: (vid_serial,)
    """
    logger.info(f'{datetime.now()} 异步函数执行了 args={args} kwargs={kwargs}')

    video_ids = []
    if kwargs.get('video_ids'):
        video_ids = kwargs.get('video_ids')
    elif kwargs.get('video_id'): # 兼容前端传参
        video_ids = [kwargs.get('video_id')]
    elif kwargs.get('vid_serial'):
        video_ids = [kwargs.get('vid_serial')]
    elif len(args) > 0:
        video_ids = [args[0]]

    if not video_ids:
        logger.warning("未提供任何视频ID或序列号，任务跳过")
        return

    if not isinstance(video_ids, list):
        video_ids = [video_ids]

    async with AsyncSessionLocal() as db:
        try:
            for vid in video_ids:
                await process_single_video(db, vid)
        except Exception as e:
            logger.error(f"定时任务执行失败: {e}")


async def async_job(*args, **kwargs):
    """
    定时任务执行异步函数示例
    """
    print(args)
    print(kwargs)
    print(f'{datetime.now()}异步函数执行了')
