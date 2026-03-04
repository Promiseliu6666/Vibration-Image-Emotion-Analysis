from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_task.inference_monitor import get_inference_monitor
from utils.response_util import ResponseUtil
from utils.log_util import logger

monitorController = APIRouter(prefix='/xuzhou/monitor', dependencies=[Depends(unified_auth)])


@monitorController.get('/inference/status', summary='获取推理监控状态')
@integration_log(
    title='获取推理监控状态',
    system_name='徐州推理监控系统',
    business_type=BusinessType.OTHER,
)
async def get_inference_monitor_status(request: Request):
    """
    获取后台推理监控器的当前状态
    
    :return: 监控器状态信息
    """
    try:
        monitor = get_inference_monitor()
        status = monitor.get_monitor_status()
        
        return ResponseUtil.success(
            data=status,
            msg='获取监控状态成功'
        )
        
    except Exception as e:
        logger.error(f"获取推理监控状态失败: {str(e)}")
        return ResponseUtil.error(msg=f"获取推理监控状态失败: {str(e)}")


@monitorController.get('/inference/tasks', summary='获取推理任务详情')
@integration_log(
    title='获取推理任务详情',
    system_name='徐州推理监控系统',
    business_type=BusinessType.OTHER,
)
async def get_inference_tasks(
    request: Request,
    vid_id: Optional[int] = Query(None, description='视频ID，不指定则返回所有任务')
):
    """
    获取推理任务的详细信息
    
    :param vid_id: 视频ID（可选）
    :return: 任务详情
    """
    try:
        monitor = get_inference_monitor()
        task_details = await monitor.get_task_details(vid_id)
        
        return ResponseUtil.success(
            data=task_details,
            msg='获取任务详情成功'
        )
        
    except Exception as e:
        logger.error(f"获取推理任务详情失败: {str(e)}")
        return ResponseUtil.error(msg=f"获取推理任务详情失败: {str(e)}")


@monitorController.post('/inference/stop', summary='手动停止推理任务')
@integration_log(
    title='手动停止推理任务',
    system_name='徐州推理监控系统',
    business_type=BusinessType.OTHER,
)
async def stop_inference_task(
    request: Request,
    vid_id: int = Query(..., description='要停止的视频ID')
):
    """
    手动停止指定的推理任务
    
    :param vid_id: 视频ID
    :return: 停止结果
    """
    try:
        monitor = get_inference_monitor()
        await monitor.stop_inference_task(vid_id)
        
        return ResponseUtil.success(
            data={'vid_id': vid_id, 'action': 'stop'},
            msg='推理任务停止成功'
        )
        
    except Exception as e:
        logger.error(f"停止推理任务失败 - vid_id: {vid_id}, error: {str(e)}")
        return ResponseUtil.error(msg=f"停止推理任务失败: {str(e)}")


@monitorController.get('/streaming/status', summary='获取推流状态')
@integration_log(
    title='获取推流状态',
    system_name='徐州推理监控系统',
    business_type=BusinessType.OTHER,
)
async def get_streaming_status(
    request: Request,
    publish_path: Optional[str] = Query(None, description='发布路径')
):
    """
    获取推流状态信息
    
    :param publish_path: 发布路径（可选）
    :return: 推流状态
    """
    try:
        from module_task.streaming_checker import get_streaming_checker
        
        checker = get_streaming_checker()
        
        if publish_path:
            # 检查指定发布路径的推流状态
            is_streaming = await checker.check_streaming_status(publish_path)
            active_streams = []
        else:
            # 获取所有活跃流
            active_streams = await checker.get_active_streams()
            is_streaming = len(active_streams) > 0
        
        return ResponseUtil.success(
            data={
                'is_streaming': is_streaming,
                'publish_path': publish_path,
                'active_streams': active_streams,
                'stream_count': len(active_streams) if active_streams else 0
            },
            msg='获取推流状态成功'
        )
        
    except Exception as e:
        logger.error(f"获取推流状态失败: {str(e)}")
        return ResponseUtil.error(msg=f"获取推流状态失败: {str(e)}")


@monitorController.get('/streaming/videos', summary='获取正在推流的视频列表')
@integration_log(
    title='获取正在推流的视频列表',
    system_name='徐州推理监控系统',
    business_type=BusinessType.OTHER,
)
async def get_streaming_videos(request: Request):
    """
    获取当前正在推流的视频ID列表
    
    :return: 正在推流的视频列表
    """
    try:
        from module_task.streaming_checker import get_streaming_checker
        
        checker = get_streaming_checker()
        streaming_videos = await checker.get_streaming_videos()
        
        return ResponseUtil.success(
            data={
                'streaming_videos': streaming_videos,
                'count': len(streaming_videos)
            },
            msg='获取推流视频列表成功'
        )
        
    except Exception as e:
        logger.error(f"获取推流视频列表失败: {str(e)}")
        return ResponseUtil.error(msg=f"获取推流视频列表失败: {str(e)}")


@monitorController.post('/config/update', summary='更新监控配置')
@integration_log(
    title='更新监控配置',
    system_name='徐州推理监控系统',
    business_type=BusinessType.OTHER,
)
async def update_monitor_config(
    request: Request,
    max_inference_hours: Optional[float] = Query(None, description='最大推理时间（小时）'),
    check_interval_minutes: Optional[float] = Query(None, description='检查间隔（分钟）')
):
    """
    更新监控器配置参数
    
    :param max_inference_hours: 最大推理时间（小时）
    :param check_interval_minutes: 检查间隔（分钟）
    :return: 更新结果
    """
    try:
        monitor = get_inference_monitor()
        
        if max_inference_hours is not None:
            monitor.max_inference_time = timedelta(hours=max_inference_hours)
            logger.info(f"更新最大推理时间为: {max_inference_hours}小时")
        
        if check_interval_minutes is not None:
            monitor.check_interval = check_interval_minutes * 60  # 转换为秒
            logger.info(f"更新检查间隔为: {check_interval_minutes}分钟")
        
        return ResponseUtil.success(
            data={
                'max_inference_hours': monitor.max_inference_time.total_seconds() / 3600,
                'check_interval_minutes': monitor.check_interval / 60
            },
            msg='监控配置更新成功'
        )
        
    except Exception as e:
        logger.error(f"更新监控配置失败: {str(e)}")
        return ResponseUtil.error(msg=f"更新监控配置失败: {str(e)}")


@monitorController.get('/jobs/configurations', summary='获取视频任务配置')
@integration_log(
    title='获取视频任务配置',
    system_name='徐州推理监控系统',
    business_type=BusinessType.OTHER,
)
async def get_job_configurations(request: Request):
    """
    获取所有视频相关的任务配置信息
    
    :return: 视频任务配置列表
    """
    try:
        monitor = get_inference_monitor()
        job_configs = await monitor.get_job_configurations()
        
        return ResponseUtil.success(
            data={
                'job_configurations': job_configs,
                'count': len(job_configs)
            },
            msg='获取视频任务配置成功'
        )
        
    except Exception as e:
        logger.error(f"获取视频任务配置失败: {str(e)}")
        return ResponseUtil.error(msg=f"获取视频任务配置失败: {str(e)}")