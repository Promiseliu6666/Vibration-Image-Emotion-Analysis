from pathlib import Path
import os,socket,subprocess,time,shutil,json,urllib.error,urllib.request
root=Path(__file__).resolve().parent
desktop_launcher = root.parent / 'start_interactive_rest.py'
if __name__ == '__main__' and desktop_launcher.is_file():
    import sys
    sys.path.insert(0, str(desktop_launcher.parent))
    from start_interactive_rest import HOME_URL, run
    raise SystemExit(run(HOME_URL))

b=root/'ruoyi-fastapi-backend';f=root/'ruoyi-fastapi-frontend';x=root/'xiaozhi-study'
fatigue=root/'fatigue_model_bundle'
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

def http_ready(url):
 try:
  with urllib.request.urlopen(url,timeout=2) as response:
   return response.status<500
 except urllib.error.HTTPError as exc:
  return exc.code<500
 except OSError:
  return False

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

# The complete Xiaozhi backend remains a separate service on port 8000. The
# RuoYi backend proxies to it for SSO, device discovery and camera frames.
xconfig=x/'.runtime/runtime.json'
xpython=x/'.venv/Scripts/python.exe'
xmysql=x/'.runtime/mysql/bin/mysqld.exe'
if not xconfig.exists() or not xpython.exists() or not xmysql.exists():
 raise FileNotFoundError(f'Xiaozhi runtime is incomplete: {x}')
xcfg=json.loads(xconfig.read_text(encoding='utf-8-sig'))
xdb_port=int(xcfg['mysql_port'])
launch('xiaozhi-mysql',[xmysql,'--no-defaults','--basedir=.','--datadir=../mysql-data','--bind-address=127.0.0.1',f'--port={xdb_port}','--mysqlx=0','--console'],x/'.runtime/mysql',xdb_port)
for _ in range(30):
 if listening(xdb_port):break
 time.sleep(1)
if not listening(xdb_port):raise ConnectionError(f'Xiaozhi MySQL is not listening on 127.0.0.1:{xdb_port}')

launch('backend',[b/'.venv/Scripts/python.exe','app.py','--env=dev'],b,9099)
launch('xiaozhi',[xpython,'-u','main.py'],x,8000)
fatigue_python=Path(os.getenv('FATIGUE_SERVICE_PYTHON') or config_value(
 'FATIGUE_SERVICE_PYTHON',
 str(root/'.runtime/fatigue-venv/Scripts/python.exe') if (root/'.runtime/fatigue-venv/Scripts/python.exe').is_file() else r'D:\Python\environments\fatigue-sense\python.exe'
))
fatigue_port=int(config_value('FATIGUE_SERVICE_PORT','9101'))
if not fatigue_python.exists():
 raise FileNotFoundError(f'Fatigue Python environment not found: {fatigue_python}')
launch('fatigue',[fatigue_python,root/'start_fatigue.py','--host','127.0.0.1','--port',str(fatigue_port)],root,fatigue_port)
for _ in range(60):
 if http_ready('http://127.0.0.1:9099/openapi.json') and http_ready('http://127.0.0.1:8000/'):break
 time.sleep(1)
if not http_ready('http://127.0.0.1:9099/openapi.json'):print('Warning: main backend is still starting on port 9099')
if not http_ready('http://127.0.0.1:8000/'):print('Warning: Xiaozhi backend is still starting on port 8000')
# Resume only after confirming the service on port 8000 is Xiaozhi.
def xiaozhi_ready():
 try:
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  with opener.open('http://127.0.0.1:8000/openapi.json',timeout=2) as response:
   paths=json.load(response).get('paths',{})
   return all(path in paths for path in ('/api/portal/exchange','/api/camera-source/devices'))
 except (OSError,ValueError,AttributeError,TypeError):
  return False

if os.getenv("XIAOZHI_RESUME_USB", "1") != "0" and xiaozhi_ready():
 try:
  result=subprocess.run(
   [str(xpython),'-c','import json; from app.device.capture_control import resume_registered; print(json.dumps(resume_registered(), ensure_ascii=False))'],
   cwd=x,capture_output=True,text=True,encoding='utf-8',timeout=20,
   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
  )
  if result.returncode == 0:
   restored=json.loads(result.stdout.splitlines()[-1])
   print('Xiaozhi USB capture:',len(restored['collectors']),'resumed,',len(restored['errors']),'failed.')
  else:print('Warning: USB capture could not resume; check the Xiaozhi device manager.')
 except (OSError,ValueError,KeyError,IndexError,subprocess.TimeoutExpired):
  print('Warning: USB capture could not resume; check the Xiaozhi device manager.')
for _ in range(20):
 if http_ready(f'http://127.0.0.1:{fatigue_port}/health'):break
 time.sleep(.5)
if not http_ready(f'http://127.0.0.1:{fatigue_port}/health'):print(f'Warning: fatigue service is still starting on port {fatigue_port}')
node_path=shutil.which('node')
if not node_path:raise FileNotFoundError('Node.js was not found on PATH.')
node=Path(node_path)
launch('frontend',[node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort','--open','false'],f,5173)
print('http://127.0.0.1:5173/')
print('Backend may take a moment to load. Logs:',logs)
