from pathlib import Path
import os,socket,subprocess,time,shutil
root=Path(__file__).resolve().parent
b=root/'ruoyi-fastapi-backend';f=root/'ruoyi-fastapi-frontend'
logs=root/'.runtime/logs';logs.mkdir(parents=True,exist_ok=True)
dotnet=root/'.runtime/dotnet'
if dotnet.exists():os.environ['DOTNET_ROOT']=str(dotnet)
os.environ['PADDLE_PDX_CACHE_HOME']=str(root/'.runtime/paddlex')
os.environ['PYTHONIOENCODING']='utf-8'

def config_value(name,default):
 text=(b/'.env.dev').read_text(encoding='utf-8')
 for line in text.splitlines():
  key,sep,value=line.partition('=')
  if sep and key.strip()==name:
   return value.strip().strip('\'"')
 return default

def listening(port):
 try:
  with socket.create_connection(('127.0.0.1',port),timeout=1): return True
 except OSError: return False

def launch(name,args,cwd,port):
 if listening(port): print(name,'already running');return
 executable=Path(args[0])
 if not executable.exists():
  raise FileNotFoundError(f'{name} executable not found: {executable}')
 out=open(logs/(name+'.out.log'),'a',encoding='utf-8');err=open(logs/(name+'.err.log'),'a',encoding='utf-8')
 proc=subprocess.Popen([str(a) for a in args],cwd=cwd,stdout=out,stderr=err,creationflags=0x08000000)
 print(name,'started',proc.pid)

db_port=int(config_value('DB_PORT','3306'));cache_port=int(config_value('REDIS_PORT','6379'))
bundled_mysql=root/'.runtime/mariadb/bin/mariadbd.exe'
bundled_cache=root/'.runtime/garnet/net10.0/GarnetServer.exe'
if db_port==13306 and bundled_mysql.exists():
 launch('mysql',[bundled_mysql,'--defaults-file='+str(root/'.runtime/data/my.ini'),'--bind-address=127.0.0.1','--port=13306'],root,13306)
elif db_port==13306:
 raise FileNotFoundError('Bundled MySQL is missing; set DB_PORT to a running MySQL service.')
if cache_port==16379 and bundled_cache.exists():
 launch('cache',[bundled_cache,'--port','16379','--bind','127.0.0.1'],root,16379)
elif cache_port==16379:
 raise FileNotFoundError('Bundled cache is missing; set REDIS_PORT to a running Redis service.')
for name,port in [('MySQL',db_port),('Redis',cache_port)]:
 for _ in range(30):
  if listening(port):break
  time.sleep(1)
 if not listening(port):raise ConnectionError(f'{name} is not listening on 127.0.0.1:{port}')

launch('backend',[b/'.venv/Scripts/python.exe','app.py','--env=dev'],b,9099)
node_path=shutil.which('node')
if not node_path:raise FileNotFoundError('Node.js was not found on PATH.')
node=Path(node_path)
launch('frontend',[node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort','--open','false'],f,5173)
print('http://127.0.0.1:5173/')
print('Backend may take a moment to load. Logs:',logs)
