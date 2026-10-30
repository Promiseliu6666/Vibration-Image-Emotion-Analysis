import asyncio

from app.analysis import device_voice, state_sync
from app.analysis.state_sync import ScreenSync, state_line


def frame(state='engaged_reading', candidate=None, flags=None, **observations):
    return {
        'person_present': True,
        'learning_state': state,
        'evidence': {'observations': dict(observations), 'flags': dict(flags or {}),
                     'candidate_state': candidate},
    }


def test_line_mirrors_the_page_words():
    assert state_line({'person_present': False, 'learning_state': 'absent'}) == '未识别到人'
    reading = frame(presence_seconds=725, near_work_seconds=480)
    assert state_line(reading) == '投入阅读 · 连续用眼 8 分'
    unknown = frame('thinking', candidate='distracted_phone')
    assert state_line(unknown) == '正在确认使用手机'
    assert state_line(frame('thinking')) == '活动未确认'
    fresh = frame(presence_seconds=120)
    assert state_line(fresh) == '投入阅读 · 在位 2 分'


def test_risk_flags_win_over_plain_durations():
    away = frame(presence_seconds=900, flags={'attention_away': 1})
    assert state_line(away) == '投入阅读 · 视线离开'
    eyes = frame(presence_seconds=1800, flags={'eye_nearwork': 1}, near_work_seconds=1300)
    assert state_line(eyes) == '投入阅读 · 连续用眼 21 分'
    posture = frame(flags={'posture_tilt': 1})
    assert state_line(posture) == '投入阅读 · 坐姿倾斜'


def test_played_voice_reminder_is_reflected():
    result = frame('distracted_phone', presence_seconds=300)
    result['phone_alert'] = {'voice_status': 'played'}
    assert state_line(result) == '使用手机 · 已语音提醒'


def test_state_codes_and_flag_bits_match_the_firmware_table():
    # 固件 kStudyStateLabels / kFlag* 的顺序就是这份协议，改动必须两边同步。
    assert len(state_sync.STATE_CODES) == 13
    assert state_sync.STATE_CODES['absent'] == 0
    assert state_sync.STATE_CODES['engaged_reading'] == 1
    assert state_sync.STATE_CODES['distracted_phone'] == 8
    assert state_sync.STATE_CODES['thinking'] == 12
    assert state_sync.FLAG_BITS == {
        'attention_phone': 0x01, 'attention_away': 0x02, 'eye_fatigue': 0x04,
        'eye_nearwork': 0x08, 'posture_tilt': 0x10, 'posture_lying': 0x20,
        'quality_poor': 0x40, 'sedentary_due': 0x80,
    }


def test_sync_line_carries_code_flags_and_minutes():
    reading = frame(presence_seconds=725, near_work_seconds=480)
    assert state_sync.sync_line(reading) == '1 00 8 0 12 1 45'
    phone = frame('distracted_phone', presence_seconds=310, screen_seconds=1250)
    phone['evidence']['observations']['screen_activity'] = True
    assert state_sync.sync_line(phone) == '8 01 0 20 5 1 45'
    # "正在确认手机"用 20 + 状态码表示，固件渲染成"正在确认使用手机"。
    confirming = frame('thinking', candidate='distracted_phone')
    assert state_sync.sync_line(confirming) == '28 00 0 0 0 1 45'
    assert state_sync.state_code({'person_present': False, 'learning_state': 'absent'}) == 0
    # 分钟数按一字节截断，超过 255 分钟仍然安全。
    long_reading = frame(presence_seconds=999999, near_work_seconds=999999, flags={'eye_nearwork': 1})
    assert state_sync.sync_line(long_reading) == '1 08 255 0 255 1 45'

def test_display_line_only_carries_the_four_display_fields():
    reading = frame(presence_seconds=725, near_work_seconds=480,
                    flags={'posture_tilt': 1, 'sedentary_due': 1},
                    screen_seconds=300, screen_activity=True)
    assert state_sync.display_line(reading) == '1 90 8 12'


def test_sync_line_uses_reminder_preferences():
    posture = frame(presence_seconds=3600, flags={'posture_tilt': 1})
    preferences = {'break_minutes': 60, 'break_enabled': True, 'posture_enabled': False}
    assert state_sync.sync_line(posture, preferences) == '1 00 0 0 60 1 60'
    disabled = {'break_minutes': 15, 'break_enabled': False, 'posture_enabled': True}
    assert state_sync.sync_line(posture, disabled) == '1 10 0 0 60 1 0'

