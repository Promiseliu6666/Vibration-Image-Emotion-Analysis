import json
import asyncio
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import AsyncSessionLocal
from config.get_rabbitmq import RabbitMQUtil
from module_xuzhou.controller.command_controller import device_status_cache
from module_xuzhou.service.video_service import VideoService
from utils.log_util import logger
from module_task.streaming_checker import get_streaming_checker
from module_task.video_ai import process_single_video
from module_admin.service.job_service import JobService
from module_admin.entity.vo.job_vo import JobPageQueryModel
from sqlalchemy import select, desc
from module_admin.entity.do.job_do import SysJobLog

class InferenceMonitor:
    """
    后台推理任务监控器
    监控当前运行的后台推理任务，智能判断任务是否应该在当前时间运行
    """
    
    def __init__(self):
        self.running_tasks: Dict[int, Dict] = {}  # vid_id -> task_info
        self.max_inference_time = timedelta(hours=2)  # 最大推理时间2小时
        self.check_interval = 300  # 检查间隔5分钟
        self.algorithm_service = 'algorithm_0004'
        self.streaming_checker = get_streaming_checker()
        
    async def start_monitoring(self):
        """开始监控任务"""
        logger.info("启动后台推理任务监控器...")
        while True:
            try:
                await self.check_inference_tasks()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"监控任务执行失败: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def check_inference_tasks(self):
        """检查所有推理任务"""
        logger.info("开始检查后台推理任务状态...")
        
        async with AsyncSessionLocal() as session:
            # 获取所有配置的视频任务
            configured_tasks = await self.get_configured_tasks(session)
            
            # 获取当前运行的设备状态
            current_running_devices = self.get_running_devices()
            
            # 智能时间判断：检查每个配置任务是否应该在当前时间运行
            should_run_tasks, should_stop_tasks = await self.analyze_task_schedule(session, configured_tasks, current_running_devices)
            
            # 处理应该运行但未运行的任务
            for vid_id in should_run_tasks:
                if vid_id not in current_running_devices:
                    logger.info(f"任务应该在当前时间运行但未运行，准备启动 - vid_id: {vid_id}")
                    await self.start_inference_task(vid_id)
            
            # 处理不应该运行但正在运行的任务
            for vid_id in should_stop_tasks:
                if vid_id in current_running_devices:
                    logger.info(f"任务不应该在当前时间运行但正在运行，准备停止 - vid_id: {vid_id}")
                    await self.stop_inference_task(vid_id)
            
            # 更新任务状态
            await self.update_task_status(current_running_devices)
            
            # 检查超时任务
            await self.check_timeout_tasks()
            
            logger.info(f"监控检查完成，当前运行任务数: {len(self.running_tasks)}")
    
    async def get_configured_tasks(self, session: AsyncSession) -> List[Dict]:
        """获取所有配置的视频任务"""
        configured_tasks = []
        
        try:
            # 获取所有视频配置
            from module_xuzhou.dao.video_dao import VideoDao
            from module_xuzhou.entity.vo.video_vo import VideoPageQueryModel
            
            query_model = VideoPageQueryModel()
            video_list_result = await VideoDao.get_video_list(session, query_model, is_page=False)
            
            video_rows = []
            if hasattr(video_list_result, 'rows'):
                video_rows = video_list_result.rows
            elif isinstance(video_list_result, list):
                video_rows = video_list_result
            
            for video in video_rows:
                if video.get('vidAlgorithm'):  # 只有配置了算法的才需要监控
                        # skip box-managed cameras — box controls its own lifecycle
                        if video.get('vidBoxSerial'):
                            continue
                        # 获取对应的定时任务配置
                        job_config = await self.get_video_job_config(session, video.get('vidId'))
                        
                        task_info = {
                            'vid_id': video.get('vidId'),
                            'vid_name': video.get('vidName'),
                            'vid_serial': video.get('vidSerial'),
                            'vid_algorithm': video.get('vidAlgorithm'),
                            'vid_uri': video.get('vidUri'),
                            'device_status': video.get('deviceStatus', 'unknown'),
                            'is_running': video.get('isRunning', False),
                            'job_config': job_config  # 添加任务配置信息
                        }
                        configured_tasks.append(task_info)
            
        except Exception as e:
            logger.error(f"获取配置任务失败: {e}")
        
        return configured_tasks
    
    async def get_video_job_config(self, session: AsyncSession, vid_id: int) -> Optional[Dict]:
        """获取视频对应的定时任务配置"""
        try:
            # 查询所有定时任务，查找包含该video_id的任务
            job_query = JobPageQueryModel()
            job_list_result = await JobService.get_job_list_services(session, job_query, is_page=False)
            
            if hasattr(job_list_result, 'rows') and isinstance(job_list_result.rows, list):
                for job in job_list_result.rows:
                    # 检查job_kwargs中是否包含该video_id
                    job_kwargs = job.get('job_kwargs', '')
                    if job_kwargs:
                        try:
                            kwargs = json.loads(job_kwargs)
                            if (kwargs.get('video_id') == str(vid_id) or 
                                kwargs.get('vid_id') == str(vid_id) or
                                kwargs.get('vid_serial') == str(vid_id)):
                                
                                return {
                                    'job_id': job.get('job_id'),
                                    'job_name': job.get('job_name'),
                                    'job_group': job.get('job_group'),
                                    'cron_expression': job.get('cron_expression'),
                                    'status': job.get('status'),  # 0=正常, 1=暂停
                                    'invoke_target': job.get('invoke_target'),
                                    'job_args': job.get('job_args'),
                                    'job_kwargs': kwargs
                                }
                        except json.JSONDecodeError:
                            continue
            
            return None
            
        except Exception as e:
            logger.error(f"获取视频任务配置失败 - vid_id: {vid_id}, error: {e}")
            return None
    
    async def analyze_task_schedule(self, session: AsyncSession, configured_tasks: List[Dict], current_running_devices: List[int]) -> Tuple[List[int], List[int]]:
        """
        智能分析任务调度时间
        
        :param session: 数据库会话
        :param configured_tasks: 配置的任务列表
        :param current_running_devices: 当前运行的设备列表
        :return: (应该运行的任务ID列表, 应该停止的任务ID列表)
        """
        should_run_tasks = []
        should_stop_tasks = []
        
        current_time = datetime.now()
        current_hour = current_time.hour
        current_weekday = current_time.weekday()  # 0-6, 周一到周日
        
        for task in configured_tasks:
            vid_id = task['vid_id']
            
            # 基础时间判断逻辑
            should_run = await self.should_task_run_now(session, task, current_hour, current_weekday)
            
            if should_run:
                should_run_tasks.append(vid_id)
            else:
                should_stop_tasks.append(vid_id)
        
        return should_run_tasks, should_stop_tasks
    
    async def should_task_run_now(self, session: AsyncSession, task: Dict, current_hour: int, current_weekday: int) -> bool:
        """
        判断任务是否应该在当前时间运行
        
        :param session: 数据库会话
        :param task: 任务信息
        :param current_hour: 当前小时
        :param current_weekday: 当前星期几
        :return: 是否应该运行
        """
        # 获取任务配置
        job_config = task.get('job_config')
        # 如果没有任务配置，默认不运行
        if not job_config:
            # logger.info(f"视频 {task['vid_id']} 未配置定时任务，默认不运行")
            return False
        logger.info(f"task: {task}")
        
        # 如果任务被暂停，直接返回False
        if job_config.get('status') == '1':  # 1=暂停
            logger.info(f"任务已被暂停 - vid_id: {task['vid_id']}, job_id: {job_config.get('job_id')}")
            return False
        
        # 从sys_job_log表中获取最近一次执行时间
        job_name = job_config.get('job_name')
        job_group = job_config.get('job_group')
        
        if not job_name or not job_group:
            logger.warning(f"任务配置缺失名称或组名 - vid_id: {task['vid_id']}")
            return False
            
        try:
            stmt = select(SysJobLog.create_time).where(
                SysJobLog.job_name == job_name,
                SysJobLog.job_group == job_group,
                SysJobLog.status == '0'  # 只查找执行成功的日志
            ).order_by(desc(SysJobLog.create_time)).limit(1)
            
            result = await session.execute(stmt)
            last_run_time = result.scalar_one_or_none()
            
            logger.info(f"获取到任务最近执行时间 - job_name: {job_name}, last_run_time: {last_run_time}")
            
            if last_run_time:
                # 获取最大运行时间（优先从任务参数获取，默认为2小时）
                max_run_time = self.max_inference_time
                job_kwargs = job_config.get('job_kwargs', {})
                if isinstance(job_kwargs, dict):
                    duration_minutes = job_kwargs.get('duration')
                    if duration_minutes and str(duration_minutes).replace('.', '', 1).isdigit():
                        max_run_time = timedelta(minutes=float(duration_minutes))

                # 检查是否在运行窗口内（上一次启动时间 + 最大运行时间）
                current_time = datetime.now()
                time_since_start = current_time - last_run_time
                
                logger.info(f'last_run_time: {last_run_time}')
                logger.info(f'current_time: {current_time}')
                logger.info(f'time_since_start: {time_since_start}')
                
                if timedelta(0) <= time_since_start <= max_run_time:
                    logger.info(f"任务在运行窗口内 - vid_id: {task['vid_id']}, 上次启动: {last_run_time}, 已运行: {time_since_start}, 最大运行时长: {max_run_time}")
                    return True
                else:
                    logger.info(f"任务不在运行窗口内 - vid_id: {task['vid_id']}, 上次启动: {last_run_time}, 已运行: {time_since_start}, 最大运行时长: {max_run_time}")
                    return False
            else:
                logger.info(f"未找到任务执行日志 - vid_id: {task['vid_id']}, job_name: {job_name}")
                return False
                
        except Exception as e:
            logger.error(f"查询任务日志失败 - vid_id: {task['vid_id']}, error: {e}")
            return False
    

    def get_running_devices(self) -> List[int]:
        """获取当前正在运行的设备列表"""
        running_devices = []
        
        # 清理过期设备状态
        from module_xuzhou.controller.command_controller import cleanup_old_device_status
        cleanup_old_device_status()
        
        # 获取运行中的设备
        for vid_id, status_info in device_status_cache.items():
            if status_info.get('status') == 'running':
                running_devices.append(vid_id)
        
        return running_devices
    
    async def start_inference_task(self, vid_id: int):
        """启动推理任务"""
        try:
            logger.info(f"正在启动推理任务 - vid_id: {vid_id}")
            
            # 使用现有的视频处理逻辑启动推理
            async with AsyncSessionLocal() as session:
                await process_single_video(session, str(vid_id))
            
            logger.info(f"推理任务启动成功 - vid_id: {vid_id}")
            
        except Exception as e:
            logger.error(f"启动推理任务失败 - vid_id: {vid_id}, error: {e}")
    
    async def update_task_status(self, current_running_devices: List[int]):
        """更新任务状态"""
        current_time = datetime.now()
        
        # 添加新发现的运行任务
        for vid_id in current_running_devices:
            if vid_id not in self.running_tasks:
                # 新任务，添加到监控列表
                task_info = {
                    'vid_id': vid_id,
                    'start_time': current_time,
                    'last_update': current_time,
                    'is_streaming': await self.check_streaming_status(vid_id),
                    'status': 'running'
                }
                self.running_tasks[vid_id] = task_info
                logger.info(f"发现新的后台推理任务 - vid_id: {vid_id}")
            else:
                # 更新已存在任务的状态
                self.running_tasks[vid_id]['last_update'] = current_time
                self.running_tasks[vid_id]['is_streaming'] = await self.check_streaming_status(vid_id)
        
        # 移除已停止的任务
        stopped_tasks = []
        for vid_id in list(self.running_tasks.keys()):
            if vid_id not in current_running_devices:
                self.running_tasks[vid_id]['status'] = 'stopped'
                self.running_tasks[vid_id]['stop_time'] = current_time
                stopped_tasks.append(vid_id)
                logger.info(f"任务已停止 - vid_id: {vid_id}")
        
        # 清理已停止的任务（保留1小时用于日志记录）
        for vid_id in stopped_tasks:
            task_info = self.running_tasks[vid_id]
            if current_time - task_info.get('stop_time', current_time) > timedelta(hours=1):
                del self.running_tasks[vid_id]
                logger.info(f"清理已停止的任务 - vid_id: {vid_id}")
    
    async def check_streaming_status(self, vid_id: int) -> bool:
        """检查设备是否正在推流"""
        try:
            # 从device_status_cache中获取发布路径
            status_info = device_status_cache.get(vid_id, {})
            publish_path = status_info.get('publish_path', f'publish_{vid_id}')
            
            # 使用推流状态检查器检查是否正在推流
            is_streaming = await self.streaming_checker.check_streaming_status(publish_path)
            
            if is_streaming:
                logger.info(f"检测到视频正在推流 - vid_id: {vid_id}, publish_path: {publish_path}")
            
            return is_streaming
            
        except Exception as e:
            logger.error(f"检查推流状态失败 - vid_id: {vid_id}, error: {e}")
            return False
    
    async def check_timeout_tasks(self):
        """检查超时任务并自动关闭"""
        current_time = datetime.now()
        timeout_tasks = []
        
        for vid_id, task_info in self.running_tasks.items():
            if task_info.get('status') != 'running':
                continue
                
            # 检查是否超时
            start_time = task_info.get('start_time', current_time)
            if current_time - start_time > self.max_inference_time:
                # 检查是否正在推流
                if not task_info.get('is_streaming', False):
                    timeout_tasks.append(vid_id)
                    logger.warning(f"发现超时任务 - vid_id: {vid_id}, 运行时间: {current_time - start_time}")
                else:
                    logger.info(f"任务超时但正在推流，跳过自动关闭 - vid_id: {vid_id}")
        
        # 关闭超时任务
        for vid_id in timeout_tasks:
            await self.stop_inference_task(vid_id)
    
    async def stop_inference_task(self, vid_id: int):
        """停止推理任务"""
        try:
            logger.info(f"正在停止推理任务 - vid_id: {vid_id}")
            
            # 构建停止消息
            message_data = {
                'vid_id': vid_id,
                'serial': self.algorithm_service,
                'action': 'stop',
                'reason': 'schedule_auto_stop',
                'stop_time': datetime.now().isoformat()
            }
            
            message_json = json.dumps(message_data, ensure_ascii=False)

            # 发送停止消息到RabbitMQ
            await RabbitMQUtil.publish_message(self.algorithm_service, message_json)
            logger.info(f'成功发送停止消息到消息队列: {message_json}')
            
            # 更新任务状态
            if vid_id in self.running_tasks:
                self.running_tasks[vid_id]['status'] = 'stopped_schedule'
                self.running_tasks[vid_id]['stop_time'] = datetime.now()
                self.running_tasks[vid_id]['stop_reason'] = 'schedule'
            
            logger.info(f"推理任务已自动停止 - vid_id: {vid_id}")
            
        except Exception as e:
            logger.error(f"停止推理任务失败 - vid_id: {vid_id}, error: {e}")
    
    def get_monitor_status(self) -> Dict:
        """获取监控器状态"""
        current_time = datetime.now()
        
        running_count = 0
        timeout_count = 0
        streaming_count = 0
        
        for vid_id, task_info in self.running_tasks.items():
            if task_info.get('status') == 'running':
                running_count += 1
                
                if task_info.get('is_streaming'):
                    streaming_count += 1
                
                # 检查是否接近超时
                start_time = task_info.get('start_time', current_time)
                if current_time - start_time > timedelta(hours=1.5):  # 1.5小时
                    timeout_count += 1
        
        return {
            'total_tasks': len(self.running_tasks),
            'running_tasks': running_count,
            'streaming_tasks': streaming_count,
            'near_timeout_tasks': timeout_count,
            'max_inference_hours': self.max_inference_time.total_seconds() / 3600,
            'check_interval_minutes': self.check_interval / 60
        }
    
    async def get_job_configurations(self) -> List[Dict]:
        """获取所有视频相关的任务配置"""
        job_configs = []
        
        try:
            async with AsyncSessionLocal() as session:
                # 获取所有定时任务
                job_query = JobPageQueryModel()
                job_list_result = await JobService.get_job_list_services(session, job_query, is_page=False)
                
                if hasattr(job_list_result, 'rows') and isinstance(job_list_result.rows, list):
                    for job in job_list_result.rows:
                        # 检查是否是视频相关的任务
                        job_kwargs = job.get('job_kwargs', '')
                        if job_kwargs:
                            try:
                                kwargs = json.loads(job_kwargs)
                                video_id = kwargs.get('video_id') or kwargs.get('vid_id') or kwargs.get('vid_serial')
                                
                                if video_id:
                                    # 获取视频详情
                                    vid_id = None
                                    if kwargs.get('video_id') or kwargs.get('vid_id'):
                                        vid_id = int(video_id)
                                    elif kwargs.get('vid_serial'):
                                        # 根据序列号获取vid_id
                                        video_detail = await VideoService.video_detail_by_serial_services(session, video_id)
                                        if video_detail:
                                            vid_id = video_detail.get('vid_id')
                                    
                                    job_configs.append({
                                        'job_id': job.get('job_id'),
                                        'job_name': job.get('job_name'),
                                        'cron_expression': job.get('cron_expression'),
                                        'status': job.get('status'),
                                        'video_id': video_id,
                                        'vid_id': vid_id,
                                        'invoke_target': job.get('invoke_target'),
                                        'job_args': job.get('job_args'),
                                        'job_kwargs': kwargs,
                                        'remark': job.get('remark', '')
                                    })
                                    
                            except json.JSONDecodeError:
                                continue
                
        except Exception as e:
            logger.error(f"获取任务配置失败: {e}")
        
        return job_configs
    
    async def get_task_details(self, vid_id: Optional[int] = None) -> Dict:
        """获取任务详细信息"""
        if vid_id:
            if vid_id in self.running_tasks:
                return {
                    'task_info': self.running_tasks[vid_id],
                    'device_status': device_status_cache.get(vid_id, {})
                }
            else:
                return {'error': f'未找到vid_id为{vid_id}的任务'}
        else:
            return {
                'all_tasks': self.running_tasks,
                'device_status_cache': device_status_cache
            }


# 全局监控器实例
inference_monitor = InferenceMonitor()


async def start_inference_monitor():
    """启动推理监控器"""
    await inference_monitor.start_monitoring()


def get_inference_monitor():
    """获取推理监控器实例"""
    return inference_monitor