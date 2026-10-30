"""REST API：登录、设备管理、时段查询、实时数据"""
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
import os
import asyncio
from app.core import access_control
import random
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Query as FastAPIQuery
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from app.core.db import get_connection
from app.core.config import (
    FRAME_SAVE_DIR
)

router = APIRouter(prefix="/api")
security = HTTPBearer()
security_loose = HTTPBearer(auto_error=False)

# MySQL DATETIME 不保存时区，pymysql 返回的是 naive datetime，
# 但实际存的是 UTC 时间，需要补上时区标识给前端 JS 正确解析
def _iso(ts):
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat()


def _behavior_points(rows, limit=150):
    """Keep endpoints and one observation of each state before uniform sampling."""
    if len(rows) <= limit:
        return rows
    selected = {0, len(rows)-1}
    seen = set()
    for index, row in enumerate(rows):
        key = (bool(row.get("person_present", 1)), row.get("learning_state"))
        if key not in seen and len(selected) < limit:
            seen.add(key)
            selected.add(index)
    remaining = limit - len(selected)
    if remaining:
        candidates = [i for i in range(len(rows)) if i not in selected]
        selected.update(candidates[round(i*(len(candidates)-1)/max(1, remaining-1))] for i in range(remaining))
    return [rows[i] for i in sorted(selected)]


# --- 认证 ---

@router.post("/login")
async def login(body: dict, request: Request):
    username,password=body.get("username",""),body.get("password","")
    if not isinstance(username,str) or not isinstance(password,str):
        raise HTTPException(400,"请输入用户名和密码")
    return await asyncio.to_thread(access_control.login,username,password,request.client.host if request.client else "unknown")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return await asyncio.to_thread(access_control.decode,credentials.credentials)

async def get_current_user_loose(credentials: HTTPAuthorizationCredentials = Depends(security_loose),token: str = FastAPIQuery(None)):
    raw=credentials.credentials if credentials else token
    if not raw:raise HTTPException(401,"缺少认证令牌")
    return await asyncio.to_thread(access_control.decode,raw)

async def require_admin(username: str = Depends(get_current_user)):
    await asyncio.to_thread(access_control.admin,username)
    return username


# --- 设备管理 ---