def test_sync_line_honors_each_reminder_category():
    result = frame('distracted_phone', presence_seconds=300, near_work_seconds=1300,
                   flags={'attention_phone': 1, 'attention_away': 1, 'eye_fatigue': 1,
                          'eye_nearwork': 1, 'posture_tilt': 1, 'posture_lying': 1,
                          'quality_poor': 1})
    preferences = {
        'reminders_enabled': False, 'phone_enabled': False, 'eye_enabled': False,
        'fatigue_enabled': False, 'posture_enabled': False, 'lying_enabled': False, 'away_enabled': False,
        'quality_enabled': False, 'break_minutes': 15, 'break_enabled': False,
    }
    assert state_sync.sync_line(result, preferences) == '8 00 21 0 5 0 0'

def test_reminder_intervals_mask_active_flags_until_due():
    sync = ScreenSync()
    item = sync.entry('dev-interval')
    phone = frame('distracted_phone', flags={'attention_phone': 1})
    phone['evidence']['phone_held'] = True
    preferences = {'phone_trigger_seconds': 4, 'phone_interval_minutes': 5}
    assert sync.suppressed_bits(item, phone, preferences, 100) == state_sync.FLAG_BITS['attention_phone']
    assert sync.suppressed_bits(item, phone, preferences, 104) == 0
    item['reminder_times'] = {'phone': 100}
    assert sync.suppressed_bits(item, phone, preferences, 399) == state_sync.FLAG_BITS['attention_phone']
    assert sync.suppressed_bits(item, phone, preferences, 400) == 0

def test_break_repeat_interval_is_independent_from_trigger_minutes():
    sync = ScreenSync()
    item = sync.entry('dev-sit')
    item['reminder_times'] = {'sit': 100}
    result = frame(presence_seconds=3600)
    preferences = {'break_minutes': 30, 'break_repeat_minutes': 60}
    assert sync.suppress_break(item, result, preferences, 3699)
    assert not sync.suppress_break(item, result, preferences, 3700)

def test_each_voice_kind_has_one_unique_risk_source():
    assert set(state_sync.VOICE_RISK_SOURCE)==set(state_sync.VOICE_PRIORITY)
    assert len(set(state_sync.VOICE_RISK_SOURCE.values()))==8
    assert state_sync.VOICE_RISK_SOURCE['sit']=='sedentary_due'

def test_sedentary_voice_is_driven_by_its_risk_flag():
    sync=ScreenSync(direct_voice=True)
    item=sync.entry('dev-sedentary')
    preferences=dict(state_sync.DEFAULT_VOICE_PREFERENCES)
    preferences['break_repeat_minutes']=1
    result=frame(presence_seconds=120)
    assert sync.due_reminder(item,result,preferences,100) is None
    result['evidence']['flags']['sedentary_due']=1
    assert sync.due_reminder(item,result,preferences,100)=='sit'


async def test_screen_sync_caches_device_preferences(monkeypatch):
    sent = []
    loads = []

    def fake_send(device, command, ack_type=None, **kwargs):
        sent.append(command)
        return 'ok', None, {'type': 'study_sync_ack', 'status': 'shown',
                            'voice': 'none', 'what': 'none'}

    def load_preferences(device):
        loads.append(True)
        return {'break_minutes': 60, 'break_enabled': True, 'posture_enabled': True}

    monkeypatch.setattr(state_sync, 'send_console', fake_send)
    device_voice.forget('dev-pref')
    sync = ScreenSync(load_preferences)
    result = frame(presence_seconds=3600)
    sync.observe('dev-pref', result, now=100)
    await asyncio.gather(*sync.tasks)
    assert sent[-1] == 'study_sync 1 00 0 0 60 1 60'
    sync.observe('dev-pref', result, now=104)
    await asyncio.gather(*sync.tasks)
    assert len(loads) == 1


