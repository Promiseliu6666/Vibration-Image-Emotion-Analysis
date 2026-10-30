"""Account-scoped plans and explicit, image-aligned recognition corrections."""
import json
import hashlib
import uuid
import base64
import time
from collections import OrderedDict
from threading import RLock
from pathlib import Path
from datetime import datetime,timedelta,timezone
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,Field
from app.api.api_router import get_current_user
from app.core.db import get_connection
from app.core import live_state
from app.core.paths import FRAMES_DIR
router=APIRouter(prefix='/api/study')
REVIEWS=OrderedDict()
REVIEW_LOCK=RLock()
LABELS={'engaged_reading','engaged_writing','engaged_screen','engaged_computer','engaged_hand_raising','engaged_discussing','standing','distracted_phone','distracted_away','resting','fatigued','thinking','absent'}

def schema():
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute("CREATE TABLE IF NOT EXISTS study_profiles(username VARCHAR(32) PRIMARY KEY,goal_minutes INT NOT NULL DEFAULT 60,block_minutes INT NOT NULL DEFAULT 25)")
            q.execute("CREATE TABLE IF NOT EXISTS study_tasks(id BIGINT AUTO_INCREMENT PRIMARY KEY,username VARCHAR(32) NOT NULL,title VARCHAR(160) NOT NULL,done TINYINT NOT NULL DEFAULT 0,created_at DATETIME NOT NULL,INDEX(username,created_at))")
            q.execute("CREATE TABLE IF NOT EXISTS study_timers(id BIGINT AUTO_INCREMENT PRIMARY KEY,username VARCHAR(32) NOT NULL,minutes INT NOT NULL,started_at DATETIME NOT NULL,ended_at DATETIME NULL,INDEX(username,started_at))")
            q.execute("CREATE TABLE IF NOT EXISTS study_feedback(id BIGINT AUTO_INCREMENT PRIMARY KEY,username VARCHAR(32) NOT NULL,device_id VARCHAR(64) NOT NULL,frame_id VARCHAR(64) NOT NULL,predicted VARCHAR(32) NOT NULL,corrected VARCHAR(32) NOT NULL,note VARCHAR(300) NOT NULL,evidence_json LONGTEXT,frame_sha256 VARCHAR(64),image_path VARCHAR(512),created_at DATETIME NOT NULL,UNIQUE KEY(username,device_id,frame_id))")
        c.commit()
    finally:c.close()

class Profile(BaseModel):
    goal_minutes:int=Field(default=60,ge=10,le=600)
    block_minutes:int=Field(default=25,ge=10,le=90)
class Task(BaseModel):title:str=Field(min_length=1,max_length=160)
class Done(BaseModel):done:bool
class Timer(BaseModel):minutes:int=Field(ge=10,le=90)
class Feedback(BaseModel):
    device_id:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9:_-]+$')
    frame_id:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    corrected:str=Field(max_length=32)
    note:str=Field(default='',max_length=300)
    save_image:bool=False

def timer_view(row,now=None):
    if not row:return None
    now=now or datetime.utcnow();deadline=row['started_at']+timedelta(minutes=row['minutes'])
    return {'id':row['id'],'minutes':row['minutes'],'remaining_seconds':max(0,round((deadline-now).total_seconds())),'deadline_utc':deadline.isoformat()+'Z'}

