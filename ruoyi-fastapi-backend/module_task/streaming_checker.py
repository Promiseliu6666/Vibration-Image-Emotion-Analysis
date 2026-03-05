import json
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import AsyncSessionLocal
from config.get_rabbitmq import RabbitMQUtil
from module_xuzhou.controller.command_controller import device_status_cache
from module_xuzhou.service.video_service import VideoService
from utils.log_util import logger
import aio_pika
from config.env import SRSConfig


class StreamingStatusChecker:
    """
    推流状态检查器
    检查SRS服务器上的推流状态
    """
    
    def __init__(self):
        self.srs_api_base = f"http://{SRSConfig.srs_host}:{SRSConfig.srs_flv}"
        self.timeout = 5  # HTTP请求超时时间
        
    async def check_streaming_status(self, publish_path: str) -> bool:
        """
        检查指定发布路径是否正在推流
        
        :param publish_path: 发布路径
        :return: 是否正在推流
        """
        try:
            # 检查SRS服务器的流状态
            streams = await self.get_active_streams()
            
            if not streams:
                return False
            
            # 检查是否有匹配的流
            for stream in streams:
                stream_name = stream.get('name', '')
                if publish_path in stream_name or stream_name in publish_path:
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"检查推流状态失败 - publish_path: {publish_path}, error: {e}")
            return False
    
    async def get_active_streams(self) -> List[Dict]:
        """
        获取SRS服务器上的活跃流列表
        
        :return: 活跃流列表
        """
        try:
            # 尝试获取SRS的API数据
            api_urls = [
                f"{self.srs_api_base}/api/v1/streams",
                f"{self.srs_api_base}/api/v1/summaries",
            ]
            
            for api_url in api_urls:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                        async with session.get(api_url) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                # 解析不同格式的响应
                                if 'streams' in data:
                                    return data['streams']
                                elif 'data' in data and 'streams' in data['data']:
                                    return data['data']['streams']
                                else:
                                    # 尝试其他可能的格式
                                    return self.parse_srs_streams(data)
                                    
                except Exception as e:
                    logger.warning(f"SRS API调用失败 - URL: {api_url}, error: {e}")
                    continue
                    
            # 如果API调用失败，尝试通过HTTP获取简单的流信息
            return await self.get_streams_from_http()
            
        except Exception as e:
            logger.error(f"获取活跃流列表失败: {e}")
            return []
    
    def parse_srs_streams(self, data: Dict) -> List[Dict]:
        """
        解析SRS响应数据中的流信息
        
        :param data: SRS响应数据
        :return: 流列表
        """
        streams = []
        
        try:
            # 尝试不同的数据结构
            if isinstance(data, list):
                streams = data
            elif isinstance(data, dict):
                # 查找包含流信息的字段
                for key, value in data.items():
                    if key.lower() in ['streams', 'stream'] and isinstance(value, list):
                        streams = value
                        break
                    elif key.lower() in ['publishers', 'publisher'] and isinstance(value, list):
                        streams = value
                        break
                        
            # 标准化流数据格式
            normalized_streams = []
            for stream in streams:
                if isinstance(stream, dict):
                    normalized_stream = {
                        'name': stream.get('name', stream.get('stream', '')),
                        'url': stream.get('url', ''),
                        'active': stream.get('active', True),
                        'clients': stream.get('clients', 0),
                        'publish_time': stream.get('publish_time', stream.get('create_time', '')),
                        'kbps': stream.get('kbps', 0),
                        'fps': stream.get('fps', 0),
                    }
                    normalized_streams.append(normalized_stream)
                    
            return normalized_streams
            
        except Exception as e:
            logger.error(f"解析SRS流数据失败: {e}")
            return []
    
    async def get_streams_from_http(self) -> List[Dict]:
        """
        通过HTTP获取流信息（备用方法）
        
        :return: 流列表
        """
        try:
            # 尝试获取FLV播放列表页面
            flv_url = f"http://{SRSConfig.srs_flv_url}/live/"
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(flv_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        # 解析HTML内容获取流列表
                        return self.parse_flv_list_html(content)
                        
        except Exception as e:
            logger.warning(f"HTTP获取流信息失败: {e}")
            
        return []
    
    def parse_flv_list_html(self, html: str) -> List[Dict]:
        """
        解析FLV列表HTML内容
        
        :param html: HTML内容
        :return: 流列表
        """
        streams = []
        
        try:
            # 简单的HTML解析，查找.flv链接
            import re
            flv_pattern = r'href=["\']([^"\']+\.flv)["\']'
            flv_matches = re.findall(flv_pattern, html, re.IGNORECASE)
            
            for flv_file in flv_matches:
                stream_name = flv_file.replace('.flv', '')
                streams.append({
                    'name': stream_name,
                    'url': f"http://{SRSConfig.srs_flv_url}/live/{flv_file}",
                    'active': True,
                    'clients': 0,  # 无法从HTML获取客户端数量
                    'publish_time': '',
                    'kbps': 0,
                    'fps': 0,
                })
                
        except Exception as e:
            logger.error(f"解析FLV列表HTML失败: {e}")
            
        return streams
    
    async def get_streaming_videos(self) -> List[int]:
        """
        获取正在推流的视频ID列表
        
        :return: 正在推流的视频ID列表
        """
        streaming_videos = []
        
        try:
            # 获取所有活跃流
            streams = await self.get_active_streams()
            
            # 从device_status_cache中获取视频映射信息
            for vid_id, status_info in device_status_cache.items():
                publish_path = status_info.get('publish_path', '')
                if not publish_path:
                    # 尝试构建发布路径
                    publish_path = f"publish_{vid_id}"
                
                # 检查该发布路径是否在活跃流中
                if await self.check_streaming_status(publish_path):
                    streaming_videos.append(vid_id)
                    
        except Exception as e:
            logger.error(f"获取推流视频列表失败: {e}")
            
        return streaming_videos


# 全局推流状态检查器实例
streaming_checker = StreamingStatusChecker()


def get_streaming_checker():
    """获取推流状态检查器实例"""
    return streaming_checker