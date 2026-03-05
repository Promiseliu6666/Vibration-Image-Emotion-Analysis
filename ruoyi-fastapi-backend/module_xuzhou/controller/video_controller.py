import time
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.dao.video_dao import VideoDao
from module_xuzhou.entity.vo.video_vo import VideoModel, VideoPageQueryModel, DeleteVideoModel
from module_xuzhou.service.video_service import VideoService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil


# 推流请求模型
class StreamRequest(BaseModel):
    vid_type: str = Field(description='视频类型')
    vid_uri: str = Field(description='视频源地址')
    flag: str = Field(default=None, description='流标识符，可选')


# 推流响应模型
class StreamResponse(BaseModel):
    flv_url: str = Field(description='FLV播放地址')
    rtmp_url: str = Field(description='RTMP推流地址')
    stream_key: str = Field(description='流密钥')


videoController = APIRouter(prefix='/xuzhou/video', dependencies=[Depends(unified_auth)])


@videoController.get('/list', response_model=PageResponseModel, summary='获取视频列表')
@integration_log(
    title='获取视频列表',
    system_name='徐州视频管理系统',
    business_type=BusinessType.OTHER,
)
async def get_video_list(
    request: Request,
    video_page_query: VideoPageQueryModel = Depends(VideoPageQueryModel.as_query),
    query_db: AsyncSession = Depends(get_db),
):
    """
    获取视频列表
    """
    video_list_result = await VideoService.get_video_list_services(query_db, video_page_query, is_page=True)
    return ResponseUtil.success(model_content=video_list_result)


@videoController.post('/', summary='添加视频')
@integration_log(
    title='添加视频',
    system_name='徐州视频管理系统',
    business_type=BusinessType.INSERT,
)
async def add_video(request: Request, video: VideoModel, query_db: AsyncSession = Depends(get_db)):
    """
    添加视频
    """
    # 设置更新时间
    video.vid_update_time = datetime.now()
    # 调用Service层添加视频
    result = await VideoService.add_video_services(query_db, video)
    await query_db.commit()
    return ResponseUtil.success(msg='添加成功')


@videoController.get('/{vid_id}', response_model=VideoModel, summary='获取视频详细信息')
@integration_log(
    title='获取视频详细信息',
    system_name='徐州视频管理系统',
    business_type=BusinessType.OTHER,
)
async def get_video_detail(request: Request, vid_id: int, query_db: AsyncSession = Depends(get_db)):
    """
    获取视频详细信息
    """
    video_detail_result = await VideoService.video_detail_services(query_db, vid_id)
    return ResponseUtil.success(data=video_detail_result)


@videoController.put('/', summary='编辑视频')
@integration_log(
    title='编辑视频',
    system_name='徐州视频管理系统',
    business_type=BusinessType.UPDATE,
)
async def edit_video(request: Request, video: VideoModel, query_db: AsyncSession = Depends(get_db)):
    """
    编辑视频
    """
    # 设置更新时间
    video.vid_update_time = datetime.now()
    # 调用Service层编辑视频
    result = await VideoService.edit_video_services(query_db, video)
    if result:
        await query_db.commit()
        return ResponseUtil.success(msg='编辑成功')
    else:
        await query_db.rollback()
        return ResponseUtil.error(msg='编辑失败，视频不存在')


@videoController.delete('/', summary='删除视频')
@integration_log(
    title='删除视频',
    system_name='徐州视频管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_video(request: Request, delete_video: DeleteVideoModel, query_db: AsyncSession = Depends(get_db)):
    """
    删除视频
    """
    vid_id = int(delete_video.vid_ids)
    result = await VideoService.delete_video_services(query_db, vid_id)
    if result:
        await query_db.commit()
        return ResponseUtil.success(msg='删除成功')
    else:
        await query_db.rollback()
        return ResponseUtil.error(msg='删除失败，视频不存在')


@videoController.post('/stream', summary='启动视频推流', response_model=StreamResponse)
@integration_log(
    title='启动视频推流',
    system_name='徐州视频管理系统',
    business_type=BusinessType.OTHER,
)
async def start_video_stream(request: Request, stream_request: StreamRequest):
    """
    启动视频推流到SRS服务器

    :param stream_request: 推流请求参数，包含视频类型和视频源地址
    :return: 推流启动结果和播放地址
    """
    try:
        # 使用传入的flag或生成新的flag
        flag = stream_request.flag or f'preview_{int(time.time())}'

        # 规范化真实推流类型
        real_vid_type = stream_request.vid_type.lower()

        if real_vid_type == 'hik':
            # 海康监控点编号，需先换取RTSP预览地址
            try:
                from config.get_hik import get_hik_rtsp_url

                camera_index_code = stream_request.vid_uri
                rtsp_url = await get_hik_rtsp_url(camera_index_code)
                vid_uri = rtsp_url
                real_vid_type = 'rtmp'
                logger.info(f'海康监控点编号转换成功: {camera_index_code} -> {rtsp_url}')
            except Exception as e:
                logger.error(f'海康RTSP地址获取失败: {str(e)}')
                return ResponseUtil.error(msg=f'海康RTSP地址获取失败: {str(e)}')
        elif real_vid_type in ['rtsp', 'rtmp', 'hls', 'https']:
            # 网络流直接使用视频源地址
            vid_uri = stream_request.vid_uri
        else:
            # 未知视频类型，返回错误
            return ResponseUtil.error(msg=f'未知视频类型: {stream_request.vid_type}')

        # 调用VideoDao的推流方法
        process = VideoDao.start_ffmpeg_stream(real_vid_type, vid_uri, flag)

        if process:
            # 获取FLV播放地址
            from config.get_srs import SRSUtil

            flv_url = SRSUtil.get_flv_url(flag, request)
            rtmp_url = SRSUtil.get_rtmp_url(flag)

            logger.info(f'视频推流启动成功，类型: {real_vid_type}, 地址: {vid_uri}')

            return ResponseUtil.success(
                data={'flv_url': flv_url, 'rtmp_url': rtmp_url, 'stream_key': flag}, msg='视频推流启动成功'
            )
        else:
            logger.error(f'视频推流启动失败，类型: {real_vid_type}, 地址: {vid_uri}')
            return ResponseUtil.error(msg='视频推流启动失败')

    except Exception as e:
        logger.error(f'视频推流异常: {str(e)}')
        return ResponseUtil.error(msg=f'视频推流异常: {str(e)}')
