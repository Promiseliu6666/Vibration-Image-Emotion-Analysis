"""Account-scoped habit preferences, observation windows and self-reported responses.

观察时段：用户设定一段观察时间，期间照常采集，到点由小智语音提示休息（到点提醒由
app/analysis/rest_reminder.py 投递）。只做习惯提示，不做诊断。
"""
from datetime import datetime,timedelta,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from app.api.api_router import get_current_user
from app.core.db import get_connection
router=APIRouter(prefix='/api/health')

class Preferences(BaseModel):
    break_minutes:int=Field(default=45,ge=15,le=90)
    break_enabled:bool=True
    posture_enabled:bool=True

class ReminderSettings(Preferences):
    device_id:str=Field(pattern=r'^[A-Za-z0-9:_-]{1,64}$')
    break_minutes:int=Field(default=45,gt=0)
    reminders_enabled:bool=True
    phone_enabled:bool=True
    eye_enabled:bool=True
    fatigue_enabled:bool=True
    away_enabled:bool=True
    quality_enabled:bool=True
    lying_enabled:bool=True
    phone_trigger_seconds:int=Field(default=4,gt=0)
    eye_trigger_minutes:int=Field(default=20,gt=0)
    posture_trigger_seconds:int=Field(default=4,gt=0)
    lying_trigger_seconds:int=Field(default=10,gt=0)
    break_repeat_minutes:int=Field(default=45,gt=0)
    fatigue_trigger_seconds:int=Field(default=60,gt=0)
    away_trigger_seconds:int=Field(default=60,gt=0)
    quality_trigger_seconds:int=Field(default=15,gt=0)
    phone_interval_minutes:int=Field(default=1,gt=0)
    eye_interval_minutes:int=Field(default=20,gt=0)
    posture_interval_minutes:int=Field(default=10,gt=0)
    lying_interval_minutes:int=Field(default=10,gt=0)
    fatigue_interval_minutes:int=Field(default=10,gt=0)
    away_interval_minutes:int=Field(default=3,gt=0)
    quality_interval_minutes:int=Field(default=5,gt=0)

REMINDER_VALUE_FIELDS = (
    'reminders_enabled','phone_enabled','eye_enabled','break_enabled','posture_enabled',
    'fatigue_enabled','away_enabled','quality_enabled','lying_enabled',
    'phone_trigger_seconds','eye_trigger_minutes','posture_trigger_seconds',
    'lying_trigger_seconds','break_repeat_minutes','fatigue_trigger_seconds',
    'away_trigger_seconds','quality_trigger_seconds','phone_interval_minutes',
    'eye_interval_minutes','posture_interval_minutes','lying_interval_minutes',
    'fatigue_interval_minutes','away_interval_minutes','quality_interval_minutes',
    'break_minutes',
)
class Action(BaseModel):
    device_id:str=Field(pattern=r'^[A-Za-z0-9:_-]{1,64}$')
    kind:Literal['break','posture']
    response:Literal['done','later']
class WindowStart(BaseModel):
    device_id:str=Field(pattern=r'^[A-Za-z0-9:_-]{1,64}$')
    minutes:int=Field(ge=10,le=90)
class WindowStop(BaseModel):
    device_id:str=Field(pattern=r'^[A-Za-z0-9:_-]{1,64}$')

REST_ACTION_TEXT='到时间了。起来活动一下，或远眺 20 秒让眼睛休息，屏幕外的东西也能看看。'

def window_view(row,now=None):
    """观察时段的对外视图：剩余秒数由服务端截止时间算出，页面只负责显示。"""
    if not row:return None
    now=now or datetime.utcnow()
    deadline=row['started_at']+timedelta(minutes=int(row['minutes']))
    row=dict(row)
    return {'id':row['id'],'device_id':row['device_id'],'minutes':int(row['minutes']),
            'started_at':row['started_at'].replace(tzinfo=timezone.utc).isoformat(),
            'deadline_utc':deadline.isoformat()+'Z',
            'remaining_seconds':max(0,round((deadline-now).total_seconds())),
            'status':row.get('status') or 'running',
            'reminded':row.get('reminded_at') is not None,
            'reminder_status':row.get('remind_status'),
            'reminder_error':row.get('remind_error'),
            'action_text':REST_ACTION_TEXT}

