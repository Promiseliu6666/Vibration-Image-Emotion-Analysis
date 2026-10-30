"""Storage housekeeping never blocks the camera-analysis consumer."""
import asyncio
import logging
from app.analysis.analysis_storage import cleanup_expired_frames

logger = logging.getLogger(__name__)


async def run(first_delay=30, interval=3600):
    await asyncio.sleep(first_delay)
    while True:
        try:
            await asyncio.to_thread(cleanup_expired_frames)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('照片保留策略清理未完成，将在下一轮重试')
        await asyncio.sleep(interval)
