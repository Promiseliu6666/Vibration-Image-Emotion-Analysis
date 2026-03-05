import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from config.database import AsyncSessionLocal
from module_xuzhou.dao.alarm_dao import AlarmDao
from module_xuzhou.entity.vo.alarm_vo import AlarmPageQueryModel

async def check_alarms():
    async with AsyncSessionLocal() as db:
        query = AlarmPageQueryModel(page_num=1, page_size=10)
        result = await AlarmDao.get_alarm_list(db, query, is_page=True)
        if result and result.rows:
            for row in result.rows:
                print(f'alarm_id: {row.get("alarm_id")}, vid_id: {row.get("vid_id")}, vid_name: {row.get("vid_name")}, vid_serial: {row.get("vid_serial")}, alarm_code: {row.get("alarm_code")}, alarm_time: {row.get("alarm_time")}, alarm_content: {row.get("alarm_content")[:100] if row.get("alarm_content") else "None"}')
        else:
            print('没有找到预警数据')

if __name__ == "__main__":
    asyncio.run(check_alarms())