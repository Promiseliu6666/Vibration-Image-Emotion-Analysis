import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.video_dao import VideoDao
from module_xuzhou.entity.vo.video_vo import VideoModel, VideoPageQueryModel
from utils.common_util import CamelCaseUtil


class VideoService:
    """
    视频管理模块服务层
    """

    @classmethod
    async def get_video_list_services(
        cls, query_db: AsyncSession, query_object: VideoPageQueryModel, is_page: bool = False
    ):
        """
        获取视频列表信息service

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 视频列表信息对象
        """
        video_list_result = await VideoDao.get_video_list(query_db, query_object, is_page)

        # 修改个别字段 - 对 vidAlgorithm 和 vidAlgorithmName 进行 JSON 序列化
        if hasattr(video_list_result, 'rows') and isinstance(video_list_result.rows, list):
            # 导入设备状态缓存（需要在controller层传入或全局访问）
            from module_xuzhou.controller.command_controller import device_status_cache, box_registry
            from datetime import datetime as dt

            # 处理分页结果
            for item in video_list_result.rows:
                if 'vidAlgorithm' in item and item['vidAlgorithm'] is not None:
                    item['vidAlgorithm'] = json.loads(item['vidAlgorithm'])
                if 'vidAlgorithmName' in item and item['vidAlgorithmName'] is not None:
                    item['vidAlgorithmName'] = json.loads(item['vidAlgorithmName'])

                # 添加设备运行状态检查 - 从设备状态缓存中获取
                try:
                    vid_id = item.get('vidId')
                    vid_box_serial = item.get('vidBoxSerial') or item.get('vid_box_serial')

                    # 检查盒子是否在线
                    box_offline = False
                    if vid_box_serial:
                        box_info = box_registry.get(str(vid_box_serial))
                        if box_info:
                            try:
                                last_seen = dt.fromisoformat(box_info['last_seen']).timestamp()
                                box_offline = dt.now().timestamp() - last_seen > 60
                            except Exception:
                                box_offline = True
                        else:
                            box_offline = True  # box never registered

                    if vid_id and vid_id in device_status_cache:
                        device_status = device_status_cache[vid_id]
                        if box_offline:
                            item['deviceStatus'] = 'offline'
                            item['deviceErrorMessage'] = f'盒子 {vid_box_serial} 已离线'
                        else:
                            item['deviceStatus'] = device_status.get('status', 'unknown')
                            item['deviceErrorMessage'] = device_status.get('error_message', '')
                        item['deviceUpdateTime'] = device_status.get('update_time')
                        item['isRunning'] = device_status.get('status') == 'running' and not box_offline
                    elif item.get('vidType') == 'local' and not vid_box_serial:
                        # 纯本地摄像头(未绑定盒子) — 默认运行中
                        item['deviceStatus'] = 'running'
                        item['deviceUpdateTime'] = None
                        item['isRunning'] = True
                        item['deviceErrorMessage'] = ''
                    elif item.get('vidType') == 'local' and vid_box_serial:
                        # 盒子上的本地摄像头 — 等盒子回报状态
                        item['deviceStatus'] = 'stopped'
                        item['deviceUpdateTime'] = None
                        item['isRunning'] = False
                        item['deviceErrorMessage'] = ''
                    elif box_offline:
                        item['deviceStatus'] = 'offline'
                        item['deviceUpdateTime'] = None
                        item['isRunning'] = False
                        item['deviceErrorMessage'] = f'盒子 {vid_box_serial} 已离线'
                    else:
                        item['deviceStatus'] = 'unknown'
                        item['deviceUpdateTime'] = None
                        item['isRunning'] = False
                        item['deviceErrorMessage'] = ''
                except Exception as e:
                    # 如果获取设备状态失败，设置默认值
                    item['deviceStatus'] = 'unknown'
                    item['deviceUpdateTime'] = None
                    item['isRunning'] = False
                    item['deviceErrorMessage'] = ''
                    import logging
                    logging.warning(f"获取视频设备状态失败 - vid_id: {item.get('vidId')}, 错误: {e}")
            
            # 计算全局设备状态统计
            # 获取视频总数（不受筛选条件影响）
            total_count = await VideoDao.get_video_count(query_db)
            running_count = sum(1 for item in video_list_result.rows if item.get('isRunning'))
            stopped_count = max(0, total_count - running_count)
            
            setattr(video_list_result, 'running_count', running_count)
            setattr(video_list_result, 'stopped_count', stopped_count)

        return video_list_result

    @classmethod
    async def video_detail_services(cls, query_db: AsyncSession, vid_id: int):
        """
        获取视频详细信息service

        :param query_db: orm对象
        :param vid_id: 视频id
        :return: 视频id对应的信息
        """
        video = await VideoDao.get_video_detail_by_id(query_db, vid_id=vid_id)
        if video:
            # 转换视频基本信息
            video_dict = CamelCaseUtil.transform_result(video)

            # 处理算法字段的JSON解析
            if 'vidAlgorithm' in video_dict and video_dict['vidAlgorithm']:
                try:
                    # 尝试解析JSON格式的算法数据
                    parsed_algorithm = json.loads(video_dict['vidAlgorithm'])
                    video_dict['vidAlgorithm'] = parsed_algorithm
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，保持原始字符串格式（兼容旧数据）
                    pass

            if 'vidAlgorithmName' in video_dict and video_dict['vidAlgorithmName']:
                try:
                    # 尝试解析JSON格式的算法名称数据
                    parsed_algorithm_name = json.loads(video_dict['vidAlgorithmName'])
                    video_dict['vidAlgorithmName'] = parsed_algorithm_name
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，保持原始字符串格式（兼容旧数据）
                    pass

            return video_dict
        else:
            return {}

    @classmethod
    async def video_detail_by_serial_services(cls, query_db: AsyncSession, vid_serial: str):
        """
        根据视频serial获取视频详细信息service

        :param query_db: orm对象
        :param vid_serial: 视频serial
        :return: 视频serial对应的信息
        """
        video = await VideoDao.get_video_detail_by_serial(query_db, vid_serial=vid_serial)
        if video:
            # 转换视频基本信息
            video_dict = CamelCaseUtil.transform_result(video)

            # 处理算法字段的JSON解析
            if 'vidAlgorithm' in video_dict and video_dict['vidAlgorithm']:
                try:
                    # 尝试解析JSON格式的算法数据
                    parsed_algorithm = json.loads(video_dict['vidAlgorithm'])
                    video_dict['vidAlgorithm'] = parsed_algorithm
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，保持原始字符串格式（兼容旧数据）
                    pass

            if 'vidAlgorithmName' in video_dict and video_dict['vidAlgorithmName']:
                try:
                    # 尝试解析JSON格式的算法名称数据
                    parsed_algorithm_name = json.loads(video_dict['vidAlgorithmName'])
                    video_dict['vidAlgorithmName'] = parsed_algorithm_name
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，保持原始字符串格式（兼容旧数据）
                    pass

            return video_dict
        else:
            return {}

    @classmethod
    async def add_video_services(cls, query_db: AsyncSession, video: VideoModel):
        """
        新增视频信息service

        :param query_db: orm对象
        :param video: 视频对象
        :return: 新增结果
        """
        result = await VideoDao.add_video_dao(query_db, video)
        return result

    @classmethod
    async def edit_video_services(cls, query_db: AsyncSession, video: VideoModel):
        """
        编辑视频信息service

        :param query_db: orm对象
        :param video: 视频对象
        :return: 编辑结果
        """
        # 获取旧的视频信息
        video_info = await VideoDao.get_video_detail_by_id(query_db, vid_id=video.vid_id)
        if video_info:
            # 删除旧文件
            if video_info.vid_type == 'file' and video_info.vid_uri:
                # 检查是否需要删除旧文件的两种情况：
                # 1. 视频类型从'file'改为其他类型
                # 2. 都是'file'类型但URI发生了变化
                should_delete_old_file = (
                    video.vid_type != 'file'  # 类型变更
                    or (video.vid_type == 'file' and video.vid_uri != video_info.vid_uri)  # URI变更
                )

                if should_delete_old_file:
                    video_file = Path(video_info.vid_uri)
                    if video_file.exists():
                        video_file.unlink(missing_ok=True)

            # 更新数据
            video_data = video.model_dump(exclude_unset=True)
            for key, value in video_data.items():
                setattr(video_info, key, value)
            await query_db.commit()
            return True
        else:
            return False

    @classmethod
    async def delete_video_services(cls, query_db: AsyncSession, vid_id: int):
        """
        删除视频信息service

        :param query_db: orm对象
        :param vid_id: 视频id
        :return: 删除结果
        """
        video_info = await VideoDao.get_video_detail_by_id(query_db, vid_id=vid_id)
        if video_info:
            if video_info.vid_type == 'file' and (video_file := Path(video_info.vid_uri)).exists():
                video_file.unlink(missing_ok=True)
            await VideoDao.delete_video_dao(query_db, vid_id=vid_id)
            await query_db.commit()
            return True
        else:
            return False