def schema():
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('CREATE TABLE IF NOT EXISTS health_preferences(username VARCHAR(32) PRIMARY KEY,break_minutes INT NOT NULL DEFAULT 45,break_enabled BOOLEAN NOT NULL DEFAULT TRUE,posture_enabled BOOLEAN NOT NULL DEFAULT TRUE)')
            q.execute('CREATE TABLE IF NOT EXISTS device_reminder_preferences(device_id VARCHAR(64) PRIMARY KEY,updated_by VARCHAR(32) NOT NULL,reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,phone_enabled BOOLEAN NOT NULL DEFAULT TRUE,eye_enabled BOOLEAN NOT NULL DEFAULT TRUE,break_enabled BOOLEAN NOT NULL DEFAULT TRUE,posture_enabled BOOLEAN NOT NULL DEFAULT TRUE,fatigue_enabled BOOLEAN NOT NULL DEFAULT TRUE,away_enabled BOOLEAN NOT NULL DEFAULT TRUE,quality_enabled BOOLEAN NOT NULL DEFAULT TRUE,lying_enabled BOOLEAN NOT NULL DEFAULT TRUE,phone_trigger_seconds INT NOT NULL DEFAULT 4,eye_trigger_minutes INT NOT NULL DEFAULT 20,posture_trigger_seconds INT NOT NULL DEFAULT 4,lying_trigger_seconds INT NOT NULL DEFAULT 10,break_repeat_minutes INT NOT NULL DEFAULT 45,fatigue_trigger_seconds INT NOT NULL DEFAULT 60,away_trigger_seconds INT NOT NULL DEFAULT 60,quality_trigger_seconds INT NOT NULL DEFAULT 15,phone_interval_minutes INT NOT NULL DEFAULT 1,eye_interval_minutes INT NOT NULL DEFAULT 20,posture_interval_minutes INT NOT NULL DEFAULT 10,lying_interval_minutes INT NOT NULL DEFAULT 10,fatigue_interval_minutes INT NOT NULL DEFAULT 10,away_interval_minutes INT NOT NULL DEFAULT 3,quality_interval_minutes INT NOT NULL DEFAULT 5,break_minutes INT NOT NULL DEFAULT 45,updated_at DATETIME NOT NULL,INDEX(updated_by))')
            reminder_columns={
                'lying_enabled':'BOOLEAN NOT NULL DEFAULT TRUE',
                'phone_trigger_seconds':'INT NOT NULL DEFAULT 4',
                'eye_trigger_minutes':'INT NOT NULL DEFAULT 20',
                'posture_trigger_seconds':'INT NOT NULL DEFAULT 4',
                'lying_trigger_seconds':'INT NOT NULL DEFAULT 10',
                'break_repeat_minutes':'INT NOT NULL DEFAULT 45',
                'fatigue_trigger_seconds':'INT NOT NULL DEFAULT 60',
                'away_trigger_seconds':'INT NOT NULL DEFAULT 60',
                'quality_trigger_seconds':'INT NOT NULL DEFAULT 15',
                'phone_interval_minutes':'INT NOT NULL DEFAULT 1',
                'eye_interval_minutes':'INT NOT NULL DEFAULT 20',
                'posture_interval_minutes':'INT NOT NULL DEFAULT 10',
                'lying_interval_minutes':'INT NOT NULL DEFAULT 10',
                'fatigue_interval_minutes':'INT NOT NULL DEFAULT 10',
                'away_interval_minutes':'INT NOT NULL DEFAULT 3',
                'quality_interval_minutes':'INT NOT NULL DEFAULT 5',
            }
            break_repeat_added=False
            for name,definition in reminder_columns.items():
                q.execute("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='device_reminder_preferences' AND COLUMN_NAME=%s",(name,))
                if not q.fetchone():
                    q.execute(f'ALTER TABLE device_reminder_preferences ADD COLUMN {name} {definition}')
                    if name=='break_repeat_minutes':break_repeat_added=True
            if break_repeat_added:
                q.execute('UPDATE device_reminder_preferences SET break_repeat_minutes=break_minutes')
            q.execute('CREATE TABLE IF NOT EXISTS health_actions(id BIGINT AUTO_INCREMENT PRIMARY KEY,username VARCHAR(32) NOT NULL,device_id VARCHAR(64) NOT NULL,kind VARCHAR(16) NOT NULL,response VARCHAR(16) NOT NULL,created_at DATETIME NOT NULL,INDEX(username,device_id,created_at))')
            q.execute("CREATE TABLE IF NOT EXISTS observation_windows(id BIGINT AUTO_INCREMENT PRIMARY KEY,username VARCHAR(32) NOT NULL,device_id VARCHAR(64) NOT NULL,minutes INT NOT NULL,started_at DATETIME NOT NULL,ended_at DATETIME NULL,status VARCHAR(16) NOT NULL DEFAULT 'running',reminded_at DATETIME NULL,remind_status VARCHAR(16) NULL,remind_error VARCHAR(160) NULL,INDEX(username,device_id,started_at))")
        c.commit()
    finally:c.close()

