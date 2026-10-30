"""把服务端判定好的状态压成标志位，屏幕文案与语音提醒交给固件决定。

一行命令同时驱动状态屏与语音，不再为每种提醒各发一条命令：

    study_sync <状态码> <标志位> <连续用眼分> <屏幕累计分> <在位分> <允许固件播报> <久坐间隔>

判定仍然只有一处（analyzer + risk_flags）：这里只做"取码 + 节流 + 下发"。固件按同一套
状态码与标志位拼出屏幕上那句话（口径与页面一致），并自己决定要不要播本地中文提醒。

刷新策略：

* 行内容变化：立即下发（MIN_INTERVAL_SECONDS 内只发一条，抑制状态来回跳）；
* 行内容不变：每 HEARTBEAT_SECONDS 续期一次；
* 固件端 TTL 60 秒，所以服务端一旦停止，屏幕会自动淡出，不会永久挂着过时状态；
* 与语音提醒共用同一个串口控制台，冲突时本轮跳过、下一轮重试；
* 老固件没有 study_sync：自动退回 study_state 文本命令，并让服务端继续负责播报。
"""
import asyncio
import time
from collections import OrderedDict

from app.analysis import device_voice
from app.analysis.phone_alerts import play_local_voice, send_console

COMMAND = 'study_sync'
ACK_TYPE = 'study_sync_ack'
DISPLAY_COMMAND = 'study_display'
DISPLAY_ACK_TYPE = 'study_display_ack'
# 老固件只有文本命令；保留它作为退路，不用为这一版专门维护两份固件行为。
LEGACY_COMMAND = 'study_state'
LEGACY_ACK_TYPE = 'study_state_ack'

# 固件播报（默认开）。关掉后退回服务端播报，不必重新烧固件。
DEVICE_VOICE = True
SERVER_VOICE_GAP_SECONDS = 45

# 心跳比固件端的 60 秒有效期短就够了；间隔调大是为了少开关串口（串口那侧是 CDC 设备）。
HEARTBEAT_SECONDS = 20
MIN_INTERVAL_SECONDS = 3
# 固件要等本地音频播完才回执，超时给得比纯显示宽一些。
ACK_TIMEOUT_SECONDS = 14.0
# 退回文本模式后隔一段时间再试一次标志位：用户刷完新固件不用重启服务端。
REPROBE_SECONDS = 300

# 久坐语音读取现有提醒偏好。0 分钟表示用户在页面上关闭了这类提醒。
DEFAULT_VOICE_PREFERENCES = {
    'reminders_enabled': True,
    'phone_enabled': True,
    'eye_enabled': True,
    'break_minutes': 45,
    'break_enabled': True,
    'posture_enabled': True,
    'fatigue_enabled': True,
    'away_enabled': True,
    'quality_enabled': True,
    'lying_enabled': True,
    'phone_trigger_seconds': 4,
    'eye_trigger_minutes': 20,
    'posture_trigger_seconds': 4,
    'lying_trigger_seconds': 10,
    'break_repeat_minutes': 45,
    'fatigue_trigger_seconds': 60,
    'away_trigger_seconds': 60,
    'quality_trigger_seconds': 15,
    'phone_interval_minutes': 1,
    'eye_interval_minutes': 20,
    'posture_interval_minutes': 10,
    'lying_interval_minutes': 10,
    'fatigue_interval_minutes': 10,
    'away_interval_minutes': 3,
    'quality_interval_minutes': 5,
}
PREFERENCE_CACHE_SECONDS = 5

# 与 static/console.js、app/api/monthly_report.py 保持同一套说法，不另造一份文案。
LABELS = {
    'engaged_reading': '投入阅读',
    'engaged_writing': '投入书写',
    'engaged_screen': '听讲 / 朝向学习区',
    'engaged_computer': '电脑操作',
    'engaged_hand_raising': '举手互动',
    'engaged_discussing': '讨论交流',
    'standing': '站立活动',
    'distracted_phone': '使用手机',
    'distracted_away': '视线离开',
    'resting': '休息',
    'fatigued': '疲劳迹象',
    'thinking': '活动未确认',
    'absent': '未识别到人',
}

