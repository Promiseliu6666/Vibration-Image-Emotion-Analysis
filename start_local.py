from pathlib import Path
import os,socket,subprocess,time
root=Path(__file__).resolve().parent
logs=root/'.runtime/logs';logs.mkdir(exist_ok=True)
os.environ['DOTNET_ROOT']=str(root/'.runtime/dotnet')
os.environ['PADDLE_PDX_CACHE_HOME']=str(root/'.runtime/paddlex')
def listening(port):
 try:
  with socket.create_connection(('127.0.0.1',port),timeout=1): return True
 except OSError: return False
def launch(name,args,cwd,port):
 if listening(port): print(name,'already running');return
 out=open(logs/(name+'.out.log'),'a',encoding='utf-8');err=open(logs/(name+'.err.log'),'a',encoding='utf-8')
 proc=subprocess.Popen([str(a) for a in args],cwd=cwd,stdout=out,stderr=err,creationflags=0x08000000)
 print(name,'started',proc.pid)
launch('mysql',[root/'.runtime/mariadb/bin/mariadbd.exe','--defaults-file='+str(root/'.runtime/data/my.ini'),'--bind-address=127.0.0.1','--port=13306'],root,13306)
launch('cache',[root/'.runtime/garnet/net10.0/GarnetServer.exe','--port','16379','--bind','127.0.0.1'],root,16379)
for _ in range(60):
 if listening(13306) and listening(16379):break
 time.sleep(1)
b=root/'ruoyi-fastapi-backend';f=root/'ruoyi-fastapi-frontend'
launch('backend',[b/'.venv/Scripts/python.exe','app.py','--env=dev'],b,9099)
node=Path(r'C:\Users\21982\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
launch('frontend',[node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort','--open','false'],f,5173)
print('http://127.0.0.1:5173/   admin / admin123')
print('Backend may take a moment to load. Logs:',logs)
