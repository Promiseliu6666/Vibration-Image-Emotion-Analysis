"""风险标志位：每个样本按测量值判定，三态取值。

    1   = 命中（值得复核）
    0   = 未命中
    None= 无法判定（该维度这次没测出来）——必须与 0 区分，否则"测不到"会被误读成"没问题"

设计要点
--------
* 每个标志位只依赖**独立测量值**，不依赖行为分类结果（分类要过连续确认，长期可能停在"活动未确认"）。
* 同一状态可以同时命中多个标志位（趴着玩手机 = 用眼 + 体态 + 注意力），**允许重叠**。
* 阈值来源：2026-10-11~13 本机实测分布（有效心理样本 7326 条）。取约 P90 / P10，
  即"明显偏离近期常态"的那一档，使每个标志位大约只筛出 5%~10% 的样本。
  **属于初版固定阈值，待个人基线化后替换**（见 docs/需求文档-健康赛道.md 的 FR-4/FR-5）。
* 数据质量不合格单独成组（group='quality'），不计入健康风险。

本文件是标志位的唯一事实来源；前端对应 static/health-dimensions.js 的 HEALTH_FLAGS。
"""

FLAGS_VERSION = 2

# 阈值集中在这里，便于统一调整与写文档
THRESHOLDS = {
    'near_work_seconds': 20 * 60,   # 连续近距离用眼 20 分钟
    'fatigue_level': 0.6,           # 疲劳指标
    'gaze_away_seconds': 60,        # 视线离开持续 60 秒才语音提醒
    'torso_lying_angle': 25,        # 躯干与竖直方向夹角小于 25° 视为趴桌
    'stress_high': 35,              # e2 压力偏高（实测命中约 8%）
    'tension_high': 45,             # e3 紧张偏高（约 5%）
    'stability_low': 60,            # e14 稳定性偏低（约 10%）
    'happiness_low': 20,            # 幸福指数偏低（约 10%）
    'sharpness_min': 5,             # 清晰度下限
}

# group: eye / posture / attention / mood / quality
FLAGS = [
    {'key': 'eye_nearwork',       'label': '用眼·连续近距离用眼', 'group': 'eye',
     'scope': '连续近距离用眼（看书/写字/看屏幕）达到 20 分钟'},
    {'key': 'eye_fatigue',        'label': '用眼·疲劳',           'group': 'eye',
     'scope': '疲劳指标 ≥ 0.6，且已完成个人基线标定'},
    {'key': 'posture_tilt',       'label': '体态·坐姿倾斜',       'group': 'posture',
     'scope': '肩部持续倾斜（连续 3 帧且持续 4 秒）'},
    {'key': 'posture_lying',      'label': '体态·趴桌',           'group': 'posture',
     'scope': '躯干与竖直方向夹角小于 25°'},
    {'key': 'attention_phone',    'label': '注意力·使用手机',     'group': 'attention',
     'scope': '检测到手机实物且与可见手部位置对应'},
    {'key': 'attention_away',     'label': '注意力·视线离开',     'group': 'attention',
     'scope': '视线离开学习区持续 60 秒以上'},
    {'key': 'sedentary_due',      'label': '久坐·连续在位过久',   'group': 'sedentary',
     'scope': '连续在位时间达到当前设备的久坐提醒阈值'},
    {'key': 'mood_stress',        'label': '情绪·压力偏高',       'group': 'mood',
     'scope': '振动图像压力 e2 ≥ 35（初版固定阈值）'},
    {'key': 'mood_tension',       'label': '情绪·紧张偏高',       'group': 'mood',
     'scope': '振动图像紧张 e3 ≥ 45（初版固定阈值）'},
    {'key': 'mood_low_stability', 'label': '情绪·稳定性偏低',     'group': 'mood',
     'scope': '振动图像稳定性 e14 ≤ 60（初版固定阈值）'},
    {'key': 'mood_low_happiness', 'label': '情绪·幸福指数偏低',   'group': 'mood',
     'scope': '幸福指数 ≤ 20（初版固定阈值）'},
    {'key': 'quality_poor',       'label': '数据质量·画面不合格', 'group': 'quality',
     'scope': '光线过暗/过亮、画面发虚或人离镜头太远，本次测量不可信'},
]

