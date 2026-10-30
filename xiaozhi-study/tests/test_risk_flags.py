from app.analysis.risk_flags import FLAGS, RISK_KEYS, THRESHOLDS, evaluate


def base(**kw):
    args = dict(observations={}, learning_state='thinking', fatigue_level=0.0,
                fatigue_calibrated=True, phone_held=False, phone_available=True,
                torso_angle=90.0, gaze_away_seconds=0.0, vibra=None)
    args.update(kw)
    return evaluate(**args)


def test_lying_and_phone_hits_several_groups():
    """趴着玩手机：用眼 + 体态 + 注意力 应同时命中（标志位允许重叠）。"""
    f = base(observations={'near_work_seconds': 1500, 'posture_assessable': True, 'posture_tilt': True},
             phone_held=True, torso_angle=20.0, gaze_away_seconds=0.0)
    assert f['eye_nearwork'] == 1
    assert f['posture_tilt'] == 1
    assert f['posture_lying'] == 1
    assert f['attention_phone'] == 1
    assert sum(1 for k in RISK_KEYS if f[k] == 1) >= 4


def test_unknown_is_none_not_zero():
    """测不出来必须是 None：写成 0 会被读成"没问题"，比漏报更危险。"""
    f = base(observations={'posture_assessable': False, 'quality': 'dark', 'sharpness': 3.0},
             phone_available=False, vibra={})
    assert f['posture_tilt'] is None
    assert f['posture_lying'] is None or f['posture_lying'] == 0
    assert f['attention_phone'] is None
    assert f['mood_stress'] is None and f['mood_low_stability'] is None
    assert f['quality_poor'] == 1


def test_mood_requires_real_output():
    """vibraimage 未真正产出时（happiness_level 为空），不能按 0 值判定。"""
    fake = {'e2': 0.0, 'e3': 0.0, 'e14': 0.0, 'happiness_index': 0.0, 'happiness_level': ''}
    f = base(vibra=fake)
    assert f['mood_stress'] is None
    assert f['mood_low_stability'] is None
    assert f['mood_low_happiness'] is None


def test_face_motion_never_establishes_mental_health_risk():
    real = {'e2': 60.0, 'e3': 50.0, 'e14': 40.0, 'happiness_index': 10.0, 'happiness_level': '低'}
    f = base(vibra=real)
    assert f['mood_stress'] is None
    assert f['mood_tension'] is None
    assert f['mood_low_stability'] is None
    assert f['mood_low_happiness'] is None


def test_fatigue_needs_calibration():
    assert base(fatigue_level=0.9, fatigue_calibrated=False)['eye_fatigue'] is None
    assert base(fatigue_level=0.9, fatigue_calibrated=True)['eye_fatigue'] == 1
    assert base(fatigue_level=0.2, fatigue_calibrated=True)['eye_fatigue'] == 0


def test_sedentary_flag_follows_device_threshold():
    from app.analysis.risk_flags import apply_sedentary_due
    result={'person_present':True,'evidence':{'observations':{'presence_seconds':119},'flags':{}}}
    assert apply_sedentary_due(result,2)==0
    result['evidence']['observations']['presence_seconds']=120
    assert apply_sedentary_due(result,2)==1
    assert 'sedentary_due' in RISK_KEYS


def test_quality_is_not_a_health_risk():
    assert 'quality_poor' not in RISK_KEYS
    assert any(f['key'] == 'quality_poor' and f['group'] == 'quality' for f in FLAGS)
    assert base(observations={'quality': 'clear', 'sharpness': 50,
                              'posture_reason': 'too_far'})['quality_poor'] == 1


def test_declared_scope():
    """阈值必须有注释可查：每个标志位都要能在 FLAGS 里找到口径说明。"""
    for f in FLAGS:
        assert f.get('scope'), f['key']
        assert f.get('group') in ('eye', 'posture', 'attention', 'sedentary', 'mood', 'quality')
    assert THRESHOLDS['near_work_seconds'] == 1200
    assert THRESHOLDS['gaze_away_seconds'] == 60
