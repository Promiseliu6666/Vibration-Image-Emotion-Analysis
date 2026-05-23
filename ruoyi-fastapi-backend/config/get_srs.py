import requests
import time
import threading
from typing import Dict
from config.env import SRSConfig
from utils.log_util import logger


class SRSUtil:
    """
    SRS相关方法
    """

    @classmethod
    def get_srs_config(cls):
        """
        获取SRS配置信息

        :return: SRS配置对象
        """
        logger.info(
            f'SRS配置信息 - 主机: {SRSConfig.srs_host}, RTMP端口: {SRSConfig.srs_rtmp}, FLV端口: {SRSConfig.srs_flv}, API端口: {SRSConfig.srs_api}'
        )
        return SRSConfig

    @classmethod
    def get_rtmp_url(cls, stream_key: str):
        """
        获取RTMP推流地址

        :param stream_key: 流密钥
        :return: RTMP推流地址
        """
        rtmp_url = f'rtmp://{SRSConfig.srs_host}:{SRSConfig.srs_rtmp}/live/{stream_key}'
        logger.info(f'RTMP推流地址: {rtmp_url}')
        return rtmp_url

    @classmethod
    def get_flv_url(cls, stream_key: str, request=None):
        """
        获取FLV播放地址

        :param stream_key: 流密钥
        :return: FLV播放地址
        """
        flv_url = f'http://{SRSConfig.srs_host}:{SRSConfig.srs_flv}/live/{stream_key}.flv'
        logger.info(f'FLV播放地址: {request.headers}')
        host = request.headers.get('host', request.client.host if request.client else 'localhost')
        port = request.headers.get('port', request.client.port if request.client else '80')
        # 检测请求协议（HTTP或HTTPS）
        scheme = 'https' if request.url.scheme == 'https' else 'http'
        srs_flv_url = f'{scheme}://{host}:{port}/live/{stream_key}.flv'
        logger.info(f'FLV播放地址: {srs_flv_url}')
        return srs_flv_url

    @classmethod
    def get_hls_url(cls, stream_key: str):
        """
        获取HLS播放地址

        :param stream_key: 流密钥
        :return: HLS播放地址
        """
        hls_url = f'http://{SRSConfig.srs_host}:{SRSConfig.srs_flv}/live/{stream_key}/index.m3u8'
        logger.info(f'HLS播放地址: {hls_url}')
        return hls_url

    @classmethod
    def get_api_url(cls, endpoint: str = ''):
        """
        获取SRS API地址

        :param endpoint: API端点
        :return: API地址
        """
        api_url = f'http://{SRSConfig.srs_host}:{SRSConfig.srs_api}'
        if endpoint:
            api_url += f'/{endpoint}'
        return api_url

    @classmethod
    def check_stream_players(cls, stream_key: str) -> int:
        """
        检查指定流的播放器数量

        :param stream_key: 流密钥
        :return: 播放器数量，-1表示查询失败
        """
        try:
            api_url = cls.get_api_url(f'api/v1/streams')
            response = requests.get(api_url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                logger.debug(f'SRS API STREAM: {data}')
                if data.get('code') == 0:
                    # 根据SRS API实际返回的数据结构，streams数组直接位于根级别
                    streams = data.get('streams', [])
                    # 查找指定stream_key的流信息
                    for stream in streams:
                        if stream.get('name').replace('.flv', '') == stream_key:
                            return stream.get('clients', 0)
                    # 如果没有找到对应的流，返回0
                    return -1
                else:
                    logger.warning(f'SRS API返回错误: {data.get("msg")}')
                    return -2
            else:
                logger.warning(f'SRS API请求失败，状态码: {response.status_code}')
                return -3

        except requests.exceptions.RequestException as e:
            logger.warning(f'检查SRS流播放器失败: {str(e)}')
            return -4
        except Exception as e:
            logger.error(f'解析SRS API响应失败: {str(e)}')
            return -5


class SRSMonitor:
    """
    SRS流监控类，用于监控用户取流情况并控制FFmpeg进程
    """

    _active_monitors: Dict[str, dict] = {}  # stream_key -> {'active': bool, 'process': subprocess.Popen}

    @classmethod
    def start_stream_monitor(cls, stream_key: str, ffmpeg_process, timeout: int = 30):
        """
        启动流监控，监控用户取流情况并在超时时关闭FFmpeg进程

        :param stream_key: 流密钥
        :param ffmpeg_process: FFmpeg进程对象
        :param timeout: 超时时间（秒）
        """
        if stream_key in cls._active_monitors:
            logger.warning(f'流 {stream_key} 已经在监控中')
            return

        cls._active_monitors[stream_key] = {'active': True, 'process': ffmpeg_process}

        monitor_thread = threading.Thread(target=cls._monitor_stream_status, args=(stream_key, timeout), daemon=True)
        monitor_thread.start()

        logger.info(f'启动流状态监控: {stream_key}, 超时时间: {timeout}秒')

    @classmethod
    def stop_stream_monitor(cls, stream_key: str):
        """
        停止流监控

        :param stream_key: 流密钥
        """
        if stream_key in cls._active_monitors:
            cls._active_monitors[stream_key]['active'] = False
            logger.info(f'停止流状态监控: {stream_key}')

    @classmethod
    def _monitor_stream_status(cls, stream_key: str, timeout: int):
        """
        监控流状态，在超时时关闭FFmpeg进程

        :param stream_key: 流密钥
        :param timeout: 超时时间（秒）
        """
        last_activity_time = time.time()

        while cls._active_monitors.get(stream_key, {}).get('active', False):
            try:
                # 检查当前播放器数量
                player_count = SRSUtil.check_stream_players(stream_key)

                if player_count > 1:
                    # 有用户观看，更新最后活动时间
                    last_activity_time = time.time()
                    logger.debug(f'流 {stream_key} 有 {player_count} 个观看者')
                elif player_count <= 1:
                    # 没有用户观看，检查是否超时
                    inactive_time = time.time() - last_activity_time
                    if inactive_time >= timeout:
                        logger.info(f'流 {stream_key} 超过 {timeout} 秒有 {player_count} 个观看者，关闭FFmpeg进程')

                        # 获取FFmpeg进程并关闭
                        monitor_info = cls._active_monitors.get(stream_key)
                        if monitor_info:
                            ffmpeg_process = monitor_info.get('process')
                            if ffmpeg_process and ffmpeg_process.poll() is None:
                                # 优雅终止FFmpeg进程
                                ffmpeg_process.terminate()
                                try:
                                    ffmpeg_process.wait(timeout=5)
                                    logger.info(f'FFmpeg进程已正常终止: {stream_key}')
                                except:
                                    # 如果正常终止失败，强制杀死进程
                                    ffmpeg_process.kill()
                                    logger.warning(f'FFmpeg进程被强制终止: {stream_key}')

                        # 停止监控
                        cls.stop_stream_monitor(stream_key)
                        break
                    else:
                        logger.debug(f'流 {stream_key} 有 {player_count} 个观看者，已空闲 {inactive_time:.1f} 秒')

                # 等待5秒再次检查
                time.sleep(5)

            except Exception as e:
                logger.error(f'监控流 {stream_key} 时发生错误: {str(e)}')
                time.sleep(5)

        # 清理资源
        if stream_key in cls._active_monitors:
            del cls._active_monitors[stream_key]

        logger.info(f'流状态监控结束: {stream_key}')
