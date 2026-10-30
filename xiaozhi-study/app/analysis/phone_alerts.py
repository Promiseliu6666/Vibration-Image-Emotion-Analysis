"""Per-physical-device phone warnings and acknowledged USB speaker playback."""
import asyncio
import json
import time
import uuid
from collections import OrderedDict

from app.analysis import device_voice

TEXT = '检测到你正在使用手机，请放下手机，回到学习。'


class PhoneAlerts:
    def __init__(self):
        self.devices = OrderedDict()
        self.tasks = set()

    def entry(self, device):
        if device not in self.devices:
            self.devices[device] = dict(active=False, count=0, since=0, seen=0,
                                       last_reminded=None, retry_after=0, voice_status='idle')
        self.devices.move_to_end(device)
        while len(self.devices) > 64:
            candidate = next((key for key, value in self.devices.items()
                              if value['voice_status'] != 'sending'), None)
            if candidate is None:
                break
            self.devices.pop(candidate)
        return self.devices[device]

    def observe(self, device, result, now=None, fresh=True, enabled=True,
                cooldown_seconds=60, managed_elsewhere=False):
        now = time.time() if now is None else now
        item = self.entry(device)
        item['stale'] = not fresh
        item['enabled'] = bool(enabled)
        flags = (result.get('evidence') or {}).get('flags') or {}
        active = fresh and bool(result.get('person_present')) and (
            result.get('learning_state') == 'distracted_phone' or flags.get('attention_phone') == 1)
        if active:
            if not item['active'] or now - item['seen'] > 8:
                item.update(count=0, since=now, event_id=uuid.uuid4().hex)
            item['count'] += 1
        else:
            item.update(count=0, since=0)
        item.update(active=active, seen=now)
        item['confirmed'] = bool(active and (result.get('learning_state') == 'distracted_phone'
                                           or (item['count'] >= 3 and now-item['since'] >= 4)))
        # Muting audio must not mute detection, saved evidence or persistent alerts.
        if not enabled:
            item['voice_status'] = 'disabled'
            return self.snapshot(device)
        if item['voice_status'] == 'disabled':
            item['voice_status'] = 'idle'
        cooldown_seconds = max(60, int(cooldown_seconds))
        if (active and item['count'] >= 3 and now - item['since'] >= 4
                and now >= item['retry_after'] and item['voice_status'] != 'sending'
                and (item['last_reminded'] is None or now - item['last_reminded'] >= cooldown_seconds)):
            if managed_elsewhere:
                item.update(voice_status='scheduler', last_reminded=now, error=None)
            elif device_voice.plays(device):
                # 固件按标志位自己播报（study_sync）：服务端只记事件，不再抢同一个扬声器。
                item.update(voice_status='device', last_reminded=now, error=None)
            else:
                self.start(device)
        return self.snapshot(device)

    def snapshot(self, device):
        item = self.devices.get(device, {})
        return {key: item.get(key) for key in
                ('active', 'confirmed', 'since', 'enabled', 'event_id', 'voice_status', 'last_reminded', 'error', 'stale')} | {'text': TEXT}

    def start(self, device):
        item = self.entry(device)
        if item['voice_status'] == 'sending':
            return False
        item.update(voice_status='sending', error=None)
        task = asyncio.create_task(self.deliver(device, item))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return True

    async def deliver(self, device, item):
        try:
            status, error = await asyncio.to_thread(play_usb, device)
            item.update(voice_status=status, error=error, retry_after=time.time() + 15)
            if status == 'played':
                item['last_reminded'] = time.time()
        except Exception:
            item.update(voice_status='failed', error='语音发送失败，请检查小智连接。', retry_after=time.time() + 15)
        finally:
            from app.core import live_state
            live_state.alert_updated(device, self.snapshot(device))


import threading

_voice_lock = threading.Lock()

_ALLOWED_VOICE_COMMANDS = {
    ('study_phone_alert', 'study_alert_ack'),
    ('study_eye_alert', 'study_eye_ack'),
}
_VOICE_KINDS = {'phone','eye','posture','lying','fatigue','away','sit','quality'}
_LEGACY_VOICE_COMMANDS = {
    'phone': ('study_phone_alert', 'study_alert_ack'),
    'eye': ('study_eye_alert', 'study_eye_ack'),
}

# 固件回执 → 对外状态与说明。只在这里映射一次，避免每个调用方各写一套说法。
_ACK_RESULTS = {
    'muted': ('muted', '小智音量为 0，请在设备上调高音量后重试。'),
    'busy': ('busy', '小智正在对话，稍后再提醒。'),
    'error': ('failed', '小智未能启动语音播放，请重试。'),
}


def play_usb(device, command='study_phone_alert', ack_type='study_alert_ack'):
    if (command, ack_type) not in _ALLOWED_VOICE_COMMANDS:
        return 'failed', '不支持的语音提醒命令。'
    if not _voice_lock.acquire(blocking=False):
        return 'busy', '上一条语音提醒还没播完。'
    try:
        return _play_usb(device, command, ack_type)
    finally:
        _voice_lock.release()


