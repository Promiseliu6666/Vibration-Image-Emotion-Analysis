#!/usr/bin/env python3
"""
海康综合安防平台 Artemis 接口封装类

功能：
1. 获取监控点编号列表
2. 获取预览RTSP视频流地址
3. 统一的签名鉴权和错误处理

使用：
from config.get_hik import HikVisionClient, HikConfig

client = HikVisionClient()
# 获取监控点列表
cameras = await client.get_camera_list()
# 获取RTSP流地址
rtsp_url = await client.get_rtsp_stream(camera_index_code)
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from pydantic_settings import BaseSettings

from exceptions.exception import ServiceException
from utils.log_util import logger


class HikSettings(BaseSettings):
    """
    海康平台配置
    """

    hik_host: str = 'https://172.17.185.12:443'
    hik_app_key: str = '20335062'
    hik_app_secret: str = 'HJcBnE7qbBFlzrmE8CAk'
    hik_timeout: int = 15
    hik_verify_ssl: bool = False  # 自签证书设为False


class ArtemisClient:
    """Artemis 网关客户端（x-ca-* 签名鉴权）"""

    def __init__(
        self,
        host: str,
        app_key: str,
        app_secret: str,
        timeout: int = 15,
        verify: bool = True,
    ) -> None:
        self.host = host.rstrip('/')
        self.app_key = app_key
        self.app_secret = app_secret
        self.timeout = timeout
        self.verify = verify

    def _build_headers(
        self,
        method: str,
        path_with_query: str,
        body_bytes: bytes | None,
    ) -> Dict[str, str]:
        """构建请求头，包含签名信息"""
        accept = 'application/json'
        content_type = 'application/json'

        content_md5 = ''
        if body_bytes:
            md5 = hashlib.md5()
            md5.update(body_bytes)
            content_md5 = base64.b64encode(md5.digest()).decode('utf-8')

        headers: Dict[str, str] = {
            'Accept': accept,
            'Content-Type': content_type,
            'x-ca-key': self.app_key,
            'x-ca-nonce': str(uuid.uuid4()),
            'x-ca-timestamp': str(int(time.time() * 1000)),
        }

        # 指定参与签名的头
        signed_header_keys = ['x-ca-key', 'x-ca-nonce', 'x-ca-timestamp']
        headers['x-ca-signature-headers'] = ','.join(signed_header_keys)

        # 构造 canonical headers（按键名排序）
        canonical = '\n'.join([f'{k}:{headers[k]}' for k in sorted(signed_header_keys)])

        # 构造签名字符串
        string_to_sign = '\n'.join(
            [
                method.upper(),
                accept,
                content_md5,
                content_type,
                canonical,
                path_with_query,
            ]
        )

        signature = base64.b64encode(
            hmac.new(
                self.app_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256,
            ).digest()
        ).decode('utf-8')

        headers['x-ca-signature'] = signature
        if content_md5:
            headers['Content-MD5'] = content_md5
        return headers

    def request(
        self,
        method: str,
        path: str,
        params: Dict[str, Any] | None = None,
        json_body: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """发送HTTP请求"""
        params = params or {}
        query = urlencode(params, doseq=True)
        path_with_query = path if not query else f'{path}?{query}'

        body_bytes = None
        if json_body is not None:
            body_bytes = json.dumps(json_body, separators=(',', ':')).encode('utf-8')

        headers = self._build_headers(method, path_with_query, body_bytes)
        url = f'{self.host}{path_with_query}'

        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=body_bytes if body_bytes is not None else None,
                timeout=self.timeout,
                verify=self.verify,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f'海康接口请求失败: {e}')
            raise ServiceException(message=f'海康接口请求失败: {str(e)}')
        except Exception as e:
            logger.error(f'海康接口响应解析失败: {e}')
            return {'non_json_body': resp.text, 'status_code': resp.status_code}


class HikVisionClient:
    """海康综合安防平台接口封装类"""

    def __init__(self, config: Optional[HikSettings] = None):
        """
        初始化海康客户端

        :param config: 海康配置对象，如果为None则使用默认配置
        """
        self.config = config or HikConfig
        self.client = ArtemisClient(
            host=self.config.hik_host,
            app_key=self.config.hik_app_key,
            app_secret=self.config.hik_app_secret,
            timeout=self.config.hik_timeout,
            verify=self.config.hik_verify_ssl,
        )
        logger.info(f'海康客户端初始化完成，平台地址: {self.config.hik_host}')

    def _extract_page_info(self, resp: Dict[str, Any]) -> Tuple[int, int, int, List[Dict[str, Any]]]:
        """兼容不同响应结构，提取分页四要素：pageNo、pageSize、total、list"""
        data = resp.get('data') or resp
        page_no = int(data.get('pageNo') or resp.get('pageNo') or 1)
        page_size = int(data.get('pageSize') or resp.get('pageSize') or 0)
        total = int(data.get('total') or resp.get('total') or 0)
        items = data.get('list') or resp.get('list') or []
        return page_no, page_size, total, items

    async def get_camera_list(
        self,
        page_no: int = 1,
        page_size: int = 100,
        name: Optional[str] = None,
        region_codes: Optional[List[str]] = None,
        fetch_all: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取监控点列表

        :param page_no: 页码，从1开始
        :param page_size: 每页大小
        :param name: 监控点名称过滤
        :param region_codes: 区域编码列表过滤
        :param fetch_all: 是否获取所有数据
        :return: 监控点列表
        """
        path = '/artemis/api/resource/v2/camera/search'

        # 构建查询体
        extra_body: Dict[str, Any] = {}
        if name:
            extra_body['name'] = name
        if region_codes:
            extra_body['regionIndexCodes'] = region_codes

        try:
            if not fetch_all:
                # 获取单页数据
                body = {'pageNo': page_no, 'pageSize': page_size}
                body.update(extra_body)

                resp = self.client.request('POST', path, json_body=body)
                code = resp.get('code')
                if code != '0':
                    msg = resp.get('msg') or resp.get('message', '未知错误')
                    logger.error(f'获取监控点列表失败: code={code}, msg={msg}')
                    raise ServiceException(message=f'获取监控点列表失败: {msg}')

                _, _, _, items = self._extract_page_info(resp)
                logger.info(f'获取监控点列表成功，返回 {len(items)} 条数据')
                return items
            else:
                # 获取所有数据
                all_items: List[Dict[str, Any]] = []
                current = page_no
                total = None

                while True:
                    body = {'pageNo': current, 'pageSize': page_size}
                    body.update(extra_body)

                    resp = self.client.request('POST', path, json_body=body)
                    code = resp.get('code')
                    if code != '0':
                        msg = resp.get('msg') or resp.get('message', '未知错误')
                        logger.error(f'获取监控点列表失败: code={code}, msg={msg}')
                        break

                    page_no_resp, page_size_resp, resp_total, items = self._extract_page_info(resp)
                    if total is None:
                        total = resp_total

                    all_items.extend(items)
                    logger.info(f'已获取第 {page_no_resp} 页，本页 {len(items)} 条，总计 {len(all_items)}/{total}')

                    if len(all_items) >= (total or 0) or len(items) == 0:
                        break
                    current += 1

                logger.info(f'获取全量监控点列表成功，共 {len(all_items)} 条数据')
                return all_items

        except Exception as e:
            logger.error(f'获取监控点列表异常: {e}')
            raise ServiceException(message=f'获取监控点列表失败: {str(e)}')

    async def get_camera_index_codes(
        self, name: Optional[str] = None, region_codes: Optional[List[str]] = None
    ) -> List[str]:
        """
        获取监控点编号列表

        :param name: 监控点名称过滤
        :param region_codes: 区域编码列表过滤
        :return: 监控点编号列表
        """
        try:
            cameras = await self.get_camera_list(fetch_all=True, name=name, region_codes=region_codes)

            index_codes = []
            for camera in cameras:
                index_code = camera.get('indexCode') or camera.get('cameraIndexCode')
                if index_code:
                    index_codes.append(index_code)

            logger.info(f'提取监控点编号成功，共 {len(index_codes)} 个')
            return index_codes

        except Exception as e:
            logger.error(f'获取监控点编号列表异常: {e}')
            raise ServiceException(message=f'获取监控点编号列表失败: {str(e)}')

    async def get_rtsp_stream(
        self, camera_index_code: str, stream_type: int = 0, protocol: str = 'rtmp', expand: str = 'streamform=rtp'
    ) -> str:
        """
        获取监控点预览RTSP流地址

        :param camera_index_code: 监控点编号
        :param stream_type: 码流类型，0-主码流，1-子码流
        :param protocol: 协议类型，默认rtsp
        :param expand: 扩展参数
        :return: RTSP流地址
        """
        path = '/artemis/api/video/v1/cameras/previewURLs'

        body = {'cameraIndexCode': camera_index_code, 'streamType': stream_type, 'protocol': protocol, 'expand': expand}

        try:
            resp = self.client.request('POST', path, json_body=body)
            code = resp.get('code')
            if code != '0':
                msg = resp.get('msg') or resp.get('message', '未知错误')
                logger.error(f'获取RTSP流地址失败: code={code}, msg={msg}')
                raise ServiceException(message=f'获取RTSP流地址失败: {msg}')

            data = resp.get('data')
            if not data:
                raise ServiceException(message='获取RTSP流地址失败: 响应数据为空')

            rtsp_url = data.get('url')
            if not rtsp_url:
                raise ServiceException(message='获取RTSP流地址失败: URL为空')

            logger.info(f'获取RTSP流地址成功: {camera_index_code} -> {rtsp_url}')
            return rtsp_url

        except Exception as e:
            logger.error(f'获取RTSP流地址异常: {e}')
            raise ServiceException(message=f'获取RTSP流地址失败: {str(e)}')

    async def get_camera_detail(self, camera_index_code: str) -> Dict[str, Any]:
        """
        获取监控点详细信息

        :param camera_index_code: 监控点编号
        :return: 监控点详细信息
        """
        path = '/artemis/api/resource/v1/cameras'

        params = {'indexCodes': camera_index_code}

        try:
            resp = self.client.request('GET', path, params=params)
            code = resp.get('code')
            if code != '0':
                msg = resp.get('msg') or resp.get('message', '未知错误')
                logger.error(f'获取监控点详情失败: code={code}, msg={msg}')
                raise ServiceException(message=f'获取监控点详情失败: {msg}')

            data = resp.get('data')
            if not data or not data.get('list'):
                raise ServiceException(message='获取监控点详情失败: 未找到对应监控点')

            camera_info = data['list'][0]
            logger.info(f'获取监控点详情成功: {camera_index_code}')
            return camera_info

        except Exception as e:
            logger.error(f'获取监控点详情异常: {e}')
            raise ServiceException(message=f'获取监控点详情失败: {str(e)}')

    async def test_connection(self) -> bool:
        """
        测试海康平台连接

        :return: 连接是否成功
        """
        try:
            # 尝试获取少量监控点数据来测试连接
            cameras = await self.get_camera_list(page_no=1, page_size=1)
            logger.info('海康平台连接测试成功')
            return True
        except Exception as e:
            logger.error(f'海康平台连接测试失败: {e}')
            return False


@lru_cache()
def get_hik_config():
    """获取海康配置"""
    return HikSettings()


# 全局配置实例
HikConfig = get_hik_config()


# 全局客户端实例（单例模式）
_hik_client: Optional[HikVisionClient] = None


def get_hik_client() -> HikVisionClient:
    """
    获取海康客户端实例（单例模式）

    :return: 海康客户端实例
    """
    global _hik_client
    if _hik_client is None:
        _hik_client = HikVisionClient()
    return _hik_client


# 便捷方法
async def get_hik_camera_list(**kwargs) -> List[Dict[str, Any]]:
    """获取监控点列表的便捷方法"""
    client = get_hik_client()
    return await client.get_camera_list(**kwargs)


async def get_hik_camera_codes(**kwargs) -> List[str]:
    """获取监控点编号列表的便捷方法"""
    client = get_hik_client()
    return await client.get_camera_index_codes(**kwargs)


async def get_hik_rtsp_url(camera_index_code: str, **kwargs) -> str:
    """获取RTSP流地址的便捷方法"""
    client = get_hik_client()
    return await client.get_rtsp_stream(camera_index_code, **kwargs)