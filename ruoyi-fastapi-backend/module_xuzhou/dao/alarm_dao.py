from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from module_xuzhou.entity.do.alarm_do import XuzhouAlarm
from module_xuzhou.entity.vo.alarm_vo import AlarmModel
from utils.log_util import logger


class AlarmDao:
    """
    预警消息数据库操作层
    """

    @classmethod
    async def check_alarm_exist(cls, db: AsyncSession, vid_id: int, alarm_code: str, alarm_time: datetime):
        """
        检查是否存在重复的预警消息
        :param db: orm对象
        :param vid_id: 视频ID
        :param alarm_code: 预警编码
        :param alarm_time: 预警时间
        :return: 是否存在
        """
        # 查重逻辑优化：使用时间范围（前后1秒）避免精度问题
        start_time = alarm_time - timedelta(seconds=1)
        end_time = alarm_time + timedelta(seconds=1)
        
        query = select(XuzhouAlarm).where(
            XuzhouAlarm.vid_id == vid_id,
            XuzhouAlarm.alarm_code == alarm_code,
            XuzhouAlarm.alarm_time >= start_time,
            XuzhouAlarm.alarm_time <= end_time
        )
        result = await db.execute(query)
        return result.scalars().first() is not None

    @classmethod
    async def get_alarm_list(cls, db: AsyncSession, page_num: int = 1, page_size: int = 10, vid_id: int = None, alarm_code: str = None):
        """
        获取预警消息列表
        :param db: orm对象
        :param page_num: 页码
        :param page_size: 每页数量
        :param vid_id: 视频ID筛选
        :param alarm_code: 预警编码筛选
        :return: 预警消息列表, 总数
        """
        query = select(XuzhouAlarm)
        
        if vid_id:
            query = query.where(XuzhouAlarm.vid_id == vid_id)
        if alarm_code:
            query = query.where(XuzhouAlarm.alarm_code == alarm_code)
            
        # 计算总数
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # 分页查询，按时间倒序
        query = query.order_by(XuzhouAlarm.alarm_time.desc()).offset((page_num - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        return result.scalars().all(), total

    @classmethod
    async def add_alarm_dao(cls, db: AsyncSession, alarm: AlarmModel):
        """
        新增预警消息
        :param db: orm对象
        :param alarm: 预警消息对象
        :return: 新增的预警消息
        """
        # 检查关键数据是否完整
        if not alarm.vid_id or not alarm.alarm_code:
            logger.error(f"AlarmDao.add_alarm_dao - 严重错误: 尝试写入空数据! vid_id={alarm.vid_id}, alarm_code={alarm.alarm_code}")
            logger.error(f"完整对象数据: {alarm.model_dump()}")
            return None

        # 简化的数据库操作日志
        logger.info(f"保存预警 - vid_id: {alarm.vid_id}, alarm_code: {alarm.alarm_code}")
        
        # 手动创建数据库实体，确保字段正确映射
        db_alarm = XuzhouAlarm(
            vid_id=alarm.vid_id,
            vid_name=alarm.vid_name,
            vid_serial=alarm.vid_serial,
            alarm_code=alarm.alarm_code,
            alarm_time=alarm.alarm_time,
            alarm_image=alarm.alarm_image,
            alarm_content=alarm.alarm_content,
            push_result=alarm.push_result,
            create_time=alarm.create_time or datetime.now()
        )
        
        db.add(db_alarm)
        await db.flush()
        return db_alarm
