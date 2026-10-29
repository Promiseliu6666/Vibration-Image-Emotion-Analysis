import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from pathlib import Path
from app.device import capture_control
from app.core import live_state
from app.device import device_registry
from app.api.api_router import get_current_user, require_admin
from app.core.db import get_connection
from app.core.config import FRAME_SAVE_DIR

def _health():
    """延迟导入采集状态缓存（首次调用时才载入）。"""
    from app.api import console_health
    return console_health

POSTURE_REASONS={'no_person':'画面无人','too_dark':'光线偏暗','too_bright':'画面过亮','too_blurry':'画面发虚','no_pose':'未识别到姿态','keypoints_hidden':'肩或髋被遮挡','out_of_frame':'身体超出画面','too_far':'离镜头太远','unknown':'其他'}

router = APIRouter(prefix='/api/console', dependencies=[Depends(get_current_user)])

@router.get('/status')
def status():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT device_id,name FROM devices ORDER BY created_at DESC')
            devices = cur.fetchall()
            # 有无专属连接密码 = 走 Wi-Fi 的设备；没登记过的就是 USB 有线设备
            cur.execute('SELECT device_id FROM device_credentials WHERE enabled=1')
            wireless = {row['device_id'] for row in cur.fetchall()}
    finally: conn.close()
    for device in devices:
        device['wireless'] = device['device_id'] in wireless
        device['live'] = live_state.status(device['device_id'])
        from app.analysis.phone_alerts import alerts
        device['live']['phone_alert'] = alerts.snapshot(device['device_id'])
        from app.analysis.state_sync import screen_sync
        playback = screen_sync.snapshot(device['device_id'])
        phone = device['live']['phone_alert']
        if (phone.get('enabled') and playback.get('what') == 'phone' and
                (playback.get('voice_at') or 0) >= (phone.get('since') or float('inf'))):
            phone.update(voice_status=playback['voice'], error=playback.get('voice_error'))
        device['test'] = device['device_id'].startswith(('sim-', 'reproduction-', 'e2e-', 'test-'))
    from app.analysis.agent import get_agent
    from app.api.camera_bridge import snapshot as camera_bridge_snapshot
    return {'devices': devices, 'camera_bridges': camera_bridge_snapshot(), 'capture': _health().snapshot(), 'assistant_configured': bool(get_agent().client),
            'server_time': datetime.now(timezone.utc).isoformat()}

@router.get('/preview/{device_id}')
def preview(device_id: str, analyzed: bool = False, frame_id: str | None = None):
    jpeg = live_state.preview(device_id, analyzed=analyzed, frame_id=frame_id)
    if not jpeg: raise HTTPException(404, '暂时没有新画面')
    return Response(jpeg, media_type='image/jpeg', headers={'Cache-Control':'no-store'})

class CaptureRequest(BaseModel):
    device_id: str | None = Field(default=None,max_length=64)
    port: str | None = None
    expected_usb_serial: str | None = Field(default=None,max_length=128)

@router.post('/capture/{action}', dependencies=[Depends(require_admin)])
def capture(action: str, request: Request, body: CaptureRequest | None = None):
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, '请在运行后台的电脑上控制 USB 采集')
    if action not in ('start', 'stop'): raise HTTPException(400, '未知操作')
    try:
        if action == 'start' and body and body.expected_usb_serial:
            from app.device import usb_identity
            if not any(p.device == body.port and p.serial_number == body.expected_usb_serial for p in usb_identity.camera_ports()):
                raise ValueError('连接的物理设备已变化，请重新运行接入检测。')
        result=capture_control.set_running(action == 'start', port=body.port if body else None, device_id=body.device_id if body else None)
        _health().invalidate()
        return result
    except ValueError as e: raise HTTPException(409, str(e))
    except (OSError, RuntimeError): raise HTTPException(503, '采集操作未完成，请检查 USB 或服务日志')

class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=64)

@router.patch('/devices/{device_id}', dependencies=[Depends(require_admin)])
def rename(device_id: str, body: Rename):
    name = body.name.strip()
    if not name: raise HTTPException(400, '请输入设备名称')
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM devices WHERE device_id=%s', (device_id,))
            if not cur.fetchone(): raise HTTPException(404, '设备不存在')
            cur.execute('UPDATE devices SET name=%s WHERE device_id=%s', (name, device_id))
        conn.commit()
    finally: conn.close()
    return {'name': name}