# 状态码：必须与固件 kStudyStateLabels 的下标一一对应（顺序即协议）。
STATE_CODES = {
    'absent': 0,
    'engaged_reading': 1,
    'engaged_writing': 2,
    'engaged_screen': 3,
    'engaged_computer': 4,
    'engaged_hand_raising': 5,
    'engaged_discussing': 6,
    'standing': 7,
    'distracted_phone': 8,
    'distracted_away': 9,
    'resting': 10,
    'fatigued': 11,
    'thinking': 12,
}
# 20 + n：固件渲染成"正在确认 <n 对应的状态词>"。页面也是这个口径。
CONFIRM_OFFSET = 20

# 标志位：必须与固件 kFlag* 常量一一对应。
FLAG_BITS = {
    'attention_phone': 0x01,
    'attention_away': 0x02,
    'eye_fatigue': 0x04,
    'eye_nearwork': 0x08,
    'posture_tilt': 0x10,
    'posture_lying': 0x20,
    'quality_poor': 0x40,
    'sedentary_due': 0x80,
}

TRIGGER_RULES = (
    ('phone',('phone',),'phone_trigger_seconds','phone_interval_minutes',0,FLAG_BITS['attention_phone']),
    ('eye',('eye',),'eye_trigger_minutes','eye_interval_minutes',0,FLAG_BITS['eye_nearwork']),
    ('posture',('posture','posture_escalated'),'posture_trigger_seconds','posture_interval_minutes',0,FLAG_BITS['posture_tilt']),
    ('lying',('lying',),'lying_trigger_seconds','lying_interval_minutes',10,FLAG_BITS['posture_lying']),
    ('fatigue',('fatigue','fatigue_escalated'),'fatigue_trigger_seconds','fatigue_interval_minutes',60,FLAG_BITS['eye_fatigue']),
    ('away',('away',),'away_trigger_seconds','away_interval_minutes',0,FLAG_BITS['attention_away']),
    ('quality',('quality',),'quality_trigger_seconds','quality_interval_minutes',15,FLAG_BITS['quality_poor']),
)

ENABLED_KEYS = {
    'phone': 'phone_enabled',
    'eye': 'eye_enabled',
    'posture': 'posture_enabled',
    'lying': 'lying_enabled',
    'fatigue': 'fatigue_enabled',
    'away': 'away_enabled',
    'quality': 'quality_enabled',
    'sit': 'break_enabled',
}

VOICE_PRIORITY = ('phone','lying','fatigue','away','quality','posture','sit','eye')

VOICE_RISK_SOURCE = {
    'phone': 'attention_phone',
    'eye': 'eye_nearwork',
    'posture': 'posture_tilt',
    'lying': 'posture_lying',
    'sit': 'sedentary_due',
    'fatigue': 'eye_fatigue',
    'away': 'attention_away',
    'quality': 'quality_poor',
}


def _seconds(value):
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _span(prefix, seconds):
    minutes = _seconds(seconds) // 60
    return f'{prefix} {minutes} 分' if minutes >= 1 else ''


def _detail(result, observations, flags):
    """一行里最有信息量的那一项：先风险标志位，再看时长。"""
    if flags.get('attention_phone') == 1 or result.get('learning_state') == 'distracted_phone':
        played = ((result.get('phone_alert') or {}).get('voice_status') == 'played')
        return '已语音提醒' if played else '手机在手'
    if flags.get('attention_away') == 1:
        return '视线离开'
    if flags.get('eye_fatigue') == 1:
        return '疲劳迹象'
    if flags.get('eye_nearwork') == 1:
        return _span('连续用眼', observations.get('near_work_seconds'))
    if flags.get('posture_tilt') == 1:
        return '坐姿倾斜'
    if flags.get('posture_lying') == 1:
        return '疑似趴桌'
    if flags.get('quality_poor') == 1:
        return '画面不清晰'
    if flags.get('sedentary_due') == 1:
        return '连续在位过久'
    near = _span('连续用眼', observations.get('near_work_seconds'))
    if near:
        return near
    return _span('在位', observations.get('presence_seconds'))


def state_line(result):
    """一行短句：`状态词 · 关键依据`。没有依据时只给状态词。"""
    result = result or {}
    evidence = result.get('evidence') or {}
    observations = evidence.get('observations') or {}
    flags = evidence.get('flags') or {}
    if not result.get('person_present'):
        return LABELS['absent']
    state = result.get('learning_state') or ''
    if state == 'thinking':
        candidate = evidence.get('candidate_state')
        base = ('正在确认' + LABELS[candidate]) if candidate in LABELS else LABELS['thinking']
    else:
        base = LABELS.get(state) or '正在监测'
    detail = _detail(result, observations, flags)
    return f'{base} · {detail}' if detail else base


