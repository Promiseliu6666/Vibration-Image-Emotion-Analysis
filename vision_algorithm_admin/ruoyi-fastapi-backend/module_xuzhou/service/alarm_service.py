import json
import httpx
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import AsyncSessionLocal
from module_admin.dao.callback_dao import CallbackDao
from module_admin.entity.vo.callback_vo import CallbackPageQueryModel
from module_xuzhou.dao.alarm_dao import AlarmDao
from module_xuzhou.dao.video_dao import VideoDao
from module_xuzhou.entity.vo.alarm_vo import AlarmModel
from utils.log_util import logger


class AlarmService:
    """
    预警消息服务层
    """

    @classmethod
    async def get_alarm_list(cls, query_db: AsyncSession = None, page_num: int = 1, page_size: int = 10, vid_id: int = None, alarm_code: str = None):
        """
        获取预警消息列表
        :param query_db: orm对象
        :param page_num: 页码
        :param page_size: 每页数量
        :param vid_id: 视频ID
        :param alarm_code: 预警编码
        :return: 分页结果
        """
        if query_db:
            alarms, total = await AlarmDao.get_alarm_list(query_db, page_num, page_size, vid_id, alarm_code)
            return {
                "rows": alarms,
                "total": total,
                "page_num": page_num,
                "page_size": page_size
            }
        
        async with AsyncSessionLocal() as db:
            alarms, total = await AlarmDao.get_alarm_list(db, page_num, page_size, vid_id, alarm_code)
            return {
                "rows": alarms,
                "total": total,
                "page_num": page_num,
                "page_size": page_size
            }

    @classmethod
    async def save_alarm_message(cls, message: dict):
        """
        保存预警消息到数据库，并推送到回调接口
        :param message: 消息内容
        """
        try:
            # 简化的处理开始日志
            data_count = len(message.get('data', []))
            if data_count > 0:
                logger.info(f"处理预警消息 - 数据条数: {data_count}")
            
            async with AsyncSessionLocal() as db:
                # 解析消息内容
                # 消息结构示例: {'key': 'publish_4', 'data': [{'code': '0004', 'image': 'base64...', 'time': '2023-01-01 12:00:00'}]}
                key = message.get('key', '')
                data_list = message.get('data', [])
                
                # 从 key 中提取 vid_id (假设 key 格式为 publish_{vid_id})
                vid_id = None
                if key.startswith('publish_'):
                    try:
                        vid_id = int(key.split('_')[1])
                    except (IndexError, ValueError):
                        logger.warning(f"无法从 key 解析 vid_id: {key}")
                else:
                    logger.warning(f"key格式不符合预期: {key}, 无法解析vid_id")

                if vid_id is None:
                    logger.error(f"严重错误: 无法获取有效的vid_id，跳过此消息处理 - key: {key}")
                    return  # 直接返回，不处理后续逻辑

                # 根据 vid_id 获取视频信息
                video_info = None
                if vid_id:
                    video_info = await VideoDao.get_video_detail_by_id(db, vid_id)
                    if not video_info:
                        logger.warning(f"未找到视频信息 - vid_id: {vid_id}，视为无效数据，跳过处理")
                        return
                
                # 获取启用的回调地址列表
                active_callbacks = []
                try:
                    query_object = CallbackPageQueryModel(status='0', page_num=1, page_size=1000)
                    callback_result = await CallbackDao.get_callback_list(db, query_object, is_page=False)
                    if callback_result:
                        active_callbacks = callback_result
                except Exception:
                    pass  # 静默处理回调地址获取失败

                processed_count = 0
                
                for i, item in enumerate(data_list):
                    alarm_code = item.get('code')
                    if not alarm_code:
                        continue  # 静默跳过无效数据项
                    
                    # 提取其他字段
                    alarm_image_raw = item.get('image', '')
                    # 尝试从多个字段获取时间
                    alarm_time_str = item.get('timeStr') or item.get('time') or item.get('alarmTime') or ''
                    
                    # 将图片数据存储为列表格式
                    alarm_image_list = []
                    if alarm_image_raw:
                        alarm_image_list = [alarm_image_raw]  # 存储为base64列表
                    
                    # 简化的日志信息
                    if not alarm_image_raw:
                        logger.warning(f"警告: alarm_image为空，继续处理")
                    
                    processed_count += 1
                    
                    alarm_time = datetime.now()
                    # 尝试解析时间
                    if alarm_time_str:
                        try:
                            # 尝试解析 ISO 格式
                            alarm_time = datetime.fromisoformat(str(alarm_time_str))
                        except ValueError:
                            try:
                                # 尝试解析常见格式 YYYY-MM-DD HH:MM:SS
                                alarm_time = datetime.strptime(str(alarm_time_str), "%Y-%m-%d %H:%M:%S")
                            except Exception:
                                logger.warning(f"时间格式解析失败: {alarm_time_str}，使用当前时间")
                                pass
                        except Exception:
                            pass
                    
                    # 查重：如果在数据库中已存在相同 vid_id, alarm_code, alarm_time 的记录，则跳过
                    if await AlarmDao.check_alarm_exist(db, vid_id, alarm_code, alarm_time):
                        # logger.info(f"重复预警，跳过 - vid_id: {vid_id}, code: {alarm_code}")
                        continue
                    
                    # 构造预警数据对象（推送用，包含完整数据）
                    alarm_data = {
                        "vid_id": vid_id,
                        "vid_name": video_info.vid_name if video_info else None,
                        "vid_serial": video_info.vid_serial if video_info else None,
                        "alarm_code": alarm_code,
                        "alarm_time": alarm_time.isoformat(),
                        "alarm_content": item,  # 推送用完整数据
                        "alarm_images": alarm_image_list  # 图片列表
                    }
                    
                    # 推送消息并记录结果
                    push_results = []
                    if active_callbacks:
                        push_results = await cls.push_to_callbacks(active_callbacks, alarm_data)
                        # 统计推送结果
                        success_count = sum(1 for r in push_results if r.get('status') == 'success')
                        if success_count > 0:
                            logger.info(f"推送完成 - 成功: {success_count}, 失败: {len(push_results) - success_count}")
                    # 移除"未找到回调地址"的日志，保持安静

                    # 创建alarm_content时移除图片字段
                    item_content = item.copy()
                    if 'image' in item_content:
                        del item_content['image']  # 移除图片字段，避免数据过大
                    
                    # 打印接收到的消息内容（不包含图片）
                    logger.info(f"接收到的预警消息内容: {json.dumps(item_content, ensure_ascii=False)}")
                    
                    # 使用驼峰格式的字段名创建AlarmModel (确保兼容性，优先使用驼峰)
                    alarm_model = AlarmModel(
                        vidId=vid_id,
                        vidName=video_info.vid_name if video_info else None,
                        vidSerial=video_info.vid_serial if video_info else None,
                        alarmCode=alarm_code,
                        alarmTime=alarm_time,
                        alarmImage=json.dumps(alarm_image_list),  # 存储为JSON列表
                        alarmContent=json.dumps(item_content, ensure_ascii=False),
                        pushResult=json.dumps(push_results, ensure_ascii=False),
                        createTime=datetime.now()
                    )
                    
                    # 调试日志 - 检查AlarmModel的实际数据
                    logger.info(f"AlarmModel创建后数据检查: vid_id={alarm_model.vid_id}, alarm_code={alarm_model.alarm_code}, alarm_image长度={len(alarm_model.alarm_image) if alarm_model.alarm_image else 0}")

                    await AlarmDao.add_alarm_dao(db, alarm_model)
                    logger.info(f"保存预警成功 - alarm_id: {alarm_model.alarm_id}, vid_id: {vid_id}, alarm_code: {alarm_code}")
                    
                    # 简化的推送结果记录
                    if push_results:
                        success_count = sum(1 for r in push_results if r.get('status') == 'success')
                        logger.info(f"推送结果 - 成功: {success_count}, 失败: {len(push_results) - success_count}")
                
                await db.commit()
                if processed_count > 0:
                    logger.info(f"保存完成 - 处理: {processed_count}/{len(data_list)} 条预警")
                
        except Exception as e:
            logger.error(f"保存预警消息失败: {type(e).__name__}: {str(e)}")

    @classmethod
    async def push_to_callbacks(cls, callbacks, data):
        """
        推送消息到所有回调地址
        :param callbacks: 回调地址列表
        :param data: 推送的数据
        :return: 推送结果列表
        """
        results = []
        async with httpx.AsyncClient() as client:
            tasks = []
            for callback in callbacks:
                url = callback.get('url')
                if not url:
                    continue
                tasks.append(cls.send_request(client, url, data))
            
            if tasks:
                results = await asyncio.gather(*tasks)
        
        return results

    @classmethod
    async def send_request(cls, client, url, data):
        """
        发送单个请求
        :param client: httpx client
        :param url: 目标URL
        :param data: 数据
        :return: 结果字典
        """
        result = {
            "url": url,
            "status": "failed",
            "response": "",
            "time": datetime.now().isoformat()
        }
        try:
            response = await client.post(url, json=data, timeout=5)
            result["status"] = "success" if 200 <= response.status_code < 300 else "failed"
            result["http_code"] = response.status_code
            try:
                result["response"] = response.text
            except:
                result["response"] = "Read response failed"
        except Exception as e:
            result["error"] = str(e)
            # 简化推送错误日志
        
        return result