def play_test_usb(device, kind='phone'):
    """Play one local reminder sample without changing reminder state or cooldowns."""
    if kind not in _VOICE_KINDS:
        return 'failed', '不支持的测试提醒类型。'
    if not _voice_lock.acquire(blocking=False):
        return 'busy', '上一条语音还在播放，请稍候。'
    try:
        return _console(device, f'study_voice_test {kind}', 'study_voice_test_ack',
                        timeout=15, accepted=('played',))
    finally:
        _voice_lock.release()


def play_local_voice(device, kind):
    """One scheduler owns playback, including explicit old-firmware fallbacks.

    An absent port, busy/muted speaker, or missing acknowledgment never proves a
    command is unsupported: only an explicit unknown-command response may advance
    to another command. Keep the same serial lock throughout the fallback chain.
    """
    if kind not in _VOICE_KINDS:
        return 'failed', '不支持的提醒类型。'
    if not _voice_lock.acquire(blocking=False):
        return 'busy', '上一条语音还在播放，请稍候。'
    try:
        status,error,ack = _console(device,f'study_voice_play {kind}','study_voice_ack',
                                    timeout=15,accepted=('played',),detail=True)
        if ack.get('reason') == 'unsupported_command':
            # During staged upgrades the generic test command already provides the same
            # one-shot playback path without changing firmware reminder state.
            status,error,ack = _console(device,f'study_voice_test {kind}','study_voice_test_ack',
                                        timeout=15,accepted=('played',),detail=True)
            if ack.get('reason') == 'unsupported_command' and kind in _LEGACY_VOICE_COMMANDS:
                command,ack_type = _LEGACY_VOICE_COMMANDS[kind]
                status,error = _console(device,command,ack_type,
                                        timeout=15,accepted=('played',))
        return status,error
    finally:
        _voice_lock.release()


def _result(status, error, ack=None, detail=False):
    """detail=True 时把固件回执一并交给调用方（例如 study_sync 的 voice 字段）。"""
    return (status, error, ack or {}) if detail else (status, error)


def send_console(device, command, ack_type=None, timeout=6.0,
                 accepted=('shown', 'unchanged', 'cleared'), detail=False):
    """向同一物理设备的串口控制台发一条命令，返回 (status, error)。

    detail=True 时返回 (status, error, ack)，ack 是固件那条 JSON 回执本身。
    与语音提醒共用同一个串口，所以同样靠 _voice_lock 串行化：语音正在播时返回
    'busy'，调用方下一轮再试，绝不和播报交错写。命令允许 UTF-8（屏幕文案是中文）。
    """
    text = str(command or '')
    if not text or '\r' in text or '\n' in text:
        return _result('failed', '控制命令为空或包含换行。', detail=detail)
    if not _voice_lock.acquire(blocking=False):
        return _result('busy', '串口控制台正忙（语音提醒正在使用）。', detail=detail)
    try:
        return _console(device, text, ack_type, timeout, accepted, detail)
    finally:
        _voice_lock.release()


def _play_usb(device, command, ack_type):
    return _console(device, command, ack_type, 15, accepted=('played',))


def _console(device, command, ack_type, timeout, accepted, detail=False):
    from app.device import capture_control
    import serial
    from serial.tools import list_ports
    current = capture_control.status(device)
    identity = current.get('identity') or {}
    if not current.get('running') or current.get('device_id') != device:
        return _result('unavailable', '这台设备尚未连接本机 USB 通道。', detail=detail)
    usb_serial = identity.get('usb_serial')
    candidates = [p for p in list_ports.comports() if usb_serial and p.serial_number == usb_serial
                  and 'SERIAL-B' in (p.description or '').upper()]
    if len(candidates) != 1:
        return _result('unavailable', '未找到同一物理设备的控制端口。', detail=detail)
    port = candidates[0].device
    connection = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=2)
    connection.dtr = False
    connection.rts = False
    connection.port = port
    try:
        connection.open()
        if not any(p.device == port and p.serial_number == usb_serial for p in list_ports.comports()):
            return _result('failed', '设备连接发生变化，请重新检测。', detail=detail)
        connection.reset_input_buffer()
        connection.write((command+'\r\n').encode('utf-8'))
        connection.flush()
        pending = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pending.extend(connection.read(8192))
            if len(pending) > 65536:
                return _result('failed', '设备回执异常，请重新检测。', detail=detail)
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending = bytearray(rest)
                if b'Unrecognized command' in line:
                    return _result('unavailable', '当前固件没有这条控制命令，需要先更新固件。',
                                   {'reason': 'unsupported_command'}, detail)
                start = line.find(b'{')
                if start < 0:
                    continue
                try:
                    ack = json.loads(line[start:].strip())
                except (ValueError, UnicodeDecodeError):
                    continue
                if ack_type and ack.get('type') != ack_type:
                    continue
                status = str(ack.get('status') or '')
                if status in accepted:
                    return _result('played' if status == 'played' else 'ok', None, ack, detail)
                if status in _ACK_RESULTS:
                    mapped = _ACK_RESULTS[status]
                    return _result(mapped[0], mapped[1], ack, detail)
        return _result('failed', '没有收到小智回执，请检查设备。', detail=detail)
    except (serial.SerialException, OSError):
        return _result('failed', '控制端口无法打开，请检查 USB 或其他串口程序。', detail=detail)
    finally:
        if connection.is_open:
            connection.close()


alerts = PhoneAlerts()
