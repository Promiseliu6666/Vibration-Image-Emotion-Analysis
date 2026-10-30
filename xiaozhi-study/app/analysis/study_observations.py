"""Observable study cues; no identity, emotion, or medical inference."""
import cv2
import numpy as np

FOCUS_STATES = {'engaged_computer','engaged_reading','engaged_writing','engaged_screen','engaged_hand_raising','engaged_discussing'}

def observe(frame, pose, face, present, gaze, now, state, learning_state):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = float(gray.mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    quality = 'dark' if mean < 35 else 'overexposed' if mean > 230 else 'soft' if sharpness < 20 else 'clear'
    previous = state.get('observation_time')
    if previous is not None and now <= previous and state.get('last_health_observation'):
        return dict(state['last_health_observation'])
    gap = now - previous if previous is not None else 0
    if gap < 0 or gap > 6:
        for key in ('focus_seconds', 'presence_seconds', 'near_work_seconds', 'screen_seconds'):
            state[key] = 0
        state['observation_present'] = False
        state['posture_run'] = 0
        state['near_work_off_since'] = None
        state['screen_off_since'] = None
        gap = 0
    if present and state.get('observation_present'):
        state['presence_seconds'] = state.get('presence_seconds',0)+gap
    else:
        state['presence_seconds'] = 0
        state['presence_started_at'] = now if present else None
    state['observation_present'] = present
    # 连续投入仍来自状态分类，只作参考：分类要过连续确认，长期可能停在"活动未确认"。
    focused = present and learning_state in FOCUS_STATES
    if focused and state.get('observation_focused'):
        state['focus_seconds'] = state.get('focus_seconds',0) + gap
    elif not focused:
        state['focus_seconds'] = 0
    state['observation_time'] = now
    state['observation_focused'] = focused

    # ---- 用眼负荷：刻意不依赖 learning_state ----
    # 若把用眼时长挂在分类结果上，一旦分类停在"活动未确认"，累积量会长期为 0。
    # 这里只依赖三个独立条件：画面可用 + 有人脸 + 视线朝向。
    face_ready = bool(present and quality not in {'dark', 'overexposed'} and sharpness >= 8
                      and getattr(face, 'multi_face_landmarks', None))
    near_work = bool(face_ready and gaze in ('down', 'screen'))   # 近距离用眼：看书 / 写字 / 看屏幕
    screen = bool(face_ready and gaze == 'screen')                # 屏幕暴露是近距离用眼的子集

    def _run(key, active, off_key):
        """连续累积：短暂离开 20 秒内不清零，超过则从头计；断流或无人立即清零。"""
        if gap <= 0 or not present:
            state[key] = 0
            state[off_key] = None
        if active:
            if gap > 0 and state.get(key + '_previous'):
                state[key] = state.get(key, 0) + gap
            state[off_key] = None
        else:
            if state.get(off_key) is None:
                state[off_key] = now
            if now - state[off_key] >= 20:
                state[key] = 0
        state[key + '_previous'] = active

    _run('near_work_seconds', near_work, 'near_work_off_since')
    _run('screen_seconds', screen, 'screen_off_since')

    # ---- 久坐与姿态 ----
    # 门槛放宽：原来要求关键点可见度 ≥ .75 且清晰度 ≥ 8，实测只有约 4% 的样本可评估。
    # 现在放宽到 .6 / 5，并把"为什么不可评估"记下来，供界面提示取景问题。
    tilted = False
    assessable = False
    shoulder_slope = None
    posture_reason = None
    landmarks = getattr(pose,'pose_landmarks',None)
    if not present:
        posture_reason = 'no_person'
    elif quality == 'dark':
        posture_reason = 'too_dark'
    elif quality == 'overexposed':
        posture_reason = 'too_bright'
    elif sharpness < 5:
        posture_reason = 'too_blurry'
    elif not landmarks:
        posture_reason = 'no_pose'
    if present and landmarks:
        lm = landmarks.landmark
        keypoints_ok = all(lm[i].visibility >= .6 for i in (11,12,23,24))
        in_frame = all(.03 < lm[i].x < .97 and .03 < lm[i].y < .97 for i in (11,12,23,24))
        if keypoints_ok:
            shoulder_width = abs(lm[11].x-lm[12].x)
            assessable = bool(quality not in {'dark','overexposed'} and sharpness >= 5
                              and shoulder_width > .08 and in_frame)
            if assessable:
                shoulder_slope = (lm[11].y-lm[12].y) / shoulder_width
                tilted = abs(shoulder_slope) > .35
                posture_reason = None
            elif posture_reason is None:
                posture_reason = 'too_far' if shoulder_width <= .08 else 'out_of_frame'
        elif posture_reason is None:
            posture_reason = 'keypoints_hidden'   # 肩或髋被遮挡，或不在画面里
    if tilted:
        if not state.get('posture_run'):state['posture_since'] = now
        state['posture_run'] = state.get('posture_run',0)+1
    else:
        state['posture_run'] = 0
    posture = tilted and state['posture_run'] >= 3 and now-state.get('posture_since',now) >= 4
    seconds = round(state.get('focus_seconds',0))
    near_seconds = round(state.get('near_work_seconds',0))
    observation = {'presence_started_at':state.get('presence_started_at'),'presence_seconds':round(state.get('presence_seconds',0)),'quality':quality,'sharpness':round(sharpness,1),'posture_tilt':bool(posture),
            'posture_reason':posture_reason,
            # 只要脸清晰可见就算"可评估"，不再要求状态已确认
            'eye_assessable':face_ready,
            'screen_activity':screen,'screen_seconds':round(state.get('screen_seconds',0)),
            # 近距离用眼（看书 / 写字 / 看屏幕）——用眼负荷的主指标
            'near_work_activity':near_work,'near_work_seconds':near_seconds,
            'posture_assessable':assessable,'shoulder_slope':shoulder_slope,'focus_seconds':seconds,
            # 45 分钟休息提示改为按"连续近距离用眼"计，不再按分类派生的 focus_seconds
            'break_due':bool(near_work and near_seconds >= 45*60),
            'face_visible':bool(getattr(face,'multi_face_landmarks',None))}

    state['last_health_observation'] = dict(observation)
    return observation
