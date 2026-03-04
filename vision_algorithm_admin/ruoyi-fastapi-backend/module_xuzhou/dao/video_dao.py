import subprocess

from sqlalchemy import delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from config.get_srs import SRSUtil
from module_xuzhou.entity.do.video_do import XuzhouVideo
from module_xuzhou.entity.vo.video_vo import VideoPageQueryModel
from utils.log_util import logger
from utils.page_util import PageUtil


class VideoDao:
    """
    视频管理模块数据库操作层
    """

    @classmethod
    async def get_video_detail_by_id(cls, db: AsyncSession, vid_id: int):
        """
        根据视频id获取视频详细信息

        :param db: orm对象
        :param vid_id: 视频id
        :return: 视频信息对象
        """
        video_info = (await db.execute(select(XuzhouVideo).where(XuzhouVideo.vid_id == vid_id))).scalars().first()

        return video_info

    @classmethod
    async def get_video_detail_by_serial(cls, db: AsyncSession, vid_serial: str):
        """
        根据视频serial获取视频详细信息

        :param db: orm对象
        :param vid_serial: 视频序列号
        :return: 视频信息对象
        """
        video_info = (
            (await db.execute(select(XuzhouVideo).where(XuzhouVideo.vid_serial == vid_serial))).scalars().first()
        )

        return video_info

    @classmethod
    async def get_video_list(cls, db: AsyncSession, query_object: VideoPageQueryModel, is_page: bool = False):
        """
        根据查询参数获取视频列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 视频列表信息对象
        """
        query = (
            select(XuzhouVideo)
            .where(
                XuzhouVideo.vid_name.like(f'%{query_object.vid_name}%') if query_object.vid_name else True,
                XuzhouVideo.vid_serial.like(f'%{query_object.vid_serial}%') if query_object.vid_serial else True,
                XuzhouVideo.vid_type.like(f'%{query_object.vid_type}%') if query_object.vid_type else True,
                XuzhouVideo.vid_scene_name.like(f'%{query_object.vid_scene_name}%')
                if query_object.vid_scene_name
                else True,
            )
            .order_by(XuzhouVideo.vid_id)
            .distinct()
        )
        video_list = await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

        return video_list

    @classmethod
    async def add_video_dao(cls, db: AsyncSession, video):
        """
        新增视频数据库操作

        :param db: orm对象
        :param video: 视频对象
        :return:
        """
        db_video = XuzhouVideo(**video.model_dump())
        db.add(db_video)
        await db.flush()

        return db_video

    @classmethod
    async def edit_video_dao(cls, db: AsyncSession, video: dict):
        """
        编辑视频数据库操作

        :param db: orm对象
        :param video: 需要更新的视频字典
        :return:
        """
        await db.execute(update(XuzhouVideo), [video])

    @classmethod
    async def delete_video_dao(cls, db: AsyncSession, vid_id: int):
        """
        删除视频数据库操作

        :param db: orm对象
        :param vid_id: 视频id
        :return:
        """
        await db.execute(delete(XuzhouVideo).where(XuzhouVideo.vid_id == vid_id))

    @classmethod
    async def get_video_count(cls, db: AsyncSession):
        """
        获取视频总数量

        :param db: orm对象
        :return: 视频数量
        """
        result = await db.execute(select(func.count(XuzhouVideo.vid_id)))
        return result.scalar()

    @classmethod
    async def get_video_all(cls, db: AsyncSession):
        """
        获取所有视频信息

        :param db: orm对象
        :return: 视频列表
        """
        result = await db.execute(
            select(XuzhouVideo.vid_id, XuzhouVideo.vid_scene_name, XuzhouVideo.vid_algorithm_name)
        )
        return result.all()

    @classmethod
    def start_ffmpeg_stream(cls, vid_type: str, vid_uri: str, flag: str):
        """
        启动FFmpeg推流进程

        :param vid_type: 视频类型
        :param vid_uri: 视频源地址
        :return: 进程对象
        """
        try:
            # SRS服务器地址
            srs_rtmp_url = SRSUtil.get_rtmp_url(flag)

            # 根据视频类型构建不同的FFmpeg命令
            if vid_type.lower() in ['rtsp', 'rtmp', 'http', 'https']:
                # 网络流直接转发到SRS
                cmd = [
                    'ffmpeg',
                    '-i',
                    vid_uri,
                    '-c:v',
                    'copy',
                    # 'libx264' if platform.system() == 'Linux' else 'libopenh264',
                    '-preset',
                    'ultrafast',
                    '-tune',
                    'zerolatency',
                    # '-c:a',
                    # 'aac',
                    '-an',
                    '-strict',
                    'experimental',
                    '-f',
                    'flv',
                    srs_rtmp_url,
                ]
            else:
                # 本地文件推流
                cmd = ['ffmpeg', '-re', '-i', vid_uri, '-c', 'copy', '-f', 'flv', srs_rtmp_url]

            logger.info(f'启动FFmpeg推流: {" ".join(cmd)}')

            # 执行FFmpeg命令，使用子进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE,
                # universal_newlines=True
            )

            logger.info(f'FFmpeg推流进程已启动，视频类型: {vid_type}, 视频源: {vid_uri}, 流密钥: {flag}')

            # 启动独立的流状态监控，传递FFmpeg进程
            from config.get_srs import SRSMonitor

            SRSMonitor.start_stream_monitor(flag, process, timeout=30)

            return process

        except Exception as e:
            logger.error(f'启动FFmpeg推流进程失败: {str(e)}')
            return None