def default_reminder_settings(device_id):return ReminderSettings(device_id=device_id).model_dump()

def load_reminder_settings(device_id,username=None):
    """Read device-level settings; fall back to the account's legacy break preferences."""
    try:
        c=get_connection()
        try:
            with c.cursor() as q:
                q.execute('SELECT reminders_enabled,phone_enabled,eye_enabled,break_enabled,posture_enabled,fatigue_enabled,away_enabled,quality_enabled,lying_enabled,phone_trigger_seconds,eye_trigger_minutes,posture_trigger_seconds,lying_trigger_seconds,break_repeat_minutes,fatigue_trigger_seconds,away_trigger_seconds,quality_trigger_seconds,phone_interval_minutes,eye_interval_minutes,posture_interval_minutes,lying_interval_minutes,fatigue_interval_minutes,away_interval_minutes,quality_interval_minutes,break_minutes FROM device_reminder_preferences WHERE device_id=%s',(device_id,))
                row=q.fetchone()
                if row:
                    return ReminderSettings(device_id=device_id,**row).model_dump()
                if username:
                    q.execute('SELECT break_minutes,break_enabled,posture_enabled FROM health_preferences WHERE username=%s',(username,))
                    legacy=q.fetchone()
                else:legacy=None
            if legacy:
                return ReminderSettings(device_id=device_id,lying_enabled=bool(legacy['posture_enabled']),**legacy).model_dump()
        finally:c.close()
    except Exception:
        pass
    return default_reminder_settings(device_id)