@router.get("/devices")
def list_devices(user: str = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, device_id, name, created_at FROM devices ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [{"id": r["id"], "device_id": r["device_id"], "name": r["name"],
                 "created_at": _iso(r["created_at"])} for r in rows]
    finally:
        conn.close()


@router.post("/devices/bind")
async def bind_device(body: dict, user: str = Depends(require_admin)):
    device_id = body.get("device_id", "").strip()
    bind_code = body.get("bind_code", "").strip()
    name = body.get("name", "").strip()

    if not device_id:
        raise HTTPException(status_code=400, detail="device_id 不能为空")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM devices WHERE device_id = %s", (device_id,))
            existing = cur.fetchone()

            if existing:
                if existing["bind_code"] and existing["bind_code"] != bind_code:
                    raise HTTPException(status_code=403, detail="绑定码错误")
            else:
                code = bind_code or f"{random.randint(1000, 9999)}"
                cur.execute(
                    "INSERT INTO devices (device_id, name, bind_code) VALUES (%s, %s, %s)",
                    (device_id, name or device_id, code)
                )
                conn.commit()
                return {"status": "bound", "bind_code": code}
    finally:
        conn.close()
    return {"status": "ok"}


# --- 学习时段 ---

@router.get("/sessions")
def list_sessions(device_id: str = "", user: str = Depends(get_current_user),
                  limit: Annotated[int, FastAPIQuery(ge=1, le=500)] = 50,
                  period: Literal['all', 'today', 'week'] = 'all',
                  day: date | None = None):
    from app.analysis.health_dimensions import STATES as HEALTH_STATES, PRIMARY as HEALTH_PRIMARY
    from app.api.record_scope import session_candidates
    try:
        candidate_sql, params = session_candidates(device_id, period, day, limit)
    except (ValueError, OverflowError):
        raise HTTPException(422, "请选择有效的记录日期")
    # 风险标志位：每段命中的标志位个数（允许重叠），供界面按标志位筛选
    from app.analysis.risk_flags import FLAGS as _FLAG_DEFS
    flag_cols = ",".join(
        "SUM(FIND_IN_SET('" + f['key'] + "',COALESCE(a.risk_flags,''))>0) AS flag_" + f['key']
        for f in _FLAG_DEFS)    # 按健康维度精确计数：维度成员来自唯一事实来源 health_dimensions.STATES。
    # 注意：本 SQL 随后还要经过 pymysql 的 %-格式化，字面量百分号必须保持 %%， 
    # 因此这里用字符串拼接而不是 % 运算符，避免提前把 %% 解析成 %。
    dim_cols = ",".join(
        "SUM(CASE WHEN a.person_present=1 AND a.learning_state IN (%s) THEN 1 ELSE 0 END) AS %s_samples"
        % (",".join("'" + s + "'" for s in members), key)
        for key, members in HEALTH_STATES.items())
    # 互斥主归属：每个状态只算一次，桶内样本之和等于 valid_samples（absent 上游已排除）
    _primary_groups = {}
    for _state, _bucket in HEALTH_PRIMARY.items():
        if _state == 'absent':
            continue
        _primary_groups.setdefault(_bucket, []).append(_state)
    primary_cols = ",".join(
        "SUM(CASE WHEN a.person_present=1 AND a.learning_state IN (%s) THEN 1 ELSE 0 END) AS primary_%s_samples"
        % (",".join("'" + s + "'" for s in states), key)
        for key, states in _primary_groups.items())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql=("""SELECT s.*,COUNT(a.id) AS sample_count,
                SUM(CASE WHEN a.person_present=1 AND a.learning_state<>'absent' THEN 1 ELSE 0 END) AS valid_samples,
                SUM(CASE WHEN a.person_present=1 AND a.learning_state='distracted_phone' THEN 1 ELSE 0 END) AS phone_samples,
                SUM(CASE WHEN a.person_present=1 AND a.learning_state='distracted_away' THEN 1 ELSE 0 END) AS away_samples,
                SUM(CASE WHEN a.person_present=1 AND a.learning_state='resting' THEN 1 ELSE 0 END) AS rest_samples,
                SUM(CASE WHEN a.person_present=1 AND a.learning_state='fatigued' THEN 1 ELSE 0 END) AS fatigue_samples,
                SUM(CASE WHEN a.person_present=1 AND a.learning_state LIKE 'engaged_%%' THEN 1 ELSE 0 END) AS engaged_samples,"""
                + dim_cols
                + ","
                + primary_cols
                + ","
                + flag_cols
                + " FROM sessions s JOIN (" + candidate_sql + ") recent ON recent.id=s.id "
                "LEFT JOIN analysis_results a ON a.session_id=s.id")
            sql+=" GROUP BY s.id HAVING valid_samples>0 ORDER BY s.start_time DESC,s.id DESC"
            cur.execute(sql,params)
            rows = cur.fetchall()
        return [
            {"id": r["id"], "device_id": r["device_id"],
             "start_time": _iso(r["start_time"]), "end_time": _iso(r["end_time"]),
             "status": r["status"],"sample_count":r["sample_count"],"valid_samples":r["valid_samples"],
             "behaviors":{k:int(r[k+"_samples"] or 0) for k in ("phone","away","rest","fatigue","engaged")},
             "dimensions":{k:int(r[k+"_samples"] or 0) for k in HEALTH_STATES},
             "primary":{k:int(r["primary_"+k+"_samples"] or 0) for k in _primary_groups},
             "risk_flags":{f["key"]:int(r["flag_"+f["key"]] or 0) for f in _FLAG_DEFS}}
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: int,
    from_time: str = None,
    to_time: str = None,
    max_points: int = FastAPIQuery(100, ge=2, le=500),
    user: str = Depends(get_current_user)
):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
            session = cur.fetchone()
            if session is None:
                raise HTTPException(status_code=404, detail="时段不存在")

            # 解析时间筛选参数（兼容 JS toISOString 的 Z 后缀和 Python 3.10）
            from_dt = None
            to_dt = None
            try:
                def parse_filter(value):
                    if not value:
                        return None
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if parsed.tzinfo is not None:
                        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                    return parsed
                from_dt, to_dt = parse_filter(from_time), parse_filter(to_time)
            except ValueError:
                raise HTTPException(400, "时间格式无效")
            if from_dt and to_dt and from_dt > to_dt:
                raise HTTPException(400, "开始时间不能晚于结束时间")

            # 构建 SQL：时间范围筛选
            if from_dt and to_dt:
                cur.execute(
                    "SELECT * FROM analysis_results WHERE session_id = %s AND timestamp >= %s AND timestamp <= %s ORDER BY timestamp",
                    (session_id, from_dt, to_dt)
                )
            elif from_dt:
                cur.execute(
                    "SELECT * FROM analysis_results WHERE session_id = %s AND timestamp >= %s ORDER BY timestamp",
                    (session_id, from_dt)
                )
            elif to_dt:
                cur.execute(
                    "SELECT * FROM analysis_results WHERE session_id = %s AND timestamp <= %s ORDER BY timestamp",
                    (session_id, to_dt)
                )
            else:
                cur.execute(
                    "SELECT * FROM analysis_results WHERE session_id = %s ORDER BY timestamp",
                    (session_id,)
                )
            results = cur.fetchall()

        # 全量记录数（不含时间筛选）
        total = len(results)

        # 降采样到 max_points
        timeline = _build_trend(results, max_points)

        # 计算筛选范围内的摘要（排除无人帧，避免默认分心值污染统计）
        filtered_count = len(results)
        present_results = [r for r in results if r.get("person_present", 1)]
        summary = None
        if present_results:
            summary = {
                "avg_fatigue": round(sum(r["fatigue_level"] for r in present_results) / len(present_results), 2),
                "avg_distraction": round(sum(r["distraction_level"] for r in present_results) / len(present_results), 2),
                "avg_difficulty": round(sum(r["difficulty_indicator"] for r in present_results) / len(present_results), 2),
                "max_difficulty": round(max(r["difficulty_indicator"] for r in present_results), 2),
                "frame_count": filtered_count,
            }

        # 提取事件（无人时不产生告警），倒序遍历=最新在前
        # 事件标签基于 learning_state，比单纯阈值更有可读性
        events = []
        for r in reversed(results):
            is_present = r.get("person_present", 1)
            if not is_present:
                continue
            ts = _iso(r["timestamp"])
            fp = r.get("raw_frame_path", "")
            ls = r.get("learning_state", "")
            action = r.get("action_state", "")

            # 按学习状态生成具体标签
            label = None
            etype = None
            detail = None

            if ls == "distracted_phone":
                label = "玩手机 📱"
                etype = "distraction"
                detail = "检测到手机使用行为"
            elif ls == "distracted_away":
                label = "注意力分散"
                etype = "distraction"
                detail = "视线偏离屏幕"
            elif ls == "fatigued":
                label = "疲劳 😴"
                etype = "fatigue"
                detail = "疲劳指标偏高"
            elif ls == "resting":
                label = "趴桌休息 💤"
                etype = "fatigue"
                detail = "学生趴下休息"
            elif r["difficulty_indicator"] > 0.5:
                label = "困难度升高"
                etype = "difficulty"
                detail = "学习内容可能偏难"
            elif r["fatigue_level"] > 0.5:
                label = "疲劳趋势"
                etype = "fatigue"
                detail = "疲劳度上升中"
            elif r["distraction_level"] > 0.5:
                label = "分心趋势"
                etype = "distraction"
                detail = "注意力持续下降"

            import json
            try: evidence = json.loads(r.get('evidence_json') or '{}')
            except (ValueError,TypeError): evidence = {}
            # Legacy rows have no object evidence; retain them but identify the old algorithm.
            if label and evidence.get('version') == 2:
                if ls == 'distracted_phone' and not evidence.get('phone_held'): continue
                if etype == 'fatigue' and ls != 'resting' and not evidence.get('face_visible'): continue
                window = evidence.get('window',{})
                if ls == 'distracted_phone': detail = '手机实物与可见手部位置对应'
                detail += f" · {window.get('samples',0)} 次连续画面 / {window.get('duration_s',0)} 秒" if window.get('confirmed') else ' · 当前画面'
            elif label:
                detail += ' · 旧版结果，未经新算法复核'
            if label:
                events.append({"timestamp": ts, "type": etype, "label": label, "detail": detail, "frame_path": fp,"image_available":bool(fp and os.path.isfile(fp)),"image_preserved":bool(fp and "alerts" in __import__("pathlib").Path(fp).parts)})

        # 离开统计
        away_count = sum(1 for r in results if not r.get("person_present", 1)) if results else 0
        if summary and filtered_count > 0:
            summary["away_pct"] = round(away_count / filtered_count * 100, 1)

        # 状态分布（饼图用）— 跳过无有效 learning_state 的旧记录
        from collections import Counter
        state_counts = Counter(
            r.get("learning_state") for r in results
            if r.get("person_present", 1) and r.get("learning_state")
        )
        total_present = sum(state_counts.values()) or 1
        state_distribution = {
            state: round(count / total_present * 100, 1)
            for state, count in state_counts.most_common()
        }

        return {
            "id": session["id"], "device_id": session["device_id"],
            "start_time": _iso(session["start_time"]),
            "end_time": _iso(session["end_time"]),
            "status": session["status"],
            "timeline": timeline,
            "total_records": total,
            "valid_records":sum(state_counts.values()),
            "state_counts":dict(state_counts),
            "behavior_samples":[{"timestamp":_iso(r["timestamp"]),"state":r.get("learning_state") or "thinking","present":bool(r.get("person_present",1))} for r in _behavior_points(results)],
            "summary": summary,
            "state_distribution": state_distribution,
            "events": events,
        }
    finally:
        conn.close()


@router.get("/overview/today")
async def get_today_overview(user: str = Depends(get_current_user)):
    """今日概览：学习时长、专注率、告警次数、活跃设备数"""
    conn = get_connection()
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        # MySQL DATETIME 无时区
        today_start_naive = today_start.replace(tzinfo=None)

        with conn.cursor() as cur:
            # 活跃设备数（今天有上报过的设备）
            cur.execute(
                """SELECT COUNT(DISTINCT device_id) as cnt FROM sessions
                   WHERE start_time >= %s""",
                (today_start_naive,)
            )
            active_devices = cur.fetchone()["cnt"] or 0

            # 今日学习时段
            cur.execute(
                """SELECT id, device_id, start_time, end_time, status FROM sessions
                   WHERE start_time >= %s ORDER BY start_time""",
                (today_start_naive,)
            )
            sessions = cur.fetchall()

            # 统计
            total_learning_sec = 0
            total_frames = 0
            alert_count = 0
            engaged_frames = 0
            present_frames = 0

            for s in sessions:
                sid = s["id"]
                cur.execute(
                    "SELECT * FROM analysis_results WHERE session_id = %s ORDER BY timestamp",
                    (sid,)
                )
                results = cur.fetchall()

                for r in results:
                    if not r.get("person_present", 1):
                        continue
                    present_frames += 1
                    total_frames += 1

                    ls = r.get("learning_state", "")
                    if ls.startswith("engaged"):
                        engaged_frames += 1
                    if ls in ("distracted_phone", "distracted_away", "fatigued"):
                        alert_count += 1

                # 学习时长（有人帧 × 帧间隔约 6 秒估算，或直接按时段长度）
                if s["end_time"] and s["start_time"]:
                    dur = (s["end_time"] - s["start_time"]).total_seconds()
                    if dur > 0:  # 防御：跳过时区异常导致的负时长
                        total_learning_sec += dur
                elif s["start_time"]:
                    total_learning_sec += (datetime.now(timezone.utc).replace(tzinfo=None) - s["start_time"]).total_seconds()

            total_minutes = round(total_learning_sec / 60)
            focus_rate = round(engaged_frames / max(present_frames, 1) * 100)

        return {
            "active_devices": active_devices,
            "total_minutes": total_minutes,
            "total_sessions": len(sessions),
            "alert_count": alert_count,
            "focus_rate": focus_rate,
        }
    finally:
        conn.close()


@router.get("/realtime/{device_id}")
async def get_realtime(device_id: str, user: str = Depends(get_current_user)):
    from app.core import live_state
    live = live_state.status(device_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sessions WHERE device_id = %s AND status = 'active' ORDER BY start_time DESC LIMIT 1",
                (device_id,)
            )
            session_row = cur.fetchone()

            if session_row is None:
                return {"online": live["online"], "live": live, "session": None, "summary": {}, "trend": []}

            ten_min_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
            cur.execute(
                "SELECT * FROM analysis_results WHERE session_id = %s AND timestamp >= %s ORDER BY timestamp",
                (session_row["id"], ten_min_ago)
            )
            recent = cur.fetchall()

            if not recent:
                return {"online": live["online"], "live": live, "session_id": session_row["id"], "summary": {}, "trend": []}

            # 1分钟汇总（卡片用）
            one_min_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
            # pymysql 返回 naive datetime，补时区后筛选
            last_min = []
            for r in recent:
                ts = r["timestamp"]
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= one_min_ago:
                    last_min.append(r)
            if not last_min:
                last_min = recent[-5:] if len(recent) >= 5 else recent

            present_min = [r for r in last_min if r.get("person_present", 1)]
            if not present_min:
                present_min = last_min

            avg_fatigue = sum(r["fatigue_level"] for r in present_min) / len(present_min)
            avg_distraction = sum(r["distraction_level"] for r in present_min) / len(present_min)
            avg_difficulty = sum(r["difficulty_indicator"] for r in present_min) / len(present_min)
            latest = last_min[-1]

            # 10分钟趋势（30秒桶采样，最多20个点）
            trend = _build_trend(recent)

            # 最近告警（5条，连续同类型合并去重，取最新）
            alert_states = {"distracted_phone", "distracted_away", "fatigued"}
            all_runs = []
            current_run = None  # {learning_state, start_ts, end_ts, fatigue_sum, distraction_sum, count}

            for r in recent:
                ls = r.get("learning_state", "")
                ts = r["timestamp"]
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

                if ls in alert_states and r.get("person_present", 1):
                    if current_run and current_run["learning_state"] == ls:
                        current_run["end_ts"] = ts
                        current_run["fatigue_sum"] += r["fatigue_level"]
                        current_run["distraction_sum"] += r["distraction_level"]
                        current_run["count"] += 1
                    else:
                        if current_run:
                            all_runs.append(current_run)
                        current_run = {
                            "learning_state": ls,
                            "start_ts": ts,
                            "end_ts": ts,
                            "fatigue_sum": r["fatigue_level"],
                            "distraction_sum": r["distraction_level"],
                            "count": 1,
                        }
                else:
                    if current_run:
                        all_runs.append(current_run)
                        current_run = None

            if current_run:
                all_runs.append(current_run)

            print(f"[Alerts] {device_id}: {len(all_runs)} alert runs found in last 10min, "
                  f"keeping {min(5, len(all_runs))} most recent")

            alerts = []
            for run in all_runs[-5:]:
                cnt = run["count"]
                alerts.append({
                    "learning_state": run["learning_state"],
                    "start_time": _iso(run["start_ts"]),
                    "end_time": _iso(run["end_ts"]),
                    "duration_s": int((run["end_ts"] - run["start_ts"]).total_seconds()),
                    "frame_count": cnt,
                    "avg_fatigue": round(run["fatigue_sum"] / cnt, 2),
                    "avg_distraction": round(run["distraction_sum"] / cnt, 2),
                })

            # 最新心理状态参数
            psyche_fields = ["e1_aggression","e2_stress","e3_tension","e4_suspiciousness",
                           "e5_balance","e6_charm","e7_energy","e8_self_regulation",
                           "e9_inhibition","e10_neuroticism","e11_gloominess",
                           "e12_happiness","e13_extraversion","e14_stability",
                           "happiness_index","happiness_level","safety_risk"]
            psychology = {k: latest.get(k, 0) or 0 for k in psyche_fields}

            return {
                "online": live["online"],
                "live": live,
                "session_id": session_row["id"],
                "device_id": device_id,
                "session_start": _iso(session_row["start_time"]),
                "summary": {
                    "avg_fatigue": round(avg_fatigue, 2),
                    "avg_distraction": round(avg_distraction, 2),
                    "avg_difficulty": round(avg_difficulty, 2),
                    "learning_state": latest.get("learning_state", ""),
                    "current_action": latest["action_state"],
                    "current_gaze": latest["gaze_direction"],
                    "person_present": bool(latest.get("person_present", 1)),
                    "sscma_person_score": latest.get("sscma_person_score", 0),
                    "vad_speaking_pct": latest.get("vad_speaking_pct", 0),
                    "sample_count": len(last_min),
                    "psychology": psychology,
                },
                "trend": trend,
                "alerts": alerts,
            }
    finally:
        conn.close()


@router.get("/psychology/{device_id}")
async def get_psychology_history(device_id: str,
                                  minutes: int = FastAPIQuery(default=30, ge=5, le=120),
                                  user: str = Depends(get_current_user)):
    """获取设备的心理状态历史数据（用于雷达图+趋势图）"""
    conn = get_connection()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        with conn.cursor() as cur:
            cur.execute(
                """SELECT timestamp,
                   e1_aggression,e2_stress,e3_tension,e4_suspiciousness,e5_balance,
                   e6_charm,e7_energy,e8_self_regulation,e9_inhibition,e10_neuroticism,
                   e11_gloominess,e12_happiness,e13_extraversion,e14_stability,
                   happiness_index,happiness_level,safety_risk
                   FROM analysis_results
                   WHERE session_id IN (
                     SELECT id FROM sessions WHERE device_id=%s AND status='active'
                   )
                   AND timestamp >= %s AND person_present=1
                   ORDER BY timestamp""",
                (device_id, cutoff)
            )
            rows = cur.fetchall()

        if not rows:
            return {"device_id": device_id, "online": False, "latest": None, "history": [], "message": "无近期数据"}

        # 最新值
        latest_row = rows[-1]
        latest = {
            "e1": float(latest_row.get("e1_aggression", 0) or 0),
            "e2": float(latest_row.get("e2_stress", 0) or 0),
            "e3": float(latest_row.get("e3_tension", 0) or 0),
            "e4": float(latest_row.get("e4_suspiciousness", 0) or 0),
            "e5": float(latest_row.get("e5_balance", 0) or 0),
            "e6": float(latest_row.get("e6_charm", 0) or 0),
            "e7": float(latest_row.get("e7_energy", 0) or 0),
            "e8": float(latest_row.get("e8_self_regulation", 0) or 0),
            "e9": float(latest_row.get("e9_inhibition", 0) or 0),
            "e10": float(latest_row.get("e10_neuroticism", 0) or 0),
            "e11": float(latest_row.get("e11_gloominess", 0) or 0),
            "e12": float(latest_row.get("e12_happiness", 0) or 0),
            "e13": float(latest_row.get("e13_extraversion", 0) or 0),
            "e14": float(latest_row.get("e14_stability", 0) or 0),
            "happiness_index": float(latest_row.get("happiness_index", 0) or 0),
            "happiness_level": latest_row.get("happiness_level", "") or "",
            "safety_risk": latest_row.get("safety_risk", "") or "",
            "timestamp": _iso(latest_row["timestamp"]),
        }

        # 历史趋势（降采样最多60点）
        step = max(1, len(rows) // 60)
        history = []
        for i in range(0, len(rows), step):
            chunk = rows[i:i + step]
            n = len(chunk)
            history.append({
                "timestamp": _iso(chunk[-1]["timestamp"]),
                "e1": round(sum(float(r.get("e1_aggression", 0) or 0) for r in chunk) / n, 1),
                "e2": round(sum(float(r.get("e2_stress", 0) or 0) for r in chunk) / n, 1),
                "e3": round(sum(float(r.get("e3_tension", 0) or 0) for r in chunk) / n, 1),
                "e7": round(sum(float(r.get("e7_energy", 0) or 0) for r in chunk) / n, 1),
                "e8": round(sum(float(r.get("e8_self_regulation", 0) or 0) for r in chunk) / n, 1),
                "e12": round(sum(float(r.get("e12_happiness", 0) or 0) for r in chunk) / n, 1),
                "e14": round(sum(float(r.get("e14_stability", 0) or 0) for r in chunk) / n, 1),
                "happiness_index": round(sum(float(r.get("happiness_index", 0) or 0) for r in chunk) / n, 1),
            })

        return {
            "device_id": device_id,
            "online": True,
            "latest": latest,
            "history": history,
            "time_range_minutes": minutes,
        }
    finally:
        conn.close()


@router.get("/frame-image")
async def serve_frame_image(path: str = FastAPIQuery(...), user: str = Depends(get_current_user_loose)):
    """Serve a saved frame image with path traversal protection"""
    abs_root = os.path.abspath(FRAME_SAVE_DIR)
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
        raise HTTPException(status_code=403, detail="invalid path")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(abs_path, media_type="image/jpeg")


def _build_trend(records, max_points=100):
    """将记录按分桶降采样，返回最多 max_points 个趋势点（含心理参数）"""
    if not records:
        return []

    def _point(r):
        return {
            "timestamp": _iso(r["timestamp"]),
            "fatigue": r["fatigue_level"],
            "distraction": r["distraction_level"],
            "difficulty": r["difficulty_indicator"],
            "happiness_index": float(r.get("happiness_index", 0) or 0),
            "e2_stress": float(r.get("e2_stress", 0) or 0),
            "e7_energy": float(r.get("e7_energy", 0) or 0),
            "e12_happiness": float(r.get("e12_happiness", 0) or 0),
        }

    if len(records) <= max_points:
        return [_point(r) for r in records]

    step = max(1, len(records) // max_points)
    buckets = []
    for i in range(0, len(records), step):
        chunk = records[i:i + step]
        buckets.append({
            "timestamp": _iso(chunk[-1]["timestamp"]),
            "fatigue": round(sum(r["fatigue_level"] for r in chunk) / len(chunk), 2),
            "distraction": round(sum(r["distraction_level"] for r in chunk) / len(chunk), 2),
            "difficulty": round(sum(r["difficulty_indicator"] for r in chunk) / len(chunk), 2),
            "happiness_index": round(sum(float(r.get("happiness_index", 0) or 0) for r in chunk) / len(chunk), 1),
            "e2_stress": round(sum(float(r.get("e2_stress", 0) or 0) for r in chunk) / len(chunk), 1),
            "e7_energy": round(sum(float(r.get("e7_energy", 0) or 0) for r in chunk) / len(chunk), 1),
            "e12_happiness": round(sum(float(r.get("e12_happiness", 0) or 0) for r in chunk) / len(chunk), 1),
        })
    return buckets


# ============================================================
# Agent 对话接口
# ============================================================

from pydantic import BaseModel, Field
from typing import Literal


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    device_id: str = Field(default="default", min_length=1, max_length=128)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


@router.post("/agent/chat")
async def agent_chat(req: AgentChatRequest, user: str = Depends(get_current_user)):
    """Agent 对话 —— 结合行为缓冲区的结构化上下文"""
    from app.analysis.agent import get_agent, get_buffer
    agent = get_agent()
    snapshot = get_buffer(req.device_id).get_snapshot()
    import asyncio
    if not req.message.strip():
        raise HTTPException(422, "请输入你的问题")
    history = [turn.model_dump() for turn in req.history]
    reply = await asyncio.to_thread(agent.chat, req.message, snapshot, history)
    return {"reply": reply}


@router.get("/agent/analyze")
async def agent_analyze(device_id: str = "default", user: str = Depends(get_current_user)):
    """结构化行为分析 —— LLM 输出 JSON"""
    from app.analysis.agent import get_agent, get_buffer
    buffer = get_buffer(device_id)
    snapshot = buffer.get_snapshot()

    # 本地统计摘要（无需 LLM，秒出）
    summary = buffer.get_summary()

    # LLM 深度分析
    agent = get_agent()
    import asyncio
    analysis = await asyncio.to_thread(agent.analyze, snapshot)

    return {
        "summary": summary,
        "analysis": analysis,
        "has_data": len(snapshot) > 0,
    }
