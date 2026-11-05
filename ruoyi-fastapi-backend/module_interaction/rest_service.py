"""Per-user, server-timed rest sessions; no changes to the application's DB."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid

PROJECTS = (
    {'id': 'breathing', 'title': '呼吸放松', 'description': '跟随圆环，给自己一分钟平静', 'duration_seconds': 60, 'prompt': '一起放松一分钟。跟随圆环，缓慢吸气，再缓慢呼气。'},
    {'id': 'eyes', 'title': '远眺休息', 'description': '把视线从屏幕移开，看看远处', 'duration_seconds': 60, 'prompt': '把视线从屏幕移开，看看远处。一分钟后，可以对摄像头点赞确认完成。'},
    {'id': 'stretch', 'title': '肩颈放松', 'description': '放下手边的事，轻轻活动肩膀', 'duration_seconds': 90, 'prompt': '放下手边的事，放松肩膀，轻轻活动肩颈，保持自然呼吸。'},
)
LOCAL_TIMEZONE = timezone(timedelta(hours=8))

class RestError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message

class RestService:
    def __init__(self, database_path=None, clock=None):
        self.database_path = Path(database_path) if database_path else Path(__file__).resolve().parents[1]/'.runtime/interactive-rest.sqlite3'
        self.clock = clock or time.time
        self._lock = threading.RLock()
        self._initialized = False

    @staticmethod
    def catalog():
        return [dict(p) for p in PROJECTS]

    @staticmethod
    def validate_source(source):
        if source in ('local', 'rtsp'):
            return source
        if isinstance(source, str) and re.fullmatch(r'xiaozhi:[A-Za-z0-9:_-]{1,64}', source):
            return source
        raise RestError(400, '请选择本机、RTSP 或具体的小智摄像头')

    @staticmethod
    def _user_key(user_id):
        if isinstance(user_id, bool):
            raise RestError(401, '请重新登录')
        try:
            key = int(user_id)
        except (ValueError, TypeError):
            raise RestError(401, '请重新登录')
        if key <= 0:
            raise RestError(401, '请重新登录')
        return key

    @contextmanager
    def _transaction(self):
        with self._lock:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(self.database_path), timeout=10, isolation_level=None)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute('PRAGMA busy_timeout = 10000')
                if not self._initialized:
                    connection.execute('PRAGMA journal_mode = WAL')
                    connection.executescript('''
                        CREATE TABLE IF NOT EXISTS rest_sessions (
                            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                            project_id TEXT NOT NULL, title TEXT NOT NULL,
                            duration_seconds INTEGER NOT NULL, elapsed_seconds REAL NOT NULL DEFAULT 0,
                            phase TEXT NOT NULL, started_at REAL NOT NULL, last_resumed_at REAL,
                            completed_at REAL, source TEXT NOT NULL, device_label TEXT NOT NULL,
                            completed_by TEXT
                        );
                        CREATE INDEX IF NOT EXISTS rest_user_history ON rest_sessions(user_id, completed_at DESC);
                        CREATE UNIQUE INDEX IF NOT EXISTS rest_one_active ON rest_sessions(user_id)
                            WHERE phase IN ('running', 'paused', 'awaiting_confirmation');
                    ''')
                    self._initialized = True
                connection.execute('BEGIN IMMEDIATE')
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _elapsed(row, now):
        elapsed = max(0.0, float(row['elapsed_seconds']))
        if row['phase'] == 'running' and row['last_resumed_at'] is not None:
            elapsed += max(0.0, now-row['last_resumed_at'])
        return min(float(row['duration_seconds']), elapsed)

    def _advance(self, connection, row, now):
        if row['phase'] == 'running' and self._elapsed(row, now) >= row['duration_seconds']:
            connection.execute("UPDATE rest_sessions SET elapsed_seconds=duration_seconds, phase='awaiting_confirmation', last_resumed_at=NULL WHERE id=?", (row['id'],))
            row = connection.execute('SELECT * FROM rest_sessions WHERE id=?', (row['id'],)).fetchone()
        return row

    @staticmethod
    def _date(value):
        return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None

    def _view(self, row, now):
        return {
            'id': row['id'], 'project_id': row['project_id'], 'title': row['title'],
            'duration_seconds': row['duration_seconds'], 'elapsed_seconds': round(self._elapsed(row, now), 3),
            'phase': row['phase'], 'started_at': self._date(row['started_at']),
            'completed_at': self._date(row['completed_at']), 'source': row['source'],
            'device_label': row['device_label'], 'completed_by': row['completed_by'],
        }

    def get_state(self, user_id):
        owner = self._user_key(user_id)
        now = self.clock()
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM rest_sessions WHERE user_id=? AND phase IN ('running','paused','awaiting_confirmation')", (owner,)).fetchone()
            if row is not None:
                row = self._advance(connection, row, now)
            history = connection.execute("SELECT * FROM rest_sessions WHERE user_id=? AND phase='completed' ORDER BY completed_at DESC, rowid DESC LIMIT 20", (owner,)).fetchall()
            today = datetime.fromtimestamp(now, LOCAL_TIMEZONE).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
            count = connection.execute("SELECT COUNT(*) FROM rest_sessions WHERE user_id=? AND phase='completed' AND completed_at>=? AND completed_at<?", (owner,today,today+86400)).fetchone()[0]
            return {'active': self._view(row, now) if row is not None else None,
                    'records': [self._view(item, now) for item in history], 'today_completed': count}

    def create_session(self, user_id, project_id, source='local', device_label=None):
        owner = self._user_key(user_id)
        project = next((p for p in PROJECTS if p['id']==project_id), None)
        if project is None:
            raise RestError(400, '休息项目不存在')
        source = self.validate_source(source)
        label = device_label.strip() if isinstance(device_label,str) else ''
        if len(label)>80 or re.search(r'[\x00-\x1f\x7f]',label):
            raise RestError(400,'设备名称格式不正确')
        label = label or ('小智摄像头' if source.startswith('xiaozhi:') else {'local':'本机摄像头','rtsp':'RTSP 摄像头'}[source])
        now = self.clock()
        with self._transaction() as connection:
            existing = connection.execute("SELECT * FROM rest_sessions WHERE user_id=? AND phase IN ('running','paused','awaiting_confirmation')", (owner,)).fetchone()
            if existing is not None:
                existing = self._advance(connection,existing,now)
                if existing['project_id']==project_id and existing['source']==source:
                    return self._view(existing,now)
                raise RestError(409,'你还有进行中的休息，请先完成或结束本次休息')
            session_id = str(uuid.uuid4())
            connection.execute('''INSERT INTO rest_sessions
                (id,user_id,project_id,title,duration_seconds,phase,started_at,last_resumed_at,source,device_label)
                VALUES (?,?,?,?,?,'running',?,?,?,?)''',
                (session_id,owner,project_id,project['title'],project['duration_seconds'],now,now,source,label))
            return self._view(connection.execute('SELECT * FROM rest_sessions WHERE id=?',(session_id,)).fetchone(),now)

    def act(self, user_id, session_id, action, method='button'):
        owner = self._user_key(user_id)
        if action not in ('pause','resume','finish','cancel') or method not in ('button','gesture'):
            raise RestError(400,'休息操作不正确')
        now = self.clock()
        with self._transaction() as connection:
            row = connection.execute('SELECT * FROM rest_sessions WHERE id=? AND user_id=?',(session_id,owner)).fetchone()
            if row is None:
                raise RestError(404,'休息记录不存在')
            row = self._advance(connection,row,now)
            if row['phase']=='completed':
                if action=='finish':return self._view(row,now)
                raise RestError(409,'本次休息已经完成')
            if row['phase']=='cancelled':
                if action=='cancel':return self._view(row,now)
                raise RestError(409,'本次休息已经结束')
            elapsed = self._elapsed(row,now)
            if action=='finish':
                if row['phase']!='awaiting_confirmation':
                    raise RestError(409,'休息倒计时尚未结束，请完成后再确认')
                connection.execute("UPDATE rest_sessions SET phase='completed',completed_at=?,completed_by=? WHERE id=?",(now,method,session_id))
            elif action=='cancel':
                connection.execute("UPDATE rest_sessions SET phase='cancelled',elapsed_seconds=?,last_resumed_at=NULL WHERE id=?",(elapsed,session_id))
            elif action=='pause' and row['phase']=='running':
                connection.execute("UPDATE rest_sessions SET phase='paused',elapsed_seconds=?,last_resumed_at=NULL WHERE id=?",(elapsed,session_id))
            elif action=='resume' and row['phase']=='paused':
                connection.execute("UPDATE rest_sessions SET phase='running',last_resumed_at=? WHERE id=?",(now,session_id))
            return self._view(connection.execute('SELECT * FROM rest_sessions WHERE id=?',(session_id,)).fetchone(),now)