@router.get('/board')
def board(username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT goal_minutes,block_minutes FROM study_profiles WHERE username=%s',(username,));profile=q.fetchone() or Profile().model_dump()
            q.execute('SELECT id,title,done FROM study_tasks WHERE username=%s ORDER BY done,id DESC LIMIT 100',(username,));tasks=q.fetchall()
            q.execute('SELECT id,minutes,started_at FROM study_timers WHERE username=%s AND ended_at IS NULL ORDER BY id DESC LIMIT 1',(username,));timer=timer_view(q.fetchone())
            q.execute("SELECT COALESCE(SUM(LEAST(minutes*60,GREATEST(0,TIMESTAMPDIFF(SECOND,started_at,ended_at)))),0) AS seconds FROM study_timers WHERE username=%s AND ended_at IS NOT NULL AND DATE(started_at+INTERVAL 8 HOUR)=DATE(UTC_TIMESTAMP()+INTERVAL 8 HOUR)",(username,));minutes=int(q.fetchone()['seconds'])//60
        return {'profile':profile,'tasks':tasks,'timer':timer,'planned_minutes_today':minutes}
    finally:c.close()

@router.put('/profile')
def profile(body:Profile,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:q.execute('INSERT INTO study_profiles(username,goal_minutes,block_minutes) VALUES(%s,%s,%s) ON DUPLICATE KEY UPDATE goal_minutes=VALUES(goal_minutes),block_minutes=VALUES(block_minutes)',(username,body.goal_minutes,body.block_minutes))
        c.commit()
    finally:c.close()
    return body.model_dump()

@router.post('/tasks')
def add_task(body:Task,username=Depends(get_current_user)):
    title=body.title.strip()
    if not title:raise HTTPException(400,'请输入任务内容')
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT COUNT(*) AS n FROM study_tasks WHERE username=%s AND done=0',(username,))
            if q.fetchone()['n']>=50:raise HTTPException(409,'先完成部分任务，再添加新的任务')
            q.execute('INSERT INTO study_tasks(username,title,created_at) VALUES(%s,%s,UTC_TIMESTAMP())',(username,title));ident=q.lastrowid
        c.commit()
    finally:c.close()
    return {'id':ident,'title':title,'done':False}

@router.patch('/tasks/{ident}')
def task_done(ident:int,body:Done,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT id FROM study_tasks WHERE id=%s AND username=%s',(ident,username))
            if not q.fetchone():raise HTTPException(404,'任务不存在')
            q.execute('UPDATE study_tasks SET done=%s WHERE id=%s AND username=%s',(body.done,ident,username))
        c.commit()
    finally:c.close()
    return {'done':body.done}

@router.post('/timer')
def start_timer(body:Timer,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            # Lock the account row to serialize starts and prevent duplicate active timers.
            q.execute('SELECT username FROM workspace_users WHERE username=%s FOR UPDATE',(username,))
            q.execute('SELECT id FROM study_timers WHERE username=%s AND ended_at IS NULL',(username,))
            if q.fetchone():raise HTTPException(409,'已有学习计时，请先结束当前计时')
            q.execute('INSERT INTO study_timers(username,minutes,started_at) VALUES(%s,%s,UTC_TIMESTAMP())',(username,body.minutes))
        c.commit()
    finally:c.close()
    return board(username)

@router.post('/timer/{ident}/finish')
def finish_timer(ident:int,username=Depends(get_current_user)):
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT id FROM study_timers WHERE id=%s AND username=%s',(ident,username))
            if not q.fetchone():raise HTTPException(404,'计时不存在')
            q.execute('UPDATE study_timers SET ended_at=UTC_TIMESTAMP() WHERE id=%s AND username=%s AND ended_at IS NULL',(ident,username))
        c.commit()
    finally:c.close()
    return board(username)

@router.post('/feedback')
def feedback(body:Feedback,username=Depends(get_current_user)):
    if body.corrected not in LABELS:raise HTTPException(400,'请选择有效行为')
    key=(username,body.device_id,body.frame_id)
    with REVIEW_LOCK:
        review=REVIEWS.get(key)
    if not review or time.monotonic()-review['created']>600:raise HTTPException(409,'核对窗口已过期，请重新打开')
    jpeg=review['jpeg'];result=review['result']
    digest=hashlib.sha256(jpeg).hexdigest();image_path=''
    check=get_connection()
    try:
        with check.cursor() as q:
            q.execute('SELECT id FROM study_feedback WHERE username=%s AND device_id=%s AND frame_id=%s',(username,body.device_id,body.frame_id))
            if q.fetchone():raise HTTPException(409,'这张图已保存纠正记录，请核对新的画面')
    finally:check.close()
    if body.save_image:
        root=FRAMES_DIR/datetime.now().strftime('%Y-%m-%d')/'feedback'/hashlib.sha256(username.encode()).hexdigest()[:16]
        root.mkdir(parents=True,exist_ok=True);target=root/(uuid.uuid4().hex+'.jpg');target.write_bytes(jpeg);image_path=str(target)
    c=None
    try:
        c=get_connection()
        with c.cursor() as q:q.execute('INSERT INTO study_feedback(username,device_id,frame_id,predicted,corrected,note,evidence_json,frame_sha256,image_path,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP())',(username,body.device_id,body.frame_id,result.get('learning_state','thinking'),body.corrected,body.note,json.dumps(result.get('evidence',{}),ensure_ascii=False),digest,image_path))
        c.commit()
    except Exception:
        if image_path:Path(image_path).unlink(missing_ok=True)
        raise
    finally:
        if c:c.close()
    with REVIEW_LOCK:REVIEWS.pop(key,None)
    return {'saved':True,'image_saved':body.save_image,'message':'已保存纠正记录。原始模型结果保留，不会立即改变模型或历史统计。'}

@router.get('/review/{device}/{frame}')
def review_frame(device:str,frame:str,username=Depends(get_current_user)):
    live=live_state.status(device);result=live.get('result') or {}
    jpeg=live_state.preview(device,True,frame)
    if not jpeg or result.get('frame_id')!=frame:raise HTTPException(409,'分析画面已更新，请重新打开核对窗口')
    frozen=json.loads(json.dumps(result))
    with REVIEW_LOCK:
        for key in list(REVIEWS):
            if time.monotonic()-REVIEWS[key]['created']>600:REVIEWS.pop(key)
        REVIEWS[(username,device,frame)]={'jpeg':jpeg,'result':frozen,'created':time.monotonic()}
        while len(REVIEWS)>16:REVIEWS.popitem(last=False)
    return {'predicted':result.get('learning_state','thinking'),'frame_id':frame,'image_url':'data:image/jpeg;base64,'+base64.b64encode(jpeg).decode('ascii')}


@router.get('/feedback')
def list_feedback(device_id:str='',limit:int=50,username=Depends(get_current_user)):
    """核对纠正记录：这是共享工作空间的数据，本人与共享查看账号（家长）都能看。"""
    limit=max(1,min(200,int(limit or 50)))
    c=get_connection()
    try:
        with c.cursor() as q:
            if device_id:
                q.execute('SELECT id,username,device_id,frame_id,predicted,corrected,note,image_path,created_at '
                          'FROM study_feedback WHERE device_id=%s ORDER BY id DESC LIMIT %s',(device_id,limit))
            else:
                q.execute('SELECT id,username,device_id,frame_id,predicted,corrected,note,image_path,created_at '
                          'FROM study_feedback ORDER BY id DESC LIMIT %s',(limit,))
            rows=q.fetchall()
            q.execute('SELECT COUNT(*) AS n FROM study_feedback' + (' WHERE device_id=%s' if device_id else ''),
                      (device_id,) if device_id else ())
            total=q.fetchone()['n']
    finally:c.close()
    return {'total':int(total),'items':[{'id':row['id'],'username':row['username'],'device_id':row['device_id'],'frame_id':row['frame_id'],
            'predicted':row['predicted'],'corrected':row['corrected'],'note':row['note'],
            'has_image':bool(row['image_path']),
            'created_at':row['created_at'].replace(tzinfo=timezone.utc).isoformat()} for row in rows]}


@router.get('/feedback/{ident}/image')
def feedback_image(ident:int,username=Depends(get_current_user)):
    """纠正记录里留存的对应画面；图片只允许取自本机 frames 目录。"""
    c=get_connection()
    try:
        with c.cursor() as q:
            q.execute('SELECT image_path FROM study_feedback WHERE id=%s',(ident,))
            row=q.fetchone()
    finally:c.close()
    if not row:raise HTTPException(404,'没有这条纠正记录')
    stored=(row['image_path'] or '').strip()
    if not stored:raise HTTPException(404,'这条记录提交时没有勾选“另存这张图片”，所以没有留图')
    path=Path(stored).resolve()
    root=Path(FRAMES_DIR).resolve()
    if path!=root and root not in path.parents:raise HTTPException(403,'图片不在本机画面目录内')
    if not path.is_file():raise HTTPException(404,'图片已被清理（超过保存天数会自动删除）')
    return Response(path.read_bytes(),media_type='image/jpeg',headers={'Cache-Control':'no-store'})