@router.get('/devices/{device_id}/deletion')
def deletion_info(device_id: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS n FROM sessions WHERE device_id=%s', (device_id,)); sessions = cur.fetchone()['n']
            cur.execute('SELECT COUNT(*) AS n FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s', (device_id,)); records = cur.fetchone()['n']
    finally: conn.close()
    return {'sessions':sessions, 'records':records}

class Delete(BaseModel):
    confirm_device_id: str

@router.delete('/devices/{device_id}', dependencies=[Depends(require_admin)])
def delete(device_id: str, body: Delete, request: Request):
    if body.confirm_device_id != device_id: raise HTTPException(400, '确认的设备不匹配')
    capture_status = capture_control.status(device_id)
    if device_id == capture_status.get('device_id') and capture_status['running']:
        if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
            raise HTTPException(409, '请先在采集电脑停止 USB 采集')
        capture_control.set_running(False,device_id=device_id)
    paths=[]
    with device_registry.lock:
        previous = device_registry.blocked(device_id)
        device_registry.set_blocked(device_id, True)
        conn = None
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM devices WHERE device_id=%s', (device_id,))
                if not cur.fetchone(): raise HTTPException(404, '设备不存在')
                cur.execute('SELECT a.raw_frame_path FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s', (device_id,))
                paths=[r['raw_frame_path'] for r in cur.fetchall() if r['raw_frame_path']]
                cur.execute('DELETE a FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s', (device_id,))
                cur.execute('DELETE FROM sessions WHERE device_id=%s', (device_id,))
                cur.execute('DELETE FROM device_credentials WHERE device_id=%s',(device_id,))
                cur.execute('DELETE FROM devices WHERE device_id=%s', (device_id,))
            conn.commit()
        except Exception:
            if conn: conn.rollback()
            device_registry.set_blocked(device_id, previous)
            raise
        finally:
            if conn: conn.close()
    live_state.forget(device_id)
    root=Path(FRAME_SAVE_DIR).resolve()
    for name in paths:
        path=Path(name).resolve()
        if root in path.parents:
            try: path.unlink(missing_ok=True)
            except OSError: pass
    return {'deleted':True}

def observation_gain(cursor, column, device_id, start):
    """Observed increments remain continuous across technical session splits."""
    if column not in {'near_work_seconds','screen_seconds','presence_seconds'}:
        raise ValueError('Unknown observation counter')
    cursor.execute("SELECT SUM(GREATEST(0,cur-COALESCE(prev,cur))) AS gain, MAX(cur) AS longest "
                   "FROM (SELECT a." + column + " AS cur, "
                   "LAG(a." + column + ") OVER (ORDER BY a.timestamp,a.id) AS prev "
                   "FROM analysis_results a JOIN sessions s ON s.id=a.session_id "
                   "WHERE s.device_id=%s AND a.timestamp>=%s) t",(device_id,start))
    row=cursor.fetchone() or {}
    return {'gain':float(row.get('gain') or 0),'longest':float(row.get('longest') or 0)}


@router.get('/summary/{device_id}')
def summary(device_id: str):
    midnight = datetime.now().astimezone().replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT a.learning_state,COUNT(*) AS n,AVG(CASE WHEN JSON_VALID(a.evidence_json) AND JSON_EXTRACT(IF(JSON_VALID(a.evidence_json),a.evidence_json,'{}'),'$.face_visible')=TRUE AND JSON_EXTRACT(IF(JSON_VALID(a.evidence_json),a.evidence_json,'{}'),'$.fatigue_calibrated')=TRUE THEN a.fatigue_level ELSE NULL END) AS fatigue,SUM(CASE WHEN JSON_VALID(a.evidence_json) AND JSON_EXTRACT(IF(JSON_VALID(a.evidence_json),a.evidence_json,'{}'),'$.face_visible')=TRUE AND JSON_EXTRACT(IF(JSON_VALID(a.evidence_json),a.evidence_json,'{}'),'$.fatigue_calibrated')=TRUE THEN 1 ELSE 0 END) AS fatigue_n FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s AND a.timestamp>=%s AND a.person_present=1 AND a.learning_state<>'absent' GROUP BY a.learning_state", (device_id,midnight))
            rows=cur.fetchall()
            cur.execute("SELECT a.evidence_json FROM analysis_results a JOIN sessions s ON s.id=a.session_id WHERE s.device_id=%s AND a.timestamp>=%s AND a.person_present=1 AND a.learning_state='thinking'",(device_id,midnight))
            uncertain=cur.fetchall()
            # ---- 风险标志位聚合（三态：命中 / 未命中 / 无法判定）----
            # 标志位已落成列，用 FIND_IN_SET 聚合；旧数据没算过标志位（flags_version 为空），
            # 必须整批计入"无法判定"，不能当成"未命中"。
            from app.analysis.risk_flags import FLAGS as FLAG_DEFS, RISK_KEYS as RISK_FLAG_KEYS
            from app.analysis.risk_flags import summarize as summarize_flag_counts, FLAGS_VERSION as RISK_FLAGS_VERSION
            _computed = "COALESCE(flags_version,0)>0"
            _hit = lambda k: "(" + _computed + " AND FIND_IN_SET('" + k + "',COALESCE(risk_flags,''))>0)"
            _unk = lambda k: "(NOT (" + _computed + ") OR FIND_IN_SET('" + k + "',COALESCE(risk_unknown,''))>0)"
            flag_cols = ",".join(
                "SUM(" + _hit(f['key']) + ") AS " + f['key'] + "_hits,"
                "SUM(" + _unk(f['key']) + ") AS " + f['key'] + "_unknown"
                for f in FLAG_DEFS)
            cur.execute("SELECT " + flag_cols + ",SUM(COALESCE(risk_hit_count,0)>=2) AS composite_hits,COUNT(*) AS flag_samples"
                        " FROM analysis_results a JOIN sessions s ON s.id=a.session_id"
                        " WHERE s.device_id=%s AND a.person_present=1 AND a.timestamp>=%s",(device_id,midnight))
            flag_row = cur.fetchone() or {}
            # ---- 健康度量聚合（今日）----
            # 观测量已落列，这里全是纯列运算；今日累计 = 段内正增量之和，按 session 分区，跨段不串算。
            def _gain(q, col):
                return observation_gain(q, col, device_id, midnight)
            nw=_gain(cur,'near_work_seconds'); sc=_gain(cur,'screen_seconds'); pr=_gain(cur,'presence_seconds')
            cur.execute("""SELECT SUM(eye_assessable=1) eye_ok, SUM(posture_assessable=1) pose_ok,
                                  SUM(posture_tilt=1) tilt, COUNT(*) n
                           FROM analysis_results a JOIN sessions s ON s.id=a.session_id
                           WHERE s.device_id=%s AND a.person_present=1 AND a.timestamp>=%s""",(device_id,midnight)); kq=cur.fetchone()
            cur.execute("""SELECT COALESCE(posture_reason,'unknown') AS reason, COUNT(*) n
                           FROM analysis_results a JOIN sessions s ON s.id=a.session_id
                           WHERE s.device_id=%s AND a.person_present=1 AND a.timestamp>=%s
                           GROUP BY reason ORDER BY n DESC LIMIT 6""",(device_id,midnight)); reasons=cur.fetchall()
    finally: conn.close()
    from app.analysis.observation_status import classify, LABELS
    breakdown={key:0 for key in LABELS}
    for sample in uncertain:breakdown[classify(sample.get('evidence_json'))]+=1
    total=sum(r['n'] for r in rows)
    focused=sum(r['n'] for r in rows if r['learning_state'] in ('engaged_screen','engaged_writing','engaged_reading','engaged_hand_raising','engaged_discussing','engaged_computer'))
    from app.analysis.health_dimensions import summarize as summarize_dimensions
    from app.analysis.health_dimensions import primary_summary
    counts={r['learning_state']:int(r['n']) for r in rows}
    return {'unconfirmed_samples':sum(breakdown.values()),'unconfirmed_pct':round(sum(breakdown.values())/total*100) if total else None,'uncertainty':[{'reason':k,'label':LABELS[k],'count':n} for k,n in breakdown.items() if n], 'samples':total, 'focus_pct':round(focused/total*100) if total else None,
            'fatigue':round(sum(float(r['fatigue'] or 0)*int(r['fatigue_n'] or 0) for r in rows)/sum(int(r['fatigue_n'] or 0) for r in rows),2) if sum(r['fatigue_n'] for r in rows) else None,
            'dimensions':summarize_dimensions(counts,total),
            'primary':primary_summary(counts,total),
            'risk':{'flags':summarize_flag_counts({f['key']:{'hits':flag_row.get(f['key']+'_hits'),'unknown':flag_row.get(f['key']+'_unknown')} for f in FLAG_DEFS}),
                    'composite_hits':int(flag_row.get('composite_hits') or 0),
                    'samples':int(flag_row.get('flag_samples') or 0),
                    'version':RISK_FLAGS_VERSION},
            'eye':{'near_work_minutes':round(nw['gain']/60,1),'longest_near_work_minutes':round(nw['longest']/60,1),
                   'screen_minutes':round(sc['gain']/60,1),
                   'assessable_pct':round(float(kq['eye_ok'] or 0)/int(kq['n'])*100) if kq and kq['n'] else None},
            'posture':{'presence_minutes':round(pr['gain']/60,1),'longest_presence_minutes':round(pr['longest']/60,1),
                       'assessable_pct':round(float(kq['pose_ok'] or 0)/int(kq['n'])*100) if kq and kq['n'] else None,
                       'tilt_samples':int((kq or {}).get('tilt') or 0),
                       'reasons':[{'reason':r['reason'],'label':POSTURE_REASONS.get(r['reason'],r['reason']),'count':int(r['n'])} for r in reasons]},
            'quality':{'confirmed_pct':(100-round(sum(breakdown.values())/total*100)) if total else None},
            'distribution':[{'state':r['learning_state'],'count':r['n']} for r in rows]}


@router.post('/devices/{device_id}/voice-test', dependencies=[Depends(require_admin)])
async def voice_test(device_id: str, request: Request):
    kind = request.query_params.get('kind','phone')
    if kind not in {'phone','eye','posture','lying','fatigue','away','sit','quality'}:
        raise HTTPException(400, '不支持的测试提醒类型')
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, '请在采集电脑测试小智语音')
    current = capture_control.status(device_id)
    if current.get('device_id') != device_id or not current.get('running'):
        raise HTTPException(409, '请先连接并启动这台物理设备的 USB 采集')
    from app.analysis.phone_alerts import play_test_usb
    status,error = await asyncio.to_thread(play_test_usb,device_id,kind)
    if status != 'played':
        raise HTTPException(409,error or '测试语音未播放完成')
    return {'status': 'played', 'message': '测试语音已播放完成，请确认是否听到。'}