def _minutes(value):
    """固件端用一字节存分钟数；超过 255 分钟按 255 算。"""
    return min(255, _seconds(value) // 60)


def state_code(result):
    """状态码：无人 = 0；"正在确认 X"用 CONFIRM_OFFSET + X 的码表示。"""
    result = result or {}
    if not result.get('person_present'):
        return STATE_CODES['absent']
    state = result.get('learning_state') or ''
    if state == 'thinking':
        candidate = (result.get('evidence') or {}).get('candidate_state')
        if candidate in STATE_CODES:
            return CONFIRM_OFFSET + STATE_CODES[candidate]
        return STATE_CODES['thinking']
    return STATE_CODES.get(state, STATE_CODES['thinking'])


def flag_bits(result):
    """把 risk_flags 压成位标志；手机状态本身就是一条提醒依据（与页面口径一致）。"""
    result = result or {}
    evidence = result.get('evidence') or {}
    flags = evidence.get('flags') or {}
    observations = evidence.get('observations') or {}
    bits = 0
    for name, bit in FLAG_BITS.items():
        if flags.get(name) == 1:
            bits |= bit
    if result.get('learning_state') == 'distracted_phone':
        bits |= FLAG_BITS['attention_phone']
    return bits


def _preference_minutes(value, enabled=True):
    if not enabled:
        return 0
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = DEFAULT_VOICE_PREFERENCES['break_minutes']
    return max(15, min(90, value))


def _enabled_bits(result, preferences):
    bits = flag_bits(result)
    if not preferences['phone_enabled']:
        bits &= ~FLAG_BITS['attention_phone']
    if not preferences['eye_enabled']:
        bits &= ~FLAG_BITS['eye_nearwork']
    if not preferences['fatigue_enabled']:
        bits &= ~FLAG_BITS['eye_fatigue']
    if not preferences['away_enabled']:
        bits &= ~FLAG_BITS['attention_away']
    if not preferences['quality_enabled']:
        bits &= ~FLAG_BITS['quality_poor']
    if not preferences['posture_enabled']:
        bits &= ~FLAG_BITS['posture_tilt']
    if not preferences['lying_enabled']:
        bits &= ~FLAG_BITS['posture_lying']
    if not preferences['break_enabled']:
        bits &= ~FLAG_BITS['sedentary_due']
    return bits


def display_line(result, preferences=None):
    result = result or {}
    observations = (result.get('evidence') or {}).get('observations') or {}
    prefs = dict(DEFAULT_VOICE_PREFERENCES)
    prefs.update(preferences or {})
    bits = _enabled_bits(result, prefs)
    return (f'{state_code(result)} {bits:02X} '
            f'{_minutes(observations.get("near_work_seconds"))} '
            f'{_minutes(observations.get("presence_seconds"))}')


def sync_line(result, preferences=None, suppressed_bits=0, suppress_break=False):
    """`study_sync ... <允许播报> <久坐分钟>`；久坐分钟为 0 时关闭该类语音。"""
    result = result or {}
    observations = (result.get('evidence') or {}).get('observations') or {}
    prefs = dict(DEFAULT_VOICE_PREFERENCES)
    prefs.update(preferences or {})
    bits = _enabled_bits(result, prefs)
    bits &= ~suppressed_bits
    break_minutes = 0 if suppress_break else _preference_minutes(prefs['break_minutes'], prefs['break_enabled'])
    allow_voice = 1 if DEVICE_VOICE and prefs['reminders_enabled'] else 0
    return (f'{state_code(result)} {bits:02X} '
            f'{_minutes(observations.get("near_work_seconds"))} '
            f'{_minutes(observations.get("screen_seconds"))} '
            f'{_minutes(observations.get("presence_seconds"))} '
            f'{allow_voice} {break_minutes}')


def load_voice_preferences(device_id=None):
    """读取管理员当前使用的提醒偏好；读取失败时安全回退到默认设置。"""
    try:
        from app.api.health_api import load_reminder_settings
        from app.core.config import ADMIN_USERNAME
        return load_reminder_settings(device_id,ADMIN_USERNAME)
    except Exception:
        return dict(DEFAULT_VOICE_PREFERENCES)


class ScreenSync:
    """每个物理设备一份状态：按行去重、心跳续期、同一时刻只允许一条在途。

    mode='flags'：新固件，发标志位，屏幕文案与语音都由固件决定；
    mode='text'：老固件，退回中文文本命令，语音由服务端播报。
    """

    def __init__(self, preference_loader=None, direct_voice=False):
        self.devices = OrderedDict()
        self.tasks = set()
        self.preference_loader = preference_loader
        self.direct_voice = direct_voice

    def entry(self, device):
        if device not in self.devices:
            self.devices[device] = dict(line=None, text=None, sent_at=0.0, sending=False,
                                        mode='flags', status='idle', error=None,
                                        voice=None, what=None, probe_at=0.0,
                                        preferences=dict(DEFAULT_VOICE_PREFERENCES),
                                        preferences_at=0.0,reminder_times={},
                                        condition_since={},condition_last={},sit_last_seen=0.0,
                                        voice_sending=False,voice_retry_at=0.0,last_any_voice=0.0)
        self.devices.move_to_end(device)
        while len(self.devices) > 64:
            candidate = next((key for key, value in self.devices.items() if not value['sending']), None)
            if candidate is None:
                break
            self.devices.pop(candidate)
        return self.devices[device]

    def snapshot(self, device):
        item = self.devices.get(device) or {}
        return {'text': item.get('text'), 'line': item.get('line'),
                'mode': item.get('mode', 'flags'), 'status': item.get('status', 'idle'),
                'voice': item.get('voice'), 'what': item.get('what'),
                'error': item.get('error'), 'sent_at': item.get('sent_at')}

    def preferences_for(self, device, now=None):
        now = time.monotonic() if now is None else now
        item = self.entry(device)
        if self.preference_loader and now - item['preferences_at'] >= PREFERENCE_CACHE_SECONDS:
            prefs = dict(DEFAULT_VOICE_PREFERENCES)
            prefs.update(self.preference_loader(device) or {})
            item['preferences'] = prefs
            item['preferences_at'] = now
        return dict(item['preferences'])

    def condition_active(self, result, key):
        evidence = result.get('evidence') or {}
        observations = evidence.get('observations') or {}
        if key == 'phone':
            return evidence.get('phone_held') is True
        if key == 'eye':
            return observations.get('near_work_activity') is True
        if key == 'posture':
            slope = observations.get('shoulder_slope')
            return bool(observations.get('posture_assessable') and slope is not None and abs(float(slope)) > .35)
        if key == 'lying':
            angle = result.get('torso_angle')
            return bool(result.get('person_present') and angle is not None and float(angle) < 25)
        if key == 'fatigue':
            level = result.get('fatigue_level')
            return bool(evidence.get('fatigue_calibrated') and level is not None and float(level) >= .6)
        if key == 'away':
            seconds = observations.get('gaze_away_seconds')
            return bool(seconds is not None and float(seconds) > 0) or (evidence.get('flags') or {}).get('attention_away') == 1
        if key == 'quality':
            quality = observations.get('quality')
            sharpness = observations.get('sharpness')
            return bool(quality in ('dark','overexposed') or observations.get('posture_reason') == 'too_far'
                        or (sharpness is not None and float(sharpness) < 5))
        return False

    @staticmethod
    def _pref_seconds(preferences, key, minutes=False):
        try: value = max(0, int(preferences.get(key, 0)))
        except (TypeError, ValueError): value = 0
        return value * 60 if minutes else value

    @staticmethod
    def condition_duration(result, key):
        observations = ((result.get('evidence') or {}).get('observations') or {})
        if key == 'eye':
            return max(0,float(observations.get('near_work_seconds') or 0))
        if key == 'away':
            return max(0,float(observations.get('gaze_away_seconds') or 0))
        return 0

    def update_conditions(self, item, result, now):
        active = {}
        played = item['reminder_times']
        for active_key, whats, *_ in TRIGGER_RULES:
            is_active = self.condition_active(result, active_key)
            active[active_key] = is_active
            if is_active:
                item['condition_since'].setdefault(
                    active_key, now - self.condition_duration(result, active_key))
                item['condition_last'][active_key] = now
            else:
                last_active = item['condition_last'].get(active_key,0)
                if last_active and now-last_active > 5:
                    item['condition_since'].pop(active_key,None)
                    item['condition_last'].pop(active_key,None)
                    for what in whats:
                        played.pop(what,None)
        return active

    def suppressed_bits(self, item, result, preferences, now):
        masked = 0
        played = item['reminder_times']
        active_conditions = self.update_conditions(item, result, now)
        for active_key, whats, trigger_key, repeat_key, lead_seconds, bit in TRIGGER_RULES:
            if not active_conditions[active_key]:
                continue
            trigger = self._pref_seconds(preferences,trigger_key,trigger_key.endswith('_minutes'))
            since = item['condition_since'][active_key]
            if now-since < max(0,trigger-lead_seconds):
                masked |= bit
            last = max((played.get(what, 0) for what in whats), default=0)
            repeat = self._pref_seconds(preferences,repeat_key,True)
            if last and now-last < max(0,repeat-lead_seconds):
                masked |= bit
        return masked

    def suppress_break(self, item, result, preferences, now):
        presence = ((result.get('evidence') or {}).get('observations') or {}).get('presence_seconds') or 0
        if not result.get('person_present') or float(presence) <= 0:
            if item.get('sit_last_seen') and now-item['sit_last_seen'] > 5:
                item['reminder_times'].pop('sit',None)
                item['sit_last_seen'] = 0.0
            return False
        item['sit_last_seen'] = now
        last = item['reminder_times'].get('sit',0)
        repeat = self._pref_seconds(preferences,'break_repeat_minutes',True)
        return bool(last and now-last < repeat)

    def due_reminder(self, item, result, preferences, now):
        if (not self.direct_voice or not preferences['reminders_enabled'] or
                item['voice_sending'] or now < item['voice_retry_at'] or
                (item['last_any_voice'] and now-item['last_any_voice'] < SERVER_VOICE_GAP_SECONDS)):
            return None
        active = self.update_conditions(item, result, now)
        ready = {}
        for active_key, whats, trigger_key, repeat_key, _lead, _bit in TRIGGER_RULES:
            if not preferences[ENABLED_KEYS[active_key]] or not active[active_key]:
                continue
            trigger = self._pref_seconds(
                preferences,trigger_key,trigger_key.endswith('_minutes'))
            elapsed = self.condition_duration(result,active_key)
            if not elapsed:
                elapsed = now-item['condition_since'][active_key]
            if elapsed < trigger:
                continue
            last = max((item['reminder_times'].get(what,0) for what in whats),default=0)
            repeat = self._pref_seconds(preferences,repeat_key,True)
            if not last or now-last >= repeat:
                ready[active_key] = active_key

        flags = (result.get('evidence') or {}).get('flags') or {}
        if result.get('person_present') and flags.get('sedentary_due') == 1:
            item['sit_last_seen'] = now
            last = item['reminder_times'].get('sit',0)
            repeat = self._pref_seconds(preferences,'break_repeat_minutes',True)
            if preferences['break_enabled'] and (not last or now-last >= repeat):
                ready['sit'] = 'sit'
        elif item['sit_last_seen'] and now-item['sit_last_seen'] > 5:
            item['reminder_times'].pop('sit',None)
            item['sit_last_seen'] = 0.0

        for kind in VOICE_PRIORITY:
            if kind in ready:
                return kind
        return None

    def start_voice(self, device, kind):
        item = self.entry(device)
        if item['voice_sending']:
            return False
        item['voice_sending'] = True
        task = asyncio.create_task(self.play_voice(device,kind))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return True

    async def play_voice(self, device, kind):
        item = self.entry(device)
        try:
            status,error = await asyncio.to_thread(play_local_voice,device,kind)
            now = time.monotonic()
            if status == 'played':
                item['reminder_times'][kind] = now
                item['last_any_voice'] = now
                item['voice'] = 'played'
                item['what'] = kind
                item['error'] = None
            else:
                item['voice'] = status
                item['what'] = kind
                item['error'] = error
                item['voice_retry_at'] = now + 5
        except Exception as exc:
            now = time.monotonic()
            item['voice'] = 'failed'
            item['what'] = kind
            item['error'] = str(exc)
            item['voice_retry_at'] = now + 5
        finally:
            item['voice_sending'] = False

    def observe(self, device, result, now=None, fresh=True, preferences=None):
        """每帧调用一次。返回当前下发状态，供页面或日志查看。"""
        if not fresh:
            return self.snapshot(device)
        now = time.monotonic() if now is None else now
        item = self.entry(device)
        if preferences is not None:
            item['preferences'].update(preferences)
        else:
            self.preferences_for(device, now)
        due = self.due_reminder(item, result, item['preferences'], now) if self.direct_voice else None
        if self.direct_voice:
            line = display_line(result, item['preferences'])
        else:
            suppressed = self.suppressed_bits(item, result, item['preferences'], now)
            suppress_break = self.suppress_break(item, result, item['preferences'], now)
            line = sync_line(result, item['preferences'], suppressed, suppress_break)
        text = state_line(result)  # 只在退回文本命令时用得上
        if item['mode'] == 'text' and now >= item['probe_at']:
            # 隔一段时间重试一次标志位：用户可能刚刷了新固件，不必重启服务端。
            item['mode'] = 'flags'
        if not line:
            if due and not item['voice_sending']:
                self.start_voice(device, due)
            return self.snapshot(device)
        if item['sending']:
            return self.snapshot(device)
        if line != item['line']:
            if now - item['sent_at'] < MIN_INTERVAL_SECONDS:
                if due and not item['voice_sending']:
                    self.start_voice(device, due)
                return self.snapshot(device)
        elif now - item['sent_at'] < HEARTBEAT_SECONDS:
            if due and not item['voice_sending']:
                self.start_voice(device, due)
            return self.snapshot(device)
        self.start(device, line, text, now)
        return self.snapshot(device)

    def start(self, device, line, text, now=None):
        item = self.entry(device)
        stamp = time.monotonic() if now is None else now
        item.update(sending=True, line=line, text=text, error=None, status='sending',
                    sent_at=stamp, clock=stamp)
        task = asyncio.create_task(self.deliver(device))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return True

    async def deliver(self, device):
        item = self.entry(device)
        line, text, mode, ack = item['line'], item['text'], item['mode'], {}
        try:
            if mode == 'flags':
                if self.direct_voice:
                    status,error,ack = await asyncio.to_thread(
                        send_console,device,f'{DISPLAY_COMMAND} {line}',
                        ack_type=DISPLAY_ACK_TYPE,timeout=ACK_TIMEOUT_SECONDS,detail=True)
                else:
                    status,error,ack = await asyncio.to_thread(
                        send_console,device,f'{COMMAND} {line}',
                        ack_type=ACK_TYPE,timeout=ACK_TIMEOUT_SECONDS,detail=True)
                if status == 'unavailable' or ack.get('reason') == 'usage':
                    # 这台设备的固件还没有 study_sync：退回文本命令，语音继续由服务端播。
                    mode = item['mode'] = 'text'
                    item['probe_at'] = (item.get('clock') or time.monotonic()) + REPROBE_SECONDS
                    device_voice.mark(device, False)
                    status, error = await asyncio.to_thread(
                        send_console, device, f'{LEGACY_COMMAND} {text}',
                        ack_type=LEGACY_ACK_TYPE)
            else:
                status, error = await asyncio.to_thread(
                    send_console, device, f'{LEGACY_COMMAND} {text}',
                    ack_type=LEGACY_ACK_TYPE)
        except Exception as exc:  # 串口异常不该影响分析主流程
            status, error = 'failed', str(exc)
        if mode == 'flags' and status == 'ok':
            # 固件接管播报：服务端不再抢同一个扬声器，页面改读固件回执里的 voice。
            device_voice.mark(device, False if self.direct_voice else DEVICE_VOICE)
        item.update(sending=False, status=status, error=error,
                    voice=ack.get('voice'), what=ack.get('what'))
        if status == 'ok' and ack.get('voice') == 'played' and ack.get('what') not in (None,'none'):
            item.setdefault('reminder_times',{})[ack['what']] = time.monotonic()
        # 失败时保留本次行与 sent_at：下一轮要么等心跳、要么等内容变化再试，不立刻重发。


screen_sync = ScreenSync(load_voice_preferences,direct_voice=True)