# 参与"复合风险"统计的标志位：数据质量不算健康风险
RISK_KEYS = [f['key'] for f in FLAGS if f['group'] not in ('quality','mood')]


def _tristate(hit, available):
    """可用则给出 0/1，不可用给出 None（"无法判定"）。"""
    if not available:
        return None
    return 1 if hit else 0


def evaluate(*, observations, learning_state, fatigue_level, fatigue_calibrated,
             phone_held, phone_available, torso_angle, gaze_away_seconds, vibra,
             sedentary_seconds=None, sedentary_threshold_seconds=None):
    """按测量值判定全部标志位，返回 {标志位: 1|0|None}。

    vibra 为该帧的振动图像结果字典；没有真正产出时必须传空值，
    否则那批"全零"读数会被当成"压力 0 / 稳定性 0"而制造假风险。
    """
    o = observations or {}
    t = THRESHOLDS

    near = o.get('near_work_seconds')
    eye_nearwork = _tristate(near is not None and float(near) >= t['near_work_seconds'], near is not None)

    eye_fatigue = _tristate(fatigue_level is not None and float(fatigue_level) >= t['fatigue_level'],
                            bool(fatigue_calibrated) and fatigue_level is not None)

    posture_ok = bool(o.get('posture_assessable'))
    posture_tilt = _tristate(bool(o.get('posture_tilt')), posture_ok)
    has_angle = torso_angle is not None and learning_state != 'absent'
    posture_lying = _tristate(has_angle and float(torso_angle) < t['torso_lying_angle'], has_angle)

    attention_phone = _tristate(bool(phone_held), bool(phone_available))
    attention_away = _tristate(gaze_away_seconds is not None and float(gaze_away_seconds) >= t['gaze_away_seconds'],
                               gaze_away_seconds is not None)

    # Facial motion alone does not establish a person's mental state.
    # Keep legacy field names as unknown for backward-compatible records.
    def mood(*args):
        return None

    quality_poor = 1 if (o.get('quality') in ('dark', 'overexposed')
                         or o.get('posture_reason') == 'too_far'
                         or (o.get('sharpness') is not None and float(o['sharpness']) < t['sharpness_min'])) else 0
    sedentary_due = _tristate(
        sedentary_seconds is not None and sedentary_threshold_seconds is not None
        and float(sedentary_seconds) >= float(sedentary_threshold_seconds),
        sedentary_seconds is not None and sedentary_threshold_seconds is not None)

    return {
        'eye_nearwork': eye_nearwork,
        'eye_fatigue': eye_fatigue,
        'posture_tilt': posture_tilt,
        'posture_lying': posture_lying,
        'attention_phone': attention_phone,
        'attention_away': attention_away,
        'sedentary_due': sedentary_due,
        'mood_stress': mood('e2', lambda v: v >= t['stress_high']),
        'mood_tension': mood('e3', lambda v: v >= t['tension_high']),
        'mood_low_stability': mood('e14', lambda v: v <= t['stability_low']),
        'mood_low_happiness': mood('happiness_index', lambda v: v <= t['happiness_low']),
        'quality_poor': quality_poor,
    }


def apply_sedentary_due(result, break_minutes):
    """Apply the current device's sedentary threshold before the sample is stored."""
    evidence = result.get('evidence') or {}
    observations = evidence.get('observations') or {}
    flags = evidence.setdefault('flags',{})
    try:
        threshold = max(0,int(break_minutes)) * 60
    except (TypeError,ValueError):
        threshold = 0
    presence = observations.get('presence_seconds')
    flags['sedentary_due'] = _tristate(
        presence is not None and threshold > 0 and float(presence) >= threshold,
        bool(result.get('person_present')) and presence is not None and threshold > 0)
    evidence['flags_version'] = FLAGS_VERSION
    return flags['sedentary_due']


def summarize(counts):
    """把 {标志位: 命中数} 与 {标志位: 无法判定数} 组装成界面用的列表。"""
    out = []
    for f in FLAGS:
        if f['group']=='mood':continue
        c = counts.get(f['key']) or {}
        out.append({**f, 'hits': int(c.get('hits') or 0), 'unknown': int(c.get('unknown') or 0)})
    return out
