"""Persistent accounts for one shared, small-group learning workspace."""
import hashlib
import re
import secrets
import time
from collections import OrderedDict
from threading import RLock
from datetime import datetime,timedelta,timezone
from fastapi import HTTPException
from jose import jwt,JWTError
from passlib.context import CryptContext
from app.core.db import get_connection
from app.core.config import ADMIN_USERNAME,ADMIN_PASSWORD,JWT_SECRET,JWT_ALGORITHM,JWT_EXPIRE_MINUTES

passwords=CryptContext(schemes=['bcrypt'],deprecated='auto')
_attempts=OrderedDict();_lock=RLock()

def schema():
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS workspace_users (
                username VARCHAR(64) PRIMARY KEY,password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(16) NOT NULL,enabled TINYINT NOT NULL DEFAULT 1,
                token_version INT NOT NULL DEFAULT 0,must_change TINYINT NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4''')
            cur.execute('''CREATE TABLE IF NOT EXISTS device_credentials (
                device_id VARCHAR(64) PRIMARY KEY,hardware_id VARCHAR(128) NOT NULL,
                key_hash CHAR(64) NOT NULL,enabled TINYINT NOT NULL DEFAULT 1,
                last_seen DATETIME NULL,received_frames BIGINT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4''')
            cur.execute('SELECT username FROM workspace_users WHERE username=%s',(ADMIN_USERNAME,))
            if not cur.fetchone():
                cur.execute('INSERT INTO workspace_users(username,password_hash,role,must_change) VALUES(%s,%s,%s,%s)',
                            (ADMIN_USERNAME,passwords.hash(ADMIN_PASSWORD),'admin',int(ADMIN_PASSWORD=='admin123' or len(ADMIN_PASSWORD)<10)))
        conn.commit()
    finally:conn.close()

def user(username):
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM workspace_users WHERE username=%s',(username,));return cur.fetchone()
    finally:conn.close()

def admin(username):
    row=user(username)
    if not row or not row['enabled'] or row['role']!='admin':raise HTTPException(403,'只有管理员可以执行此操作')
    return row

def decode(token):
    try:
        payload=jwt.decode(token,JWT_SECRET,algorithms=[JWT_ALGORITHM]);row=user(payload.get('sub',''))
        if not row or not row['enabled'] or payload.get('ver',0)!=row['token_version']:raise HTTPException(401,'登录已失效，请重新登录')
        return row['username']
    except JWTError:raise HTTPException(401,'登录已失效，请重新登录')

def login(username,password,address):
    now=time.monotonic()
    with _lock:
        history=[t for t in _attempts.get(address,[]) if now-t<300]
        if len(history)>=8:raise HTTPException(429,'登录尝试过于频繁，请五分钟后重试')
        history.append(now);_attempts[address]=history;_attempts.move_to_end(address)
        while len(_attempts)>1024:_attempts.popitem(last=False)
    row=user(username)
    if not isinstance(password,str) or len(password.encode())>72 or not row or not row['enabled'] or not passwords.verify(password,row['password_hash']):
        raise HTTPException(401,'用户名或密码错误')
    with _lock:_attempts.pop(address,None)
    token=jwt.encode({'sub':username,'ver':row['token_version'],'exp':datetime.now(timezone.utc)+timedelta(minutes=JWT_EXPIRE_MINUTES)},JWT_SECRET,algorithm=JWT_ALGORITHM)
    return {'access_token':token,'token_type':'bearer','role':row['role'],'must_change_password':bool(row['must_change'])}

def valid_password(value):
    if len(value)<10 or len(value.encode())>72:raise HTTPException(400,'密码需至少 10 个字符，且不超过 72 字节')
    if value.lower() in ('admin12345','1234567890','password123'):raise HTTPException(400,'请使用不易猜测的密码')

def key_hash(value):return hashlib.sha256(value.encode()).hexdigest()

def device(token):
    if not token or len(token)>256:raise HTTPException(401,'需要有效的设备接入密钥')
    conn=get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT c.* FROM device_credentials c JOIN devices d ON c.device_id=d.device_id WHERE c.key_hash=%s AND c.enabled=1',(key_hash(token),));row=cur.fetchone()
    finally:conn.close()
    if not row:raise HTTPException(401,'设备密钥无效或已撤销')
    from app.device import device_registry
    if device_registry.blocked(row['device_id']):raise HTTPException(409,'该设备已删除')
    return row

def seen(device_id,frame=False):
    conn=get_connection()
    try:
        with conn.cursor() as cur:cur.execute('UPDATE device_credentials SET last_seen=UTC_TIMESTAMP(),received_frames=received_frames+%s WHERE device_id=%s',(int(frame),device_id))
        conn.commit()
    finally:conn.close()