async def test_direct_voice_scheduler_uses_server_trigger_and_display_command(monkeypatch):
    sent=[];played=[]
    def fake_send(device,command,ack_type=None,**kwargs):
        sent.append(command)
        return 'ok',None,{'type':'study_display_ack','status':'shown'}
    def fake_play(device,kind):
        played.append((device,kind))
        return 'played',None
    monkeypatch.setattr(state_sync,'send_console',fake_send)
    monkeypatch.setattr(state_sync,'play_local_voice',fake_play)
    sync=ScreenSync(lambda device:{'phone_trigger_seconds':1,
                                  'phone_interval_minutes':1},direct_voice=True)
    phone=frame('distracted_phone',presence_seconds=300)
    phone['evidence']['phone_held']=True
    sync.observe('dev-direct',phone,now=100)
    await asyncio.gather(*sync.tasks)
    assert sent==['study_display 8 01 0 5']
    sync.observe('dev-direct',phone,now=102)
    await asyncio.gather(*sync.tasks)
    assert played==[('dev-direct','phone')]
    assert 'phone' in sync.entry('dev-direct')['reminder_times']

def test_direct_voice_scheduler_uses_priority_order():
    sync=ScreenSync(direct_voice=True)
    item=sync.entry('dev-priority')
    phone=frame('distracted_phone',presence_seconds=300)
    phone['evidence']['phone_held']=True
    phone['torso_angle']=20
    preferences=dict(state_sync.DEFAULT_VOICE_PREFERENCES)
    preferences.update({'phone_trigger_seconds':1,'lying_trigger_seconds':1})
    assert sync.due_reminder(item,phone,preferences,100) is None
    assert sync.due_reminder(item,phone,preferences,102)=='phone'


async def test_direct_voice_failure_does_not_start_repeat_timer(monkeypatch):
    def fake_send(device,command,ack_type=None,**kwargs):
        return 'ok',None,{'type':'study_display_ack','status':'shown'}
    def fake_play(device,kind):
        return 'muted','小智当前静音'
    monkeypatch.setattr(state_sync,'send_console',fake_send)
    monkeypatch.setattr(state_sync,'play_local_voice',fake_play)
    sync=ScreenSync(lambda device:{'phone_trigger_seconds':1},direct_voice=True)
    phone=frame('distracted_phone',presence_seconds=300)
    phone['evidence']['phone_held']=True
    sync.observe('dev-muted',phone,now=100)
    await asyncio.gather(*sync.tasks)
    sync.observe('dev-muted',phone,now=102)
    await asyncio.gather(*sync.tasks)
    item=sync.entry('dev-muted')
    assert 'phone' not in item['reminder_times']
    assert item['voice']=='muted'
    assert item['voice_retry_at']>0


async def test_played_reminder_starts_its_interval(monkeypatch):
    def fake_send(device, command, ack_type=None, **kwargs):
        return 'ok', None, {'type': 'study_sync_ack', 'status': 'shown',
                            'voice': 'played', 'what': 'eye'}

    monkeypatch.setattr(state_sync, 'send_console', fake_send)
    device_voice.forget('dev-played')
    sync = ScreenSync(lambda device: {'eye_interval_minutes': 20})
    result = frame(presence_seconds=1300, near_work_seconds=1300,
                   flags={'eye_nearwork': 1})
    sync.observe('dev-played', result, now=100)
    await asyncio.gather(*sync.tasks)
    assert 'eye' in sync.entry('dev-played')['reminder_times']


async def test_screen_sync_dedups_and_renews_by_heartbeat(monkeypatch):
    sent = []

    def fake_send(device, command, ack_type=None, **kwargs):
        sent.append((device, command, ack_type))
        if kwargs.get('detail'):
            return 'ok', None, {'type': 'study_sync_ack', 'status': 'shown',
                                'voice': 'none', 'what': 'none'}
        return 'ok', None

    monkeypatch.setattr(state_sync, 'send_console', fake_send)
    device_voice.forget('dev-a')
    sync = ScreenSync()
    reading = frame(presence_seconds=725, near_work_seconds=480)

    sync.observe('dev-a', reading, now=100)
    await asyncio.gather(*sync.tasks)
    assert [item[1] for item in sent] == ['study_sync 1 00 8 0 12 1 45']
    # 固件认下这条命令后，语音提醒归固件播，服务端不再抢扬声器。
    assert device_voice.plays('dev-a') is True
    assert sync.snapshot('dev-a')['voice'] == 'none'
    assert sync.snapshot('dev-a')['mode'] == 'flags'

    # 行内容没变：心跳未到就不重复下发
    sync.observe('dev-a', reading, now=101)
    await asyncio.gather(*sync.tasks)
    assert len(sent) == 1

    # 心跳到期 → 续期一次，保证固件端不会淡出
    sync.observe('dev-a', reading, now=100 + state_sync.HEARTBEAT_SECONDS)
    await asyncio.gather(*sync.tasks)
    assert len(sent) == 2

    # 内容变化：立即下发（受最小间隔保护）
    phone = frame('distracted_phone', presence_seconds=300)
    sync.observe('dev-a', phone, now=200)
    await asyncio.gather(*sync.tasks)
    assert sent[-1][1] == 'study_sync 8 01 0 0 5 1 45'

    # 抖动抑制：同一秒内再变一次不重发
    sync.observe('dev-a', reading, now=201)
    await asyncio.gather(*sync.tasks)
    assert len(sent) == 3


