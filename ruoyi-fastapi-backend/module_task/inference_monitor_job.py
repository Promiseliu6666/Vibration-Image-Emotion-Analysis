import asyncio
from datetime import datetime
from utils.log_util import logger
from module_task.inference_monitor import start_inference_monitor


async def run_inference_monitor(*args, **kwargs):
    """
    推理监控器定时任务
    启动后台推理任务监控器，持续监控推理任务状态
    
    参数:
        args: 位置参数
        kwargs: 关键字参数
    """
    logger.info(f"启动推理监控器定时任务 - {datetime.now()}")
    
    try:
        # 启动推理监控器（这是一个长时间运行的任务）
        await start_inference_monitor()
        
    except Exception as e:
        logger.error(f"推理监控器任务执行失败: {e}")
        raise


def run_inference_monitor_sync(*args, **kwargs):
    """
    同步版本的推理监控器定时任务
    """
    logger.info(f"启动推理监控器同步任务 - {datetime.now()}")
    
    try:
        # 使用asyncio运行异步函数
        asyncio.run(run_inference_monitor(*args, **kwargs))
        
    except Exception as e:
        logger.error(f"推理监控器同步任务执行失败: {e}")
        raise