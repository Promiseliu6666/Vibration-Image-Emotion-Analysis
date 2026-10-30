import asyncio
import csv
import io
import ipaddress
import os
import re
import secrets
import shutil
import socket
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response
from pydantic import BaseModel,Field
import psutil
from app.core import access_control as access
from app.core import site_settings
from app.api.api_router import get_current_user
from app.core.db import get_connection
from app.core.paths import PROJECT_ROOT

router=APIRouter(prefix='/api/workspace',dependencies=[Depends(get_current_user)])
STARTED=time.monotonic()

def local(request):
    if not request.client or request.client.host not in ('127.0.0.1','::1'):
        raise HTTPException(403,'请在服务器电脑上更改部署设置')

@router.get('/me')
def me(username=Depends(get_current_user)):
    row=access.user(username)
    return {'username':username,'role':row['role'],'must_change_password':bool(row['must_change'])}

class Password(BaseModel):
    current_password:str=Field(max_length=72)
    new_password:str=Field(min_length=10,max_length=72)

@router.post('/password')
def password(body:Password,request:Request,username=Depends(get_current_user)):
    row=access.user(username)
    if not access.passwords.verify(body.current_password,row['password_hash']):raise HTTPException(400,'当前密码不正确')
    access.valid_password(body.new_password)
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE workspace_users SET password_hash=%s,must_change=0,token_version=token_version+1 WHERE username=%s',
                        (access.passwords.hash(body.new_password),username))
        conn.commit()
    finally:conn.close()
    return access.login(username,body.new_password,request.client.host if request.client else 'local')

@router.get('/accounts')
def accounts(username=Depends(get_current_user)):
    access.admin(username);conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT username,role,enabled,created_at FROM workspace_users ORDER BY created_at');rows=cur.fetchall()
        return rows
    finally:conn.close()

class Account(BaseModel):
    username:str=Field(min_length=3,max_length=32,pattern=r'^[A-Za-z0-9_-]+$')
    password:str=Field(min_length=10,max_length=72)

@router.post('/accounts',status_code=201)
def add_account(body:Account,username=Depends(get_current_user)):
    access.admin(username);access.valid_password(body.password)
    if access.user(body.username):raise HTTPException(409,'用户名已存在')
    conn=get_connection()
    try:
        with conn.cursor() as cur:cur.execute('INSERT INTO workspace_users(username,password_hash,role,must_change) VALUES(%s,%s,%s,0)',(body.username,access.passwords.hash(body.password),'viewer'))
        conn.commit()
    finally:conn.close()
    return {'username':body.username,'role':'viewer'}

class Enabled(BaseModel):enabled:bool

@router.patch('/accounts/{target}')
def set_account(target:str,body:Enabled,username=Depends(get_current_user)):
    access.admin(username);row=access.user(target)
    if not row:raise HTTPException(404,'账号不存在')
    if row['role']=='admin':raise HTTPException(400,'不能停用管理员账号')
    conn=get_connection()
    try:
        with conn.cursor() as cur:cur.execute('UPDATE workspace_users SET enabled=%s,token_version=token_version+1 WHERE username=%s',(int(body.enabled),target))
        conn.commit()
    finally:conn.close()
    return {'enabled':body.enabled}

@router.get('/settings')
def settings():return site_settings.read()

class Settings(BaseModel):
    """局部更新：网页把设置拆成了两张卡，各自只提交自己那几个字段。"""
    lan_enabled:bool|None=None
    frame_retention_days:int|None=Field(default=None,ge=1,le=90)
    save_all_frames:bool|None=None

@router.put('/settings')
def save_settings(body:Settings,request:Request,username=Depends(get_current_user)):
    row=access.admin(username);local(request)
    current=site_settings.read()
    merged={key:(current.get(key) if value is None else value) for key,value in body.model_dump().items()}
    if merged['lan_enabled'] and row['must_change']:raise HTTPException(409,'请先更改默认管理员密码，再启用局域网访问')
    return {'settings':site_settings.write(merged),'restart_required':True}


def frame_stats(days:int|None=None):
    """统计本机画面：普通图片按保存天数分成"会保留"和"会被清理"，提醒截图与纠正图长期保留。

    days 为空时用已保存的保存天数；带上 days 就是按这个范围试算（右侧实时预览用）。
    """
    from app.core.config import FRAME_SAVE_DIR, FRAME_RETENTION_DAYS
    retention_days=max(1,min(90,int(days))) if days else FRAME_RETENTION_DAYS
    root=Path(FRAME_SAVE_DIR)
    cutoff=time.time()-retention_days*86400
    files=0;files_bytes=0;alert_files=0;alert_bytes=0
    expired=0;expired_bytes=0;kept=0;kept_bytes=0;oldest=None;newest=None
    if root.is_dir():
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            try:stat=path.stat()
            except OSError:continue
            if 'alerts' in path.parts or 'feedback' in path.parts:
                alert_files+=1;alert_bytes+=stat.st_size
                continue
            files+=1;files_bytes+=stat.st_size
            if stat.st_mtime<cutoff:
                expired+=1;expired_bytes+=stat.st_size
            else:
                kept+=1;kept_bytes+=stat.st_size
            oldest=stat.st_mtime if oldest is None else min(oldest,stat.st_mtime)
            newest=stat.st_mtime if newest is None else max(newest,stat.st_mtime)
    def stamp(value):return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M') if value else None
    return {'files':files,'files_mb':round(files_bytes/1024**2,1),'alert_files':alert_files,'alert_mb':round(alert_bytes/1024**2,1),
            'expired_files':expired,'expired_mb':round(expired_bytes/1024**2,1),
            'kept_files':kept,'kept_mb':round(kept_bytes/1024**2,1),
            'retention_days':retention_days,'oldest':stamp(oldest),'newest':stamp(newest)}


@router.get('/frames')
def frames(days:int|None=None,username=Depends(get_current_user)):
    """days 为空时用已保存的保存天数；带上 days 就是"按这个范围试算"，用于右侧实时预览。"""
    access.admin(username)
    return frame_stats(days)


FRAME_CLEANUP_JOB={'state':'idle','deleted_files':0,'deleted_rows':0,'started':0.0,'finished':0.0,'error':None}


@router.post('/frames/cleanup')
async def cleanup_frames(request:Request,username=Depends(get_current_user)):
    """删除过期图片的耗时取决于要删多少张，可能超过网页默认等待时间，
    所以这里立刻返回、后台继续删，前端轮询结果。"""
    access.admin(username);local(request)
    if FRAME_CLEANUP_JOB['state']=='running':raise HTTPException(409,'正在清理，请稍候')
    from app.analysis.analysis_storage import cleanup_expired_frames
    FRAME_CLEANUP_JOB.update(state='running',deleted_files=0,deleted_rows=0,started=time.time(),finished=0.0,error=None)
    async def run():
        try:
            files,rows=await asyncio.to_thread(cleanup_expired_frames)
            FRAME_CLEANUP_JOB.update(state='done',deleted_files=files,deleted_rows=rows,finished=time.time())
        except Exception as error:
            FRAME_CLEANUP_JOB.update(state='done',error=str(error),finished=time.time())
    asyncio.create_task(run())
    return {'state':'running','message':'正在清理过期图片'}


@router.get('/frames/cleanup')
def cleanup_status(username=Depends(get_current_user)):
    access.admin(username)
    return dict(FRAME_CLEANUP_JOB)


WIRELESS_JOB={'state':'idle','result':None,'error':None,'started':0.0}


class WirelessSetup(BaseModel):
    """expected_device_id：从某台设备的卡片点进来时带上它，避免把别台设备接到这条记录上。"""
    expected_device_id:str|None=Field(default=None,max_length=64)


@router.post('/wireless-setup')
async def wireless_setup(request:Request,body:WirelessSetup|None=None,username=Depends(get_current_user)):
    """点一下把整套无线接入做完：读 MAC → 登记 → 生成密钥 → 写进设备。

    串口读写要十几秒，超过网页默认的 15 秒等待，所以这里立刻返回、后台继续跑，
    前端用 GET 轮询结果。
    """
    access.admin(username);local(request)
    if WIRELESS_JOB['state']=='running':raise HTTPException(409,'正在接入，请稍候')
    from app.core import wireless_setup as setup
    WIRELESS_JOB.update(state='running',result=None,error=None,started=time.time())
    async def run():
        expected=body.expected_device_id if body else None
        try:WIRELESS_JOB.update(state='done',result=await asyncio.to_thread(setup.provision,expect_device_id=expected))
        except RuntimeError as error:WIRELESS_JOB.update(state='done',error=str(error))
        except Exception as error:WIRELESS_JOB.update(state='done',error=f'服务端出错：{error}')
    asyncio.create_task(run())
    return {'state':'running','message':'正在接入，请保持 USB 连接'}


@router.get('/wireless-setup')
def wireless_setup_status(username=Depends(get_current_user)):
    access.admin(username)
    return dict(WIRELESS_JOB)

@router.get('/system')
def system(username=Depends(get_current_user)):
    access.admin(username)
    from app.core.config import API_PORT
    from app.api.ws_handler import frame_queue
    addresses=[]
    for nic,items in psutil.net_if_addrs().items():
        for item in items:
            if item.family==socket.AF_INET:
                ip=ipaddress.ip_address(item.address)
                if not ip.is_loopback and not ip.is_link_local and ip.is_private:addresses.append({'adapter':nic,'url':f'http://{ip}:{API_PORT}'})
    conn=get_connection()
    try:
        with conn.cursor() as cur:cur.execute('SELECT 1');cur.fetchone()
    finally:conn.close()
    disk=shutil.disk_usage(PROJECT_ROOT)
    return {'database':'ok','uptime_seconds':round(time.monotonic()-STARTED),'queue_used':frame_queue.qsize(),'queue_capacity':frame_queue.maxsize,
            'free_disk_gb':round(disk.free/1024**3,1),'addresses':addresses,'lan_listening':getattr(site_settings,'RUNNING_HOST','127.0.0.1')=='0.0.0.0',
            'saved_lan_enabled':site_settings.read()['lan_enabled']}

@router.get('/network-devices')
def network_devices(username=Depends(get_current_user)):
    access.admin(username);conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT c.device_id,c.hardware_id,c.enabled,c.last_seen,c.received_frames,d.name FROM device_credentials c JOIN devices d ON d.device_id=c.device_id ORDER BY c.created_at DESC');rows=cur.fetchall()
        now=datetime.now(timezone.utc).replace(tzinfo=None)
        for row in rows:
            row['network_online']=bool(row['last_seen'] and (now-row['last_seen']).total_seconds()<30)
            row['last_seen']=row['last_seen'].replace(tzinfo=timezone.utc).isoformat() if row['last_seen'] else None
            from app.core import live_state
            row['live']=live_state.status(row['device_id'])
        return rows
    finally:conn.close()

class Pair(BaseModel):
    hardware_id:str=Field(min_length=12,max_length=32)
    name:str=Field(min_length=1,max_length=64)
    existing_device_id:str|None=None

