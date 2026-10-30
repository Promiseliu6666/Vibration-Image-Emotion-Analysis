"""一键无线接入：从设备控制台读 MAC → 登记设备与专属密钥 → 把上传地址写进设备。

网页上的"Wi-Fi 接入"按钮（POST /api/workspace/wireless-setup）与命令行脚本
tools/setup_wireless.py 共用这一份实现，避免两条路各写一遍。
失败一律抛 RuntimeError，消息是可以直接给用户看的中文原因。
"""
import re
import secrets
import socket
import time
import psutil
from threading import RLock

import psutil

VID, PID = 0x1A86, 0x55D2        # 语音控制台（CH343）的 USB 标识
LOCK = RLock()                    # 串口同一时刻只允许一个接入流程


def candidate_ports():
    from serial.tools import list_ports
    return [p for p in list_ports.comports() if p.vid == VID and p.pid == PID]


def talk(port, command, timeout=4.0):
    """给设备控制台发一行命令，收集它打印回来的内容。"""
    import serial
    connection = serial.Serial(port=None, baudrate=115200, timeout=.2, write_timeout=2)
    connection.dtr = False
    connection.rts = False
    connection.port = port
    connection.open()
    try:
        connection.reset_input_buffer()
        connection.write(command.encode('ascii') + b'\r\n')
        connection.flush()
        pending = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pending.extend(connection.read(4096))
        return pending.decode('utf-8', errors='ignore')
    finally:
        connection.close()


def find_console():
    """返回 (串口, Wi-Fi MAC)；跳过摄像头那一路串口。"""
    ports = candidate_ports()
    if not ports:
        raise RuntimeError('没有发现 Watcher。请插上能传数据的 USB 线，再试一次。')
    skipped = []
    for port in ports:
        try:
            text = talk(port.device, 'read_mac')
        except Exception as error:
            skipped.append(f'{port.device}（打不开：{error}）')
            continue
        match = re.search(r'wifi_sta_mac:\s*([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})', text)
        if match:
            return port.device, match.group(1).upper()
        skipped.append(f'{port.device}（不是语音控制台）')
    raise RuntimeError('找到了串口但没有回应，请确认设备已通电并运行本项目固件。'
                       + ('已跳过：' + '、'.join(skipped) if skipped else ''))


def preferred_address():
    """挑一个能被设备访问到的本机局域网地址。"""
    found = []
    for interfaces in psutil.net_if_addrs().values():
        for address in interfaces:
            if address.family != socket.AF_INET:
                continue
            ip = address.address
            if ip.startswith(('127.', '169.254.')):
                continue
            found.append(ip)
    for prefix in ('192.168.', '10.', '172.'):
        for ip in found:
            if ip.startswith(prefix):
                return ip
    return found[0] if found else None


def register(mac, name, expect_device_id=None):
    """在本地数据库登记这台物理设备，返回 (device_id, 明文密钥)。"""
    from app.core import access_control as access
    from app.core.db import get_connection
    hardware = mac.replace(':', '').replace('-', '').upper()
    if not re.fullmatch(r'[0-9A-F]{12}',hardware) or hardware=='000000000000':
        raise RuntimeError('设备没有提供有效的物理 MAC，接入已停止。')
    token = secrets.token_urlsafe(32)
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT device_id FROM device_credentials WHERE hardware_id=%s', (hardware,))
            row = cursor.fetchone()
            if row:
                device_id = row['device_id']
            else:
                # A sole existing device is not evidence that this is the same physical unit.
                device_id = 'watcher-' + hardware
            if expect_device_id and device_id != expect_device_id:
                raise RuntimeError('插在 USB 上的这台设备对应记录“' + device_id + '”，'
                                   '不是你要接入的“' + expect_device_id + '”；请确认要接入哪一台。')
            cursor.execute('SELECT id FROM devices WHERE device_id=%s', (device_id,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO devices(device_id,name,bind_code,created_at) VALUES(%s,%s,%s,UTC_TIMESTAMP())',
                               (device_id, name, ''))
            cursor.execute('INSERT INTO device_credentials(device_id,hardware_id,key_hash,enabled) '
                           'VALUES(%s,%s,%s,1) ON DUPLICATE KEY UPDATE key_hash=VALUES(key_hash),enabled=1',
                           (device_id, hardware, access.key_hash(token)))
        connection.commit()
    finally:
        connection.close()
    return device_id, token


def provision(name='小智伴学（无线）', expect_device_id=None):
    """整套接入流程；返回 {'device_id','mac','address','url','log','status'}。"""
    from app.core import site_settings
    steps = []
    with LOCK:
        if not site_settings.read()['lan_enabled']:
            raise RuntimeError('还没打开“允许其他设备访问”。请到设置 → 运行与网络里打开，重启后再试。')
        address = preferred_address()
        if not address:
            raise RuntimeError('找不到本机的网络地址，请确认电脑已连上 Wi-Fi 或网线。')
        steps.append(f'本机网络地址：{address}')
        port, mac = find_console()
        steps.append(f'控制台端口：{port}')
        steps.append(f'设备 MAC：{mac}')
        if 'Unrecognized command' in talk(port, 'study_lan_status', 4):
            raise RuntimeError('这台设备还在运行旧固件，没有无线上传命令，请先烧录新固件。')
        device_id, token = register(mac, name, expect_device_id=expect_device_id)
        steps.append(f'已登记设备记录：{device_id}')
        url = f'http://{address}:8000/api/device/frame'
        answer = talk(port, f'study_lan_config {url} {token}', 6)
        if 'saved' not in answer:
            raise RuntimeError('设备没有确认保存配置，请检查固件与连接后重试。')
        steps.append('已把上传地址写进设备')
        status = talk(port, 'study_lan_status', 4)
        return {'device_id': device_id, 'mac': mac, 'address': address, 'url': url, 'log': steps, 'status': status.replace(token,'[已隐藏]')}
