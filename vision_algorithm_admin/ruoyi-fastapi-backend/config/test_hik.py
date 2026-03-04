#!/usr/bin/env python3
"""
海康综合安防平台 Artemis 接口测试脚本（无命令行参数版）

功能：调用“查询监控点列表 v2”分页接口，输出分页设备数据摘要。

使用：直接在脚本内默认配置区填写平台地址、appKey、appSecret、接口路径与查询条件后运行。
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, List, Tuple
from urllib.parse import urlencode

import requests


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
        params = params or {}
        query = urlencode(params, doseq=True)
        path_with_query = path if not query else f'{path}?{query}'

        body_bytes = None
        if json_body is not None:
            body_bytes = json.dumps(json_body, separators=(',', ':')).encode('utf-8')

        headers = self._build_headers(method, path_with_query, body_bytes)
        url = f'{self.host}{path_with_query}'
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=body_bytes if body_bytes is not None else None,
            timeout=self.timeout,
            verify=self.verify,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            # 保留原始响应便于排错
            return {'non_json_body': resp.text, 'status_code': resp.status_code}


def query_monitor_points_page(
    client: ArtemisClient,
    path: str,
    page_no: int,
    page_size: int,
    method: str = 'POST',
    extra_body: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """查询单页监控点数据（支持 v2 接口的分页语义；默认 POST）"""
    method_up = method.upper()
    if method_up == 'POST':
        # 按接口规则使用 POST + JSON，计算 Content-MD5 参与签名
        body = {'pageNo': page_no, 'pageSize': page_size}
        if extra_body:
            body.update(extra_body)
        return client.request(
            method='POST',
            path=path,
            json_body=body,
        )
    else:
        # 某些平台也支持 GET Query 方式（该接口规范为 POST，仅作兼容）
        return client.request(
            method='GET',
            path=path,
            params={'pageNo': page_no, 'pageSize': page_size},
        )


def extract_page_info(resp: Dict[str, Any]) -> Tuple[int, int, int, List[Dict[str, Any]]]:
    """兼容不同响应结构，提取分页四要素：pageNo、pageSize、total、list"""
    data = resp.get('data') or resp
    page_no = int(data.get('pageNo') or resp.get('pageNo') or 1)
    page_size = int(data.get('pageSize') or resp.get('pageSize') or 0)
    total = int(data.get('total') or resp.get('total') or 0)
    items = data.get('list') or resp.get('list') or []
    return page_no, page_size, total, items  # type: ignore


def print_items_summary(items: List[Dict[str, Any]], limit: int = 10) -> None:
    print(f'返回设备数：{len(items)}（展示前 {min(limit, len(items))} 条）')
    for i, it in enumerate(items[:limit], start=1):
        # 兼容字段名差异，尽量输出常见摘要字段
        idx = it.get('indexCode') or it.get('cameraIndexCode') or it.get('id')
        name = it.get('name') or it.get('cameraName') or it.get('deviceName')
        status = it.get('status') or it.get('online')
        region = it.get('regionName') or it.get('orgName') or it.get('department')
        print(f'[{i}] indexCode={idx} name={name} status={status} region={region}')


def main() -> None:
    # 默认配置（按需修改）
    HOST = 'https://172.17.185.12:443'  # 平台地址（含协议与端口）
    APP_KEY = '20335062'
    APP_SECRET = 'HJcBnE7qbBFlzrmE8CAk'
    PATH = '/artemis/api/resource/v2/camera/search'  # 接口路径
    METHOD = 'POST'  # 推荐 POST，符合接口规则
    PAGE_NO = 1
    PAGE_SIZE = 10
    FETCH_ALL = False  # True 时遍历到 total 覆盖
    TIMEOUT = 15
    INSECURE = False  # 自签证书可设为 True（忽略SSL校验）

    # 过滤与排序（POST JSON）
    NAME: str | None = None
    REGION_INDEX_CODES: List[str] = []  # 例如：["regionCode1", "regionCode2"]
    IS_SUB_REGION: bool = False
    AUTH_CODES: List[str] = []
    ORDER_BY: str | None = None
    ORDER_TYPE: str | None = None  # "asc" 或 "desc"
    EXPRESSIONS: List[
        Dict[str, Any]
    ] = []  # 例如：[{"key":"updateTime","operator":5,"values":["2025-10-08","2025-10-09"]}]

    client = ArtemisClient(
        host=HOST,
        app_key=APP_KEY,
        app_secret=APP_SECRET,
        timeout=TIMEOUT,
        verify=not INSECURE,
    )

    # 构建附加查询体（POST专用）
    extra_body: Dict[str, Any] = {}
    if NAME:
        extra_body['name'] = NAME
    if REGION_INDEX_CODES:
        extra_body['regionIndexCodes'] = REGION_INDEX_CODES
    if IS_SUB_REGION:
        extra_body['isSubRegion'] = True
    if AUTH_CODES:
        extra_body['authCodes'] = AUTH_CODES
    if ORDER_BY:
        extra_body['orderBy'] = ORDER_BY
    if ORDER_TYPE:
        extra_body['orderType'] = ORDER_TYPE
    if EXPRESSIONS:
        extra_body['expressions'] = EXPRESSIONS

    if not FETCH_ALL:
        resp = query_monitor_points_page(
            client,
            PATH,
            page_no=PAGE_NO,
            page_size=PAGE_SIZE,
            method=METHOD,
            extra_body=extra_body,
        )
        code = resp.get('code')
        msg = resp.get('msg') or resp.get('message')
        print(f'code={code} msg={msg}')
        page_no, page_size, total, items = extract_page_info(resp)
        print(f'pageNo={page_no} pageSize={page_size} total={total}')
        print_items_summary(items)
        return

    # 拉取所有页
    all_items: List[Dict[str, Any]] = []
    current = PAGE_NO
    total = None
    while True:
        resp = query_monitor_points_page(
            client,
            PATH,
            page_no=current,
            page_size=PAGE_SIZE,
            method=METHOD,
            extra_body=extra_body,
        )
        page_no, page_size, resp_total, items = extract_page_info(resp)
        if total is None:
            total = resp_total
        all_items.extend(items)
        print(f'已拉取 pageNo={page_no}, 本页 {len(items)} 条，总计 {len(all_items)}/{total}')
        if len(all_items) >= (total or 0) or len(items) == 0:
            break
        current += 1

    print('—— 全量数据摘要 ——')
    print_items_summary(all_items, limit=20)


if __name__ == '__main__':
    main()
