import asyncio

from config.database import async_engine, AsyncSessionLocal, Base
from utils.log_util import logger


async def get_db():
    """
    每一个请求处理完毕后会关闭当前连接，不同的请求使用不同的连接

    :return:
    """
    current_db = AsyncSessionLocal()
    try:
        yield current_db
    finally:
        # 使用 asyncio.shield 确保即使请求被取消（如客户端断开连接），
        # 也能正确关闭数据库连接并归还到连接池，
        # 避免 SQLAlchemy 报 "non-checked-in connection" 警告
        await asyncio.shield(current_db.close())


async def init_create_table():
    """
    应用启动时初始化数据库连接

    :return:
    """
    logger.info('初始化数据库连接...')
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info('数据库连接成功')
