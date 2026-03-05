#!/usr/bin/env python3
"""
海康接口使用示例和测试代码

演示如何使用 HikVisionClient 类获取监控点列表和RTSP流地址
"""

import asyncio

from config.get_hik import (
    HikVisionClient,
    HikSettings,
    get_hik_client,
    get_hik_camera_codes,
    get_hik_rtsp_url,
)


async def test_hik_connection():
    """测试海康平台连接"""
    print('=== 测试海康平台连接 ===')

    client = get_hik_client()
    is_connected = await client.test_connection()

    if is_connected:
        print('✅ 海康平台连接成功')
    else:
        print('❌ 海康平台连接失败')

    return is_connected


async def test_get_camera_list():
    """测试获取监控点列表"""
    print('\n=== 测试获取监控点列表 ===')

    try:
        # 方式1：使用客户端实例
        client = get_hik_client()
        cameras = await client.get_camera_list(page_no=1, page_size=5)

        print(f'获取到 {len(cameras)} 个监控点:')
        for i, camera in enumerate(cameras, 1):
            name = camera.get('name', '未知')
            index_code = camera.get('indexCode', '未知')
            status = camera.get('status', '未知')
            print(f'  {i}. {name} (编号: {index_code}, 状态: {status})')

        return cameras

    except Exception as e:
        print(f'❌ 获取监控点列表失败: {e}')
        return []


async def test_get_camera_codes():
    """测试获取监控点编号列表"""
    print('\n=== 测试获取监控点编号列表 ===')

    try:
        # 方式2：使用便捷方法
        codes = await get_hik_camera_codes()

        print(f'获取到 {len(codes)} 个监控点编号:')
        for i, code in enumerate(codes[:10], 1):  # 只显示前10个
            print(f'  {i}. {code}')

        if len(codes) > 10:
            print(f'  ... 还有 {len(codes) - 10} 个编号')

        return codes

    except Exception as e:
        print(f'❌ 获取监控点编号列表失败: {e}')
        return []


async def test_get_rtsp_stream(camera_index_code: str):
    """测试获取RTSP流地址"""
    print(f'\n=== 测试获取RTSP流地址 (编号: {camera_index_code}) ===')

    try:
        # 方式3：使用便捷方法
        rtsp_url = await get_hik_rtsp_url(camera_index_code)

        print(f'✅ RTSP流地址: {rtsp_url}')
        return rtsp_url

    except Exception as e:
        print(f'❌ 获取RTSP流地址失败: {e}')
        return None


async def test_get_camera_detail(camera_index_code: str):
    """测试获取监控点详细信息"""
    print(f'\n=== 测试获取监控点详细信息 (编号: {camera_index_code}) ===')

    try:
        client = get_hik_client()
        detail = await client.get_camera_detail(camera_index_code)

        print('监控点详细信息:')
        print(f'  名称: {detail.get("name", "未知")}')
        print(f'  编号: {detail.get("indexCode", "未知")}')
        print(f'  状态: {detail.get("status", "未知")}')
        print(f'  IP地址: {detail.get("ip", "未知")}')
        print(f'  端口: {detail.get("port", "未知")}')
        print(f'  区域编码: {detail.get("regionIndexCode", "未知")}')

        return detail

    except Exception as e:
        print(f'❌ 获取监控点详细信息失败: {e}')
        return None


async def test_custom_config():
    """测试自定义配置"""
    print('\n=== 测试自定义配置 ===')

    # 创建自定义配置
    custom_config = HikSettings(
        hik_host='https://172.17.185.12:443',
        hik_app_key='20335062',
        hik_app_secret='HJcBnE7qbBFlzrmE8CAk',
        hik_timeout=30,
        hik_verify_ssl=False,
    )

    # 使用自定义配置创建客户端
    client = HikVisionClient(config=custom_config)

    try:
        cameras = await client.get_camera_list(page_no=1, page_size=3)
        print(f'✅ 使用自定义配置获取到 {len(cameras)} 个监控点')
        return True
    except Exception as e:
        print(f'❌ 使用自定义配置失败: {e}')
        return False


async def test_filtered_search():
    """测试过滤搜索"""
    print('\n=== 测试过滤搜索 ===')

    try:
        client = get_hik_client()

        # 按名称过滤
        cameras_by_name = await client.get_camera_list(
            name='摄像头',  # 搜索包含"摄像头"的监控点
            page_size=5,
        )
        print(f'按名称过滤获取到 {len(cameras_by_name)} 个监控点')

        # 按区域编码过滤
        cameras_by_region = await client.get_camera_list(
            region_codes=['root'],  # 搜索特定区域的监控点
            page_size=5,
        )
        print(f'按区域过滤获取到 {len(cameras_by_region)} 个监控点')

        return True

    except Exception as e:
        print(f'❌ 过滤搜索失败: {e}')
        return False


async def main():
    """主测试函数"""
    print('🚀 开始海康接口测试')

    # 1. 测试连接
    is_connected = await test_hik_connection()
    if not is_connected:
        print('❌ 连接失败，终止测试')
        return

    # 2. 测试获取监控点列表
    cameras = await test_get_camera_list()

    # 3. 测试获取监控点编号列表
    codes = await test_get_camera_codes()

    # 4. 如果有监控点，测试获取RTSP流和详细信息
    if codes:
        first_code = codes[0]

        # 测试获取RTSP流地址
        await test_get_rtsp_stream(first_code)

        # 测试获取监控点详细信息
        await test_get_camera_detail(first_code)

    # 5. 测试自定义配置
    await test_custom_config()

    # 6. 测试过滤搜索
    await test_filtered_search()

    print('\n🎉 海康接口测试完成')


if __name__ == '__main__':
    # 运行测试
    asyncio.run(main())