@router.post('/network-devices')
def pair(body:Pair,username=Depends(get_current_user)):
    access.admin(username)
    hardware=body.hardware_id.replace(':','').replace('-','').upper()
    if not re.fullmatch('[0-9A-F]{12}',hardware) or hardware=='000000000000':raise HTTPException(400,'请输入设备真实 MAC 地址，例如 AA:BB:CC:DD:EE:FF')
    token=secrets.token_urlsafe(32);conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT device_id FROM device_credentials WHERE hardware_id=%s',(hardware,));existing=cur.fetchone()
            device_id=existing['device_id'] if existing else (body.existing_device_id or 'watcher-'+hardware)
            if body.existing_device_id and existing and existing['device_id']!=body.existing_device_id:raise HTTPException(409,'该物理设备已经关联另一条记录')
            cur.execute('SELECT id FROM devices WHERE device_id=%s',(device_id,));found=cur.fetchone()
            if body.existing_device_id and not found:raise HTTPException(404,'要关联的设备不存在')
            cur.execute('SELECT hardware_id FROM device_credentials WHERE device_id=%s',(device_id,));bound=cur.fetchone()
            if bound and bound['hardware_id']!=hardware:raise HTTPException(409,'此设备记录已关联其他物理设备')
            if not found:cur.execute('INSERT INTO devices(device_id,name,bind_code,created_at) VALUES(%s,%s,%s,UTC_TIMESTAMP())',(device_id,body.name.strip(),''))
            cur.execute('INSERT INTO device_credentials(device_id,hardware_id,key_hash,enabled) VALUES(%s,%s,%s,1) ON DUPLICATE KEY UPDATE key_hash=VALUES(key_hash),enabled=1',(device_id,hardware,access.key_hash(token)))
        conn.commit()
    finally:conn.close()
    from app.device import device_registry
    device_registry.set_blocked(device_id,False)
    return {'device_id':device_id,'device_key':token,'hardware_id':hardware,'upload_path':'/api/device/frame','vision_path':'/vision/explain','heartbeat_path':'/api/device/heartbeat'}

@router.patch('/network-devices/{device_id}')
def revoke(device_id:str,body:Enabled,username=Depends(get_current_user)):
    access.admin(username);conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE device_credentials SET enabled=%s WHERE device_id=%s',(int(body.enabled),device_id))
            if not cur.rowcount:
                cur.execute('SELECT device_id FROM device_credentials WHERE device_id=%s',(device_id,))
                if not cur.fetchone():raise HTTPException(404,'网络设备不存在')
        conn.commit()
    finally:conn.close()
    return {'enabled':body.enabled}

@router.get('/export')
def export(device_id:str,from_date:str,to_date:str):
    try:
        start=datetime.strptime(from_date,'%Y-%m-%d');end=datetime.strptime(to_date,'%Y-%m-%d')+timedelta(days=1)
    except ValueError:raise HTTPException(400,'请输入有效日期')
    if end<=start or end-start>timedelta(days=90):raise HTTPException(400,'导出范围需为 1 至 90 天')
    # User dates mean China local calendar dates; stored timestamps are UTC.
    start-=timedelta(hours=8);end-=timedelta(hours=8)
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT a.timestamp,a.learning_state,a.fatigue_level,a.distraction_level,a.difficulty_indicator,a.person_present
                           FROM analysis_results a JOIN sessions s ON a.session_id=s.id
                           WHERE s.device_id=%s AND a.timestamp>=%s AND a.timestamp<%s ORDER BY a.timestamp LIMIT 50001''',(device_id,start,end));rows=cur.fetchall()
    finally:conn.close()
    if len(rows)>50000:raise HTTPException(413,'记录超过五万条，请缩小日期范围后导出')
    output=io.StringIO();writer=csv.writer(output);writer.writerow(['时间（北京时间）','学习状态','疲劳指标','分心指标','困难指标','是否有人'])
    for row in rows:
        state=row['learning_state'] or ''
        if state.startswith(('=','+','-','@')):state="'"+state
        writer.writerow([(row['timestamp']+timedelta(hours=8)).isoformat(' '),state,row['fatigue_level'],row['distraction_level'],row['difficulty_indicator'],row['person_present']])
    return Response(output.getvalue().encode('utf-8-sig'),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="learning-records.csv"','Cache-Control':'no-store'})
