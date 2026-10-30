"""Independent USB collectors keyed by verified physical USB serial."""
import json,subprocess,sys,time,os
from pathlib import Path
from threading import RLock
import psutil
from app.device import usb_identity
from app.core.paths import PROJECT_ROOT,RUNTIME_DIR
ROOT=PROJECT_ROOT;SCRIPT=ROOT/'watcher_usb.py';PID=RUNTIME_DIR/'watcher-usb.pid';REGISTRY=RUNTIME_DIR/'usb-collectors.json';_lock=RLock()
def _load():
 try:return json.loads(REGISTRY.read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}
def _save(items):
 REGISTRY.parent.mkdir(exist_ok=True);temp=REGISTRY.with_suffix('.tmp');temp.write_text(json.dumps(items,ensure_ascii=False),encoding='utf-8');temp.replace(REGISTRY)
def _process(pid):
 try:
  p=psutil.Process(int(pid))
  if not any(Path(a).resolve()==SCRIPT for a in p.cmdline()[1:] if not a.startswith('-')):return None
  return p if p.is_running() else None
 except (ValueError,OSError,psutil.Error,TypeError):return None
def _items():
 items=_load()
 try:
  pid=int(PID.read_text(encoding='utf-8-sig'));p=_process(pid);legacy=usb_identity.read_state();identity=legacy.get('identity') or {};serial=identity.get('usb_serial')
  if p and serial and serial not in items:items[serial]={'pid':pid,'port':legacy.get('port'),'device_id':identity.get('device_id'),'legacy':True}
 except (OSError,ValueError):pass
 return items
def _rows():
 items=_items();ports=usb_identity.camera_ports();rows=[]
 for serial,item in items.items():
  p=_process(item.get('pid'));state=usb_identity.read_state(serial)
  if not state and item.get('legacy'):state=usb_identity.read_state()
  identity=state.get('identity') or {};valid_pids=set()
  if p:
   valid_pids.add(p.pid)
   try:valid_pids.update(child.pid for child in p.children(recursive=True) if any(Path(a).resolve()==SCRIPT for a in child.cmdline()[1:] if not a.startswith('-')))
   except (psutil.Error,OSError):pass
  valid=bool(p and state.get('pid') in valid_pids and state.get('updated_at',0)>=p.create_time() and state.get('connected') and time.time()-state.get('updated_at',0)<20 and identity.get('usb_serial')==serial and any(q.device==state.get('port') and q.serial_number==serial for q in ports))
  if valid:item.update(device_id=identity.get('device_id'),port=state.get('port'))
  rows.append(dict(running=p is not None,collector_pid=p.pid if p else None,device_id=item.get('device_id'),identity=identity if valid else None,port=item.get('port'),usb_serial=serial,identified=valid,error=state.get('error'),capture_fps=state.get('capture_fps')))
 if items!=_load():_save(items)
 return rows,ports,items
def status(device_id=None,port=None):
 with _lock:
  rows,ports,_=_rows()
  chosen=next((r for r in rows if r.get('device_id')==device_id),None) if device_id else next((r for r in rows if r['port']==port),None) if port else next((r for r in rows if r['identified']),next((r for r in rows if r['running']),None))
  chosen=chosen or dict(running=False,collector_pid=None,device_id=device_id,identity=None,port=None,identified=False,error=None)
  return {**chosen,'available':bool(ports),'ports':[p.device for p in ports],'candidates':[dict(port=p.device,usb_serial=p.serial_number,label=f'{p.device} · USB {p.serial_number or "未知序列号"}') for p in ports],'collectors':rows,'by_device':{r['device_id']:r for r in rows if r.get('device_id')}}
def process(device_id=None):return _process(status(device_id).get('collector_pid'))
def _stop(current):
 if current:
  children=current.children(recursive=True)
  for p in children+[current]:
   try:p.terminate()
   except psutil.NoSuchProcess:pass
  _,alive=psutil.wait_procs(children+[current],timeout=5)
  if alive:raise RuntimeError('采集进程仍在退出，请稍后重试')
def set_running(enabled,port=None,device_id=None):
 with _lock:
  rows,ports,items=_rows()
  if not enabled:
   targets=[r for r in rows if (r.get('device_id')==device_id if device_id else r['port']==port if port else True)]
   for row in targets:
    _stop(_process(row.get('collector_pid')));items[row['usb_serial']]={**items.get(row['usb_serial'],{}),'pid':None,'port':row['port'],'device_id':row.get('device_id')}
    try:
     if int(PID.read_text(encoding='utf-8-sig'))==row.get('collector_pid'):PID.unlink(missing_ok=True)
    except (OSError,ValueError):pass
   _save(items);return status(device_id)
  if not port and device_id:port=next((r['port'] for r in rows if r.get('device_id')==device_id),None)
  if not port:
   if len(ports)==1:port=ports[0].device
   elif not ports:raise ValueError('没有发现 USB 摄像头，请检查数据线')
   else:raise ValueError('发现多台 USB 摄像头，请选择设备端口；已运行的设备会继续采集')
  physical=next((p for p in ports if p.device==port),None)
  if not physical:raise ValueError('所选 USB 摄像头已断开')
  serial=usb_identity.normalize(physical.serial_number)
  current=items.get(serial)
  if current and _process(current.get('pid')) and current.get('port')==port:return status(device_id,port)
  # Only replace a stale collector for this serial/port; all other devices stay alive.
  for key,item in list(items.items()):
   if key==serial or item.get('port')==port:_stop(_process(item.get('pid')));items.pop(key,None)
  RUNTIME_DIR.mkdir(exist_ok=True);tag=serial.lower()
  with (RUNTIME_DIR/f'watcher-{tag}.log').open('ab') as out,(RUNTIME_DIR/f'watcher-{tag}-error.log').open('ab') as err:
   child=subprocess.Popen([sys.executable,'-u',str(SCRIPT),'--port',port,'--usb-serial',serial,'--restore'],cwd=ROOT,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  items[serial]={'pid':child.pid,'port':port,'device_id':device_id};_save(items)
 return status(device_id,port)
