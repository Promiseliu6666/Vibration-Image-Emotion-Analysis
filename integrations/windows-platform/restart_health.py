from pathlib import Path
import subprocess,time,psutil
root=Path(__file__).resolve().parent
v=root/'Vibration-Image-Emotion-Analysis-main'
x=Path(r'C:\Users\21982\Desktop\student-monitor-show\student-monitor-show')
targets={str(root/'employee-portal').lower():'server.py',str(v/'ruoyi-fastapi-backend').lower():'app.py',str(x).lower():'main.py'}
stopped=[]
for proc in psutil.process_iter(['pid','name']):
 if proc.info['name'].lower() not in ('python.exe','pythonw.exe'):continue
 try:
  expected=targets.get(str(Path(proc.cwd())).lower())
  if expected and any(Path(arg).name.lower()==expected for arg in proc.cmdline()[1:]):
   proc.terminate();stopped.append(proc)
 except (psutil.Error,OSError):pass
_,alive=psutil.wait_procs(stopped,timeout=8)
for proc in alive:
 try:proc.kill()
 except psutil.Error:pass
time.sleep(1)
subprocess.run([str(v/'ruoyi-fastapi-backend/.venv/Scripts/python.exe'),'start_all.py'],cwd=root/'employee-portal',check=True)
print('Platform restarted. Open http://127.0.0.1:5173/')
