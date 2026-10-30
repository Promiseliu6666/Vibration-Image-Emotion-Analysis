"""Initialize a clean bundled database without copying private user data."""
import json
import secrets
import socket
import subprocess
import time
from pathlib import Path
import pymysql
ROOT=Path(__file__).resolve().parent
runtime=ROOT/'.runtime'
config=runtime/'runtime.json'
if config.exists():
    raise SystemExit(0)
mysql=runtime/'mysql';data=runtime/'mysql-data'
port=3307
while True:
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',port));break
        except OSError:port+=1
    if port>3399:raise RuntimeError('No available local database port')
password=secrets.token_hex(24)
if not (data/'mysql').exists():
    data.mkdir(exist_ok=True)
    subprocess.run(['mysqld.exe','--no-defaults','--basedir=.','--datadir=../mysql-data','--initialize-insecure'],check=True,cwd=mysql,executable=str(mysql/'bin/mysqld.exe'),creationflags=subprocess.CREATE_NO_WINDOW)
with (runtime/'bootstrap-mysql.log').open('ab') as log:
    server=subprocess.Popen(['mysqld.exe','--no-defaults','--basedir=.','--datadir=../mysql-data','--bind-address=127.0.0.1',f'--port={port}','--mysqlx=0','--console'],stdout=log,stderr=log,cwd=mysql,executable=str(mysql/'bin/mysqld.exe'),creationflags=subprocess.CREATE_NO_WINDOW)
    connection=None
    try:
        for attempt in range(60):
            try:connection=pymysql.connect(host='127.0.0.1',port=port,user='root',password='',autocommit=True);break
            except pymysql.OperationalError:time.sleep(1)
        if connection is None:raise RuntimeError('Database initialization timed out')
        with connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE IF NOT EXISTS student_monitor CHARACTER SET utf8mb4')
            cursor.execute('USE student_monitor')
            cursor.execute('SET FOREIGN_KEY_CHECKS=0')
            for statement in json.loads((runtime/'schema.json').read_text(encoding='utf-8')):cursor.execute(statement)
            cursor.execute('SET FOREIGN_KEY_CHECKS=1')
            cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s",(password,))
            config.write_text(json.dumps({'mysql_port':port,'mysql_password':password,'mysql_database':'student_monitor'},indent=2),encoding='utf-8')
            cursor.execute('SHUTDOWN')
        print('Clean local database initialized; start the project normally.')
    finally:
        if connection:connection.close()
        try:server.wait(timeout=20)
        except subprocess.TimeoutExpired:server.terminate();server.wait(timeout=10)
