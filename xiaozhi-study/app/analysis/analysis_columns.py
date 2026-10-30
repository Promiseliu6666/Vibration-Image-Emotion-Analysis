"""analysis_results 表的列语义（单一事实来源）。

三个使用方都引用这里，避免注释在多处各写一份后漂移：
  1. app/analysis/analysis_schema.py —— 启动时把注释同步到数据库（Navicat 可见）
  2. app/core/models.py              —— SQLAlchemy 建表时带上注释
  3. .runtime/schema.json            —— 新安装首次建库时直接带上注释

口径提醒：e1–e14 与幸福指数来自振动图像（Vibraimage）心理生理方法，
属于非接触代理指标，只用于趋势观察；本表不产生任何医学诊断结论。
"""

# 列名 -> (完整列定义, 注释)
COLUMN_DDL = {
    'id':                   ('int NOT NULL AUTO_INCREMENT', '主键，自增'),
    'session_id':           ('int NOT NULL', '所属学习时段 ID，关联 sessions.id'),
    'timestamp':            ('datetime DEFAULT NULL', '分析时间（UTC，无时区）；北京时间需 +8 小时'),
    'fatigue_level':        ('float DEFAULT NULL', '疲劳指标 0–1：EAR 偏离 / 60 秒 PERCLOS / MAR 哈欠频率 / 点头与眨眼，以个人基线加权；个人基线未标定时不产出'),
    'distraction_level':    ('float DEFAULT NULL', '分心指标 0–1：由当前状态与视线历史导出'),
    'gaze_direction':       ('varchar(16) DEFAULT NULL', '视线方向：screen（朝学习区）/ down（低头）/ away（离开）/ up（抬头）等'),
    'action_state':         ('varchar(16) DEFAULT NULL', '动作原始判定：reading / writing / listening / turning_around / standing / playing_phone / lying_down / idle'),
    'difficulty_indicator': ('float DEFAULT NULL', '困难度 0–1：60 秒滑窗七维加权（挣扎占比 0.25 / 状态波动 0.20 / 疲劳漂移 0.18 / 空白凝视 0.13 / 姿态坍塌 0.09 / 身体躁动 0.08 / 说话占比 0.07）'),
    'learning_state':       ('varchar(32) DEFAULT NULL', '状态码（13 类）：engaged_reading 阅读 / engaged_writing 书写 / engaged_screen 听讲 / engaged_computer 电脑操作 / engaged_hand_raising 举手 / engaged_discussing 讨论 / standing 站立 / distracted_phone 使用手机 / distracted_away 视线离开 / resting 休息 / fatigued 疲劳迹象 / thinking 活动未确认 / absent 无人'),
    'raw_frame_path':       ('varchar(256) DEFAULT NULL', '关联图片路径；为空表示该条未留档'),
    'person_present':       ('int DEFAULT NULL', '画面是否有人：1 有 / 0 无'),
    'e1_aggression':        ('float DEFAULT NULL', '振动图像参数 e1 攻击性（0–100，相对值，仅作趋势）'),
    'e2_stress':            ('float DEFAULT NULL', '振动图像参数 e2 压力（0–100，相对值，仅作趋势）'),
    'e3_tension':           ('float DEFAULT NULL', '振动图像参数 e3 紧张（0–100，相对值，仅作趋势）'),
    'e4_suspiciousness':    ('float DEFAULT NULL', '振动图像参数 e4 疑虑（0–100，相对值，仅作趋势）'),
    'e5_balance':           ('float DEFAULT NULL', '振动图像参数 e5 平衡（0–100，相对值，仅作趋势）'),
    'e6_charm':             ('float DEFAULT NULL', '振动图像参数 e6 魅力（0–100，相对值，仅作趋势）'),
    'e7_energy':            ('float DEFAULT NULL', '振动图像参数 e7 活力（0–100，相对值，仅作趋势）'),
    'e8_self_regulation':   ('float DEFAULT NULL', '振动图像参数 e8 自我调节（0–100，相对值，仅作趋势）'),
    'e9_inhibition':        ('float DEFAULT NULL', '振动图像参数 e9 抑制力（0–100，相对值，仅作趋势）'),
    'e10_neuroticism':      ('float DEFAULT NULL', '振动图像参数 e10 神经质（0–100，相对值，仅作趋势）'),
    'e11_gloominess':       ('float DEFAULT NULL', '振动图像参数 e11 忧郁（0–100，相对值，仅作趋势）'),
    'e12_happiness':        ('float DEFAULT NULL', '振动图像参数 e12 幸福指数（0–100，与 happiness_index 同源）'),
    'e13_extraversion':     ('float DEFAULT NULL', '振动图像参数 e13 外向性（0–100，相对值，仅作趋势）'),
    'e14_stability':        ('float DEFAULT NULL', '振动图像参数 e14 稳定性（0–100，相对值，仅作趋势）'),
    'happiness_index':      ('float DEFAULT NULL', '幸福指数（等同 e12，便于查询）：≥80 高 / ≥60 中 / 其余低'),
    'happiness_level':      ('varchar(8) DEFAULT NULL', '幸福指数分级：高 / 中 / 低'),
    'safety_risk':          ('varchar(16) DEFAULT NULL', '由幸福指数派生的风险分级：低风险 / 中风险 / 高风险；仅为内部趋势参考，界面不展示，不作诊断'),
    'evidence_json':        ('longtext', '证据 JSON（observations 等字段）：识别原因 recognition_reason、连续证据 window、取景质量 quality/sharpness；用眼度量 near_work_seconds 近距离用眼 / screen_seconds 屏幕暴露（均不依赖状态分类）；在位 presence_seconds；姿态 posture_tilt / posture_assessable / posture_reason 不可评估原因；手机与书本证据'),
    'risk_flags':           ('varchar(200) DEFAULT NULL', '本样本命中的风险标志位键，逗号分隔（如 attention_phone,posture_tilt）；空串表示无命中。标志位允许重叠，定义与阈值见 app/analysis/risk_flags.py'),
    'risk_unknown':         ('varchar(200) DEFAULT NULL', '本样本【无法判定】的风险标志位键，逗号分隔。这些维度本次没测出来，不能当作"没问题"，界面需与 0 区分显示'),
    'risk_hit_count':       ('tinyint DEFAULT NULL', '本样本命中的风险标志位个数（不含数据质量组）；≥2 表示复合风险，例如趴着玩手机同时命中用眼/体态/注意力'),
    'flags_version':        ('tinyint DEFAULT NULL', '判定本行时所用的风险规则版本；阈值调整后可按版本分批重算历史'),
    'near_work_seconds':    ('int DEFAULT NULL', '连续近距离用眼秒数（看书/写字/看屏幕）。只依赖视线与画面可用性，不依赖状态分类；短暂离开 20 秒内不清零'),
    'screen_seconds':       ('int DEFAULT NULL', '连续屏幕暴露秒数（视线朝屏幕），是近距离用眼的子集'),
    'presence_seconds':     ('int DEFAULT NULL', '连续在位秒数：画面中持续有人的时长。注意这是在位，不等于久坐时长'),
    'posture_assessable':   ('tinyint DEFAULT NULL', '本帧姿态是否可评估：1 可 / 0 否。要求肩、髋四个关键点可见度 ≥0.6 且清晰度 ≥5'),
    'posture_tilt':         ('tinyint DEFAULT NULL', '坐姿倾斜：1 是 / 0 否。肩部持续倾斜（连续 3 帧且持续 4 秒）才判定为是'),
    'posture_reason':       ('varchar(32) DEFAULT NULL', '姿态不可评估的原因：no_person/too_dark/too_bright/too_blurry/no_pose/keypoints_hidden/out_of_frame/too_far；用于提示取景问题'),
    'eye_assessable':       ('tinyint DEFAULT NULL', '人脸是否可评估：1 可 / 0 否。只要脸清晰可见（非过暗过亮、清晰度达标）即为 1，不要求状态已确认'),
}


def col_comment(name):
    """取某列的注释，供 SQLAlchemy Column(comment=...) 使用。"""
    return COLUMN_DDL[name][1]