async def test_old_firmware_falls_back_to_text_command(monkeypatch):
    sent = []

    def fake_send(device, command, ack_type=None, **kwargs):
        sent.append(command)
        if command.startswith('study_sync'):
            result = ('unavailable', '当前固件没有这条控制命令，需要先更新固件。')
            return result + ({},) if kwargs.get('detail') else result
        return 'ok', None

    monkeypatch.setattr(state_sync, 'send_console', fake_send)
    device_voice.forget('dev-old')
    sync = ScreenSync()
    reading = frame(presence_seconds=725, near_work_seconds=480)

    sync.observe('dev-old', reading, now=100)
    await asyncio.gather(*sync.tasks)
    assert sent[0] == 'study_sync 1 00 8 0 12 1 45'
    assert sent[1] == 'study_state 投入阅读 · 连续用眼 8 分'
    assert sync.snapshot('dev-old')['mode'] == 'text'
    assert device_voice.plays('dev-old') is False

    # 记住这台设备：下一轮直接用文本命令，不再白试一遍标志位。
    sync.observe('dev-old', reading, now=100 + state_sync.HEARTBEAT_SECONDS)
    await asyncio.gather(*sync.tasks)
    assert sent[-1].startswith('study_state ')
    # 刷了新固件不用重启服务端：过了重试间隔会自动再试一次标志位。
    sync.observe('dev-old', reading, now=100 + state_sync.HEARTBEAT_SECONDS + state_sync.REPROBE_SECONDS)
    await asyncio.gather(*sync.tasks)
    assert sent[-2].startswith('study_sync ')
    assert sent[-1].startswith('study_state ')


async def test_older_seven_argument_firmware_also_falls_back(monkeypatch):
    sent = []

    def fake_send(device, command, ack_type=None, **kwargs):
        sent.append(command)
        if command.startswith('study_sync'):
            return 'failed', '命令参数数量不兼容', {
                'type': 'study_sync_ack', 'status': 'error', 'reason': 'usage'}
        return 'ok', None

    monkeypatch.setattr(state_sync, 'send_console', fake_send)
    device_voice.forget('dev-seven')
    sync = ScreenSync()
    sync.observe('dev-seven', frame(presence_seconds=300), now=100)
    await asyncio.gather(*sync.tasks)
    assert sent[0].startswith('study_sync ')
    assert sent[1].startswith('study_state ')
    assert sync.snapshot('dev-seven')['mode'] == 'text'


async def test_device_isolation_and_failure_backoff(monkeypatch):
    sent = []

    def failing_send(device, command, ack_type=None, **kwargs):
        sent.append(device)
        error = '没有收到小智回执，请检查设备。'
        return ('failed', error, {}) if kwargs.get('detail') else ('failed', error)

    monkeypatch.setattr(state_sync, 'send_console', failing_send)
    device_voice.forget('dev-a')
    sync = ScreenSync()
    result = frame(presence_seconds=300)
    sync.observe('dev-a', result, now=100)
    await asyncio.gather(*sync.tasks)
    # 一次普通的失败不该改写设备能力：仍然是标志位模式，下一轮再试。
    assert sync.snapshot('dev-a')['mode'] == 'flags'
    assert sync.snapshot('dev-a')['status'] == 'failed'
    assert device_voice.plays('dev-a') is False

    # 失败后不立刻重发，等到心跳间隔才再试
    sync.observe('dev-a', result, now=101)
    await asyncio.gather(*sync.tasks)
    assert len(sent) == 1
    sync.observe('dev-a', result, now=100 + state_sync.HEARTBEAT_SECONDS)
    await asyncio.gather(*sync.tasks)
    assert len(sent) == 2

    # 另一台物理设备有自己的状态，不互相影响
    sync.observe('dev-b', result, now=200)
    await asyncio.gather(*sync.tasks)
    assert sent[-1] == 'dev-b'
    assert sync.snapshot('dev-b')['text'] == '投入阅读 · 在位 5 分'
