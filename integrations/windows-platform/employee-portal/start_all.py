from pathlib import Path
import os,socket,subprocess,json,time,sys
root=Path(__file__).resolve().parent
vib=root.parent/'Vibration-Image-Emotion-Analysis-main'
xiao=Path(r'C:\Users\21982\Desktop\student-monitor-show\student-monitor-show')
logs=root/'logs';logs.mkdir(exist_ok=True)
def listening(port):
 try:
  with socket.create_connection(('127.0.0.1',port),timeout=1):return True
 except OSError:return False
def launch(name,args,cwd,port):
 if listening(port):print(name,'already running',flush=True);return
 out=open(logs/(name+'.out.log'),'a',encoding='utf-8');err=open(logs/(name+'.err.log'),'a',encoding='utf-8')
 p=subprocess.Popen([str(a) for a in args],cwd=cwd,stdout=out,stderr=err,creationflags=0x08000000)
 print(name,'started',p.pid,flush=True)
os.environ['DOTNET_ROOT']=str(vib/'.runtime/dotnet')
os.environ['PADDLE_PDX_CACHE_HOME']=str(vib/'.runtime/paddlex')
os.environ['PYTHONIOENCODING']='utf-8'
os.environ['API_HOST']='127.0.0.1'
vp=vib/'ruoyi-fastapi-backend/.venv/Scripts/python.exe'
subprocess.run([str(vp),str(vib/'start_local.py')],cwd=vib,check=True)
cfg=json.loads((xiao/'.runtime/runtime.json').read_text(encoding='utf-8-sig'))
if not listening(cfg['mysql_port']):
 launch('xiaozhi-db',[xiao/'.runtime/mysql/bin/mysqld.exe','--no-defaults','--basedir=.','--datadir=../mysql-data','--bind-address=127.0.0.1',f"--port={cfg['mysql_port']}",'--mysqlx=0','--console'],xiao/'.runtime/mysql',cfg['mysql_port'])
for _ in range(40):
 if listening(cfg['mysql_port']):break
 time.sleep(1)
launch('xiaozhi',[xiao/'.venv/Scripts/python.exe','-u','main.py'],xiao,8000)
launch('portal',[vp,'server.py'],root,8800)
print('Health monitoring: http://127.0.0.1:5173/',flush=True)
if '--keep-alive' in sys.argv:
 while True:time.sleep(15)