@router.post('/window')
def start_window(body:WindowStart,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT username FROM workspace_users WHERE username=%s FOR UPDATE',(username,))
            q.execute('SELECT device_id FROM devices WHERE device_id=%s',(body.device_id,))
            if not q.fetchone():raise HTTPException(404,'设备不存在')
            q.execute("UPDATE observation_windows SET status='stopped',ended_at=UTC_TIMESTAMP() WHERE username=%s AND device_id=%s AND status IN ('running','reminding')",(username,body.device_id))
            q.execute('INSERT INTO observation_windows(username,device_id,minutes,started_at,status) VALUES(%s,%s,%s,UTC_TIMESTAMP(),%s)',(username,body.device_id,body.minutes,'running'))
            ident=q.lastrowid
            q.execute('SELECT * FROM observation_windows WHERE id=%s',(ident,));row=q.fetchone()
        c.commit()
        return {'window':window_view(row)}
    finally:c.close()

@router.post('/window/stop')
def stop_window(body:WindowStop,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute("UPDATE observation_windows SET status='stopped',ended_at=UTC_TIMESTAMP() WHERE username=%s AND device_id=%s AND status IN ('running','reminding')",(username,body.device_id))
            changed=q.rowcount
        c.commit()
        return {'stopped':bool(changed)}
    finally:c.close()

@router.get('/window')
def current_window(device_id:str,username=Depends(get_current_user)):
    """进行中的观察时段；刚结束 30 分钟内的那次也返回，供页面显示到点提示。"""
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute("SELECT * FROM observation_windows WHERE username=%s AND device_id=%s AND status IN ('running','reminding') ORDER BY id DESC LIMIT 1",(username,device_id));row=q.fetchone()
            if not row:
                q.execute("SELECT * FROM observation_windows WHERE username=%s AND device_id=%s AND status='done' AND reminded_at>=UTC_TIMESTAMP()-INTERVAL 30 MINUTE ORDER BY id DESC LIMIT 1",(username,device_id));row=q.fetchone()
        return {'window':window_view(row)}
    finally:c.close()

@router.get('/preferences')
def preferences(username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT break_minutes,break_enabled,posture_enabled FROM health_preferences WHERE username=%s',(username,));r=q.fetchone()
        return Preferences(**r).model_dump() if r else Preferences().model_dump()
    finally:c.close()

@router.put('/preferences')
def save_preferences(body:Preferences,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:q.execute('INSERT INTO health_preferences VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE break_minutes=VALUES(break_minutes),break_enabled=VALUES(break_enabled),posture_enabled=VALUES(posture_enabled)',(username,body.break_minutes,body.break_enabled,body.posture_enabled))
        c.commit();return body.model_dump()
    finally:c.close()

@router.get('/reminders')
def reminder_settings(device_id:str,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT device_id FROM devices WHERE device_id=%s',(device_id,))
            if not q.fetchone():raise HTTPException(404,'设备不存在')
    finally:c.close()
    return load_reminder_settings(device_id,username)

@router.put('/reminders')
def save_reminder_settings(body:ReminderSettings,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT device_id FROM devices WHERE device_id=%s',(body.device_id,))
            if not q.fetchone():raise HTTPException(404,'设备不存在')
            fields=REMINDER_VALUE_FIELDS
            columns=','.join(('device_id','updated_by',*fields,'updated_at'))
            placeholders=','.join(['%s']*(len(fields)+2))+',UTC_TIMESTAMP()'
            updates=','.join(f'{name}=VALUES({name})' for name in ('updated_by',*fields)) + ',updated_at=UTC_TIMESTAMP()'
            values=(body.device_id,username,*(getattr(body,name) for name in fields))
            q.execute(f'INSERT INTO device_reminder_preferences({columns}) VALUES({placeholders}) ON DUPLICATE KEY UPDATE {updates}',values)
        c.commit()
        return body.model_dump()
    finally:c.close()

@router.post('/actions')
def record_action(body:Action,username=Depends(get_current_user)):
    import hashlib
    lock_name='health:'+hashlib.sha256((username+'|'+body.device_id+'|'+body.kind+'|'+body.response).encode()).hexdigest()[:48]
    c=get_connection();locked=False
    try:
        with c.cursor() as q:
            q.execute('SELECT GET_LOCK(%s,3) AS locked',(lock_name,))
            locked=bool(q.fetchone()['locked'])
            if not locked:raise HTTPException(409,'反馈正在保存，请稍后读取状态')
            q.execute('SELECT id FROM devices WHERE device_id=%s',(body.device_id,))
            if not q.fetchone():raise HTTPException(404,'设备不存在')
            # Idempotent repeated clicks within the same minute.
            q.execute('SELECT id FROM health_actions WHERE username=%s AND device_id=%s AND kind=%s AND response=%s AND created_at>=UTC_TIMESTAMP()-INTERVAL 1 MINUTE ORDER BY id DESC LIMIT 1',(username,body.device_id,body.kind,body.response))
            row=q.fetchone()
            if not row:q.execute('INSERT INTO health_actions(username,device_id,kind,response,created_at) VALUES(%s,%s,%s,%s,UTC_TIMESTAMP())',(username,body.device_id,body.kind,body.response))
        c.commit();return {'saved':True,'self_reported':True}
    finally:
        try:
            if locked:
                with c.cursor() as q:q.execute('SELECT RELEASE_LOCK(%s)',(lock_name,))
        finally:c.close()

@router.get('/summary')
def summary(device_id:str,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT kind,response,created_at FROM health_actions WHERE username=%s AND device_id=%s ORDER BY created_at DESC LIMIT 10',(username,device_id));rows=q.fetchall()
            q.execute("SELECT COUNT(*) n FROM health_actions WHERE username=%s AND device_id=%s AND response='done' AND kind='break' AND DATE(created_at+INTERVAL 8 HOUR)=DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR)",(username,device_id));n=q.fetchone()['n']
        return {'self_reported_breaks_today':n,'recent':[dict(kind=r['kind'],response=r['response'],timestamp=r['created_at'].replace(tzinfo=timezone.utc).isoformat()) for r in rows]}
    finally:c.close()


@router.get('/trend')
def trend(device_id:str,days:int=30,username=Depends(get_current_user)):
    """Daily observable behavior; no facial inference about mental health."""
    days=max(7,min(120,int(days or 30)))
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT device_id FROM devices WHERE device_id=%s',(device_id,))
            if not q.fetchone():raise HTTPException(404,'设备不存在')
            q.execute("SELECT DATE(a.timestamp+INTERVAL 8 HOUR) AS day,COUNT(*) AS samples,"
                      "SUM(a.learning_state='distracted_phone') AS phone_samples,"
                      "SUM(a.learning_state='distracted_away') AS away_samples "
                      "FROM analysis_results a JOIN sessions s ON s.id=a.session_id "
                      "WHERE s.device_id=%s AND a.person_present=1 AND a.learning_state<>'absent' "
                      "AND a.timestamp>=UTC_TIMESTAMP()-INTERVAL %s DAY GROUP BY day ORDER BY day",(device_id,days))
            rows=q.fetchall()
        return {'device_id':device_id,'days':days,'series':[dict(day=str(r['day']),samples=int(r['samples']),phone_samples=int(r['phone_samples'] or 0),away_samples=int(r['away_samples'] or 0)) for r in rows],
                'scope':'按日期汇总可观察行为；样本不是持续时长，不根据画面判断心理状态。'}
    finally:c.close()
