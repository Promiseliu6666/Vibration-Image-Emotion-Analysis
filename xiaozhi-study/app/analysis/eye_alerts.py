"""Device voice only; no browser warning and no computer speech."""
import asyncio,time
from collections import OrderedDict
from app.analysis import device_voice
from app.analysis.phone_alerts import play_usb
class EyeAlerts:
    def __init__(self): self.devices=OrderedDict();self.tasks=set()
    def observe(self,device,result,fresh=True,enabled=True,interval_seconds=1200):
        interval_seconds=max(60,int(interval_seconds))
        o=(result.get('evidence') or {}).get('observations') or {}
        entry=self.devices.setdefault(device,dict(next_seconds=interval_seconds,last_try=0,status='waiting',last_seconds=0,busy=False,generation=0,interval_seconds=interval_seconds))
        self.devices.move_to_end(device)
        while len(self.devices)>64:self.devices.popitem(last=False)
        seconds=float(o.get('screen_seconds') or 0)
        interval_changed=entry.get('interval_seconds')!=interval_seconds
        entry['interval_seconds']=interval_seconds
        if interval_changed:entry['next_seconds']=seconds+interval_seconds
        if not enabled:
            entry.update(status='disabled',busy=False)
            return {'status':'disabled','interval_minutes':round(interval_seconds/60)}
        if seconds<entry['last_seconds']:
            entry.update(next_seconds=interval_seconds,generation=entry['generation']+1,status='waiting')
        entry['last_seconds']=seconds
        if device_voice.plays(device):
            # 固件按 study_sync 传过去的屏幕累计分钟自己判断用眼提醒；服务端不再重复播报。
            entry.update(status='device',busy=False)
            return {'status':'device','interval_minutes':round(interval_seconds/60)}
        if fresh and result.get('record') and o.get('screen_activity') and seconds>=entry['next_seconds'] and not entry['busy'] and time.monotonic()-entry['last_try']>=60:
            entry.update(busy=True,last_try=time.monotonic(),status='playing')
            task=asyncio.create_task(self.play(device,entry,seconds,entry['generation']));self.tasks.add(task);task.add_done_callback(self.tasks.discard)
        return {'status':entry['status'],'interval_minutes':round(interval_seconds/60)}
    async def play(self,device,entry,seconds,generation):
        try:
            status,error=await asyncio.to_thread(play_usb,device,'study_eye_alert','study_eye_ack')
            if generation != entry['generation']:
                return  # A late acknowledgment belongs to the completed screen-use run.
            entry['status']=status
            if status=='played': entry['next_seconds']=seconds+entry['interval_seconds']
            elif status!='busy':entry['last_try']=time.monotonic()+240
        except Exception:
            if generation == entry['generation']:
                entry['status']='failed';entry['last_try']=time.monotonic()+240
        finally:entry['busy']=False
alerts=EyeAlerts()
