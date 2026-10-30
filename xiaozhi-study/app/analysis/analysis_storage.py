"""Learning session persistence, retained event images and ordinary image expiration.

Commit records before any runtime alert is published. Keep inference independent of storage.
"""
import os
import time as _time
from datetime import datetime, timezone
from app.core.db import get_connection

_absence_state = {}  # device_id -> {'absence_start': datetime, 'session_ended': bool}


def write_result(device_id, result, filepath):
    from app.device import device_registry
    with device_registry.lock:
        if device_registry.blocked(device_id):
            if filepath:
                try: os.remove(filepath)
                except OSError: pass
            return
        return write_result_unlocked(device_id, result, filepath)

def write_result_unlocked(device_id, result, filepath):
    from app.core.config import SESSION_MAX_MINUTES, ABSENCE_GRACE_S, SAVE_ALL_FRAMES, FRAME_SAVE_DIR
    conn = get_connection()
    try:
        now = datetime.fromtimestamp(result.get('captured_at',_time.time()),tz=timezone.utc).replace(tzinfo=None)  # Capture time, UTC
        person_present = result.get("person_present", True)

        with conn.cursor() as cur:
            # ---- 查询当前活跃 session ----
            cur.execute(
                "SELECT id, start_time FROM sessions WHERE device_id=%s AND status='active'",
                (device_id,)
            )
            row = cur.fetchone()

            # ---- 缺席状态管理 ----
            # SSCMA辅助：若 MediaPipe 未检测到人但 SSCMA 检测到，延长宽限期
            sscma_person_score = result.get("sscma_person_score", 0)
            effective_grace = ABSENCE_GRACE_S
            if not person_present and sscma_person_score > 85:
                effective_grace = ABSENCE_GRACE_S * 2  # 30s when SSCMA still sees person

            if not person_present:
                if device_id not in _absence_state:
                    _absence_state[device_id] = {'absence_start': now, 'session_ended': False}
                absence_info = _absence_state[device_id]

                if not absence_info['session_ended']:
                    absence_sec = (now - absence_info['absence_start']).total_seconds()
                    if absence_sec > effective_grace:
                        # 超过宽限期：关闭当前 session
                        if row is not None:
                            cur.execute(
                                "UPDATE sessions SET status='ended', end_time=%s WHERE id=%s",
                                (absence_info['absence_start'], row["id"])
                            )
                            conn.commit()
                        absence_info['session_ended'] = True

                # 当前 session 已因缺席关闭，无人帧不再写入
                if absence_info['session_ended']:
                    if filepath:
                        try: os.remove(filepath)
                        except OSError: pass
                    return
            else:
                # 人回来了，清除缺席状态
                if device_id in _absence_state:
                    del _absence_state[device_id]

            # Do not create a learning record from empty-room startup frames.
            if row is None and not person_present:
                if filepath:
                    try: os.remove(filepath)
                    except OSError: pass
                return

            # ---- 获取或创建活跃 session ----
            if row is None:
                cur.execute(
                    "INSERT INTO sessions (device_id,status,start_time) VALUES (%s,'active',%s)",
                    (device_id, now)
                )
                conn.commit()
                sid = cur.lastrowid
            else:
                sid = row["id"]
                start = row["start_time"]
                # start和now都是naive UTC，直接比较
                if (now - start).total_seconds() > SESSION_MAX_MINUTES * 60:
                    cur.execute(
                        "UPDATE sessions SET status='ended', end_time=%s WHERE id=%s",
                        (now, sid)
                    )
                    cur.execute("INSERT INTO sessions (device_id,status,start_time) VALUES (%s,'active',%s)", (device_id, now))
                    conn.commit()
                    sid = cur.lastrowid

            # ---- 隐私：非告警帧不存图 ----
            alert_states = {"distracted_phone", "distracted_away", "fatigued", "resting"}
            is_alert = (
                result["fatigue_level"] > 0.5 or
                result["distraction_level"] > 0.5 or
                result["difficulty_indicator"] > 0.5 or
                result.get("learning_state", "") in alert_states
            )
            stored_path = filepath
            if is_alert and filepath:
                from app.analysis.alert_archive import protect
                stored_path = protect(filepath, FRAME_SAVE_DIR)
                if not stored_path:
                    raise RuntimeError("事件原图不存在，截图未保存")
            if not SAVE_ALL_FRAMES and not is_alert and filepath:
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                stored_path = ""

            # ---- 写入分析结果 ----
            vib = result.get("vibraimage") or {}
            # 风险标志位落列：查询时不必再解析 JSON
            # （原实现每次聚合要对每行做 22 次 JSON 解析，接口要 5 秒以上）
            from app.analysis.risk_flags import RISK_KEYS as _RISK_KEYS
            _flags = (result.get("evidence") or {}).get("flags") or {}
            _obs = (result.get("evidence") or {}).get("observations") or {}
            _risk_flags = ",".join(k for k, v in _flags.items() if v == 1 and k in _RISK_KEYS)
            _risk_unknown = ",".join(k for k, v in _flags.items() if v is None)
            _risk_hit_count = len(_risk_flags.split(",")) if _risk_flags else 0
            _flags_version = int((result.get("evidence") or {}).get("flags_version") or 0)
            cur.execute(
                """INSERT INTO analysis_results
                (session_id,timestamp,fatigue_level,distraction_level,
                 gaze_direction,action_state,learning_state,difficulty_indicator,raw_frame_path,person_present,
                 e1_aggression,e2_stress,e3_tension,e4_suspiciousness,e5_balance,
                 e6_charm,e7_energy,e8_self_regulation,e9_inhibition,e10_neuroticism,
                 e11_gloominess,e12_happiness,e13_extraversion,e14_stability,
                 happiness_index,happiness_level,safety_risk,evidence_json,risk_flags,risk_unknown,risk_hit_count,flags_version,
                 near_work_seconds,screen_seconds,presence_seconds,posture_assessable,posture_tilt,posture_reason,eye_assessable)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (sid, now,
                 result["fatigue_level"], result["distraction_level"],
                 result["gaze_direction"], result["action_state"],
                 result.get("learning_state", ""),
                 result["difficulty_indicator"], stored_path,
                 int(person_present),
                 vib.get("e1", 0), vib.get("e2", 0), vib.get("e3", 0),
                 vib.get("e4", 0), vib.get("e5", 0), vib.get("e6", 0),
                 vib.get("e7", 0), vib.get("e8", 0), vib.get("e9", 0),
                 vib.get("e10", 0), vib.get("e11", 0), vib.get("e12", 0),
                 vib.get("e13", 0), vib.get("e14", 0),
                 vib.get("happiness_index", 0),
                 vib.get("happiness_level", ""),
                 vib.get("safety_risk", ""), __import__("json").dumps(result.get("evidence",{}),ensure_ascii=False),_risk_flags,_risk_unknown,_risk_hit_count,_flags_version,int(_obs.get("near_work_seconds") or 0),int(_obs.get("screen_seconds") or 0),int(_obs.get("presence_seconds") or 0),1 if _obs.get("posture_assessable") else 0,1 if _obs.get("posture_tilt") else 0,(_obs.get("posture_reason") or ""),1 if _obs.get("eye_assessable") else 0))
            record_id = cur.lastrowid
            conn.commit()
            return {'session_id':sid,'result_id':record_id,'frame_path':stored_path,'image_preserved':is_alert and bool(stored_path)}
    finally:
        conn.close()


def cleanup_expired_frames():
    """清理超过保留期的帧图片和数据库记录"""
    from app.core.config import FRAME_SAVE_DIR, FRAME_RETENTION_DAYS
    import time
    cutoff = time.time() - FRAME_RETENTION_DAYS * 86400
    deleted_files = 0
    deleted_rows = 0

    # 1. 清理帧文件目录中的旧文件
    if os.path.isdir(FRAME_SAVE_DIR):
        for root, dirs, files in os.walk(FRAME_SAVE_DIR, topdown=True):
            # alerts：提醒截图；feedback：识别纠正图。两者都是少量、有价值的标注，长期保留。
            # 注意要在每一层都剪掉：纠正图的实际路径是 frames/<日期>/feedback/<账号>/xx.jpg。
            dirs[:] = [d for d in dirs if d not in ('alerts', 'feedback')]
            for name in files:
                fpath = os.path.join(root, name)
                try:
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
                        deleted_files += 1
                except OSError:
                    pass
            # 删除空目录
            for name in dirs:
                dpath = os.path.join(root, name)
                try:
                    os.rmdir(dpath)
                except OSError:
                    pass

    # 2. 清理数据库中旧记录的 raw_frame_path（文件已删除，避免前端显示无效路径）
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
            cur.execute(
                "UPDATE analysis_results SET raw_frame_path='' WHERE timestamp < %s AND raw_frame_path != '' AND REPLACE(raw_frame_path,CHAR(92),'/') NOT LIKE %s",
                (cutoff_dt, '%/alerts/%')
            )
            deleted_rows = cur.rowcount
            conn.commit()
    finally:
        conn.close()

    if deleted_files or deleted_rows:
        print(f"[Cleanup] 清理完成: 删除 {deleted_files} 个旧文件, 更新 {deleted_rows} 条数据库记录")
    return deleted_files, deleted_rows
