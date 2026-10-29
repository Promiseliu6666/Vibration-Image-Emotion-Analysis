/* Keep camera requests independent from navigation and status controls. */
const uxState={previewRequest:0,previewController:null,previewKey:'',pendingKey:'',capturePending:false,pollTimer:null,statusMs:0,failures:0};
function cancelPreview(){if(typeof stopLivePreview==='function')stopLivePreview();uxState.previewRequest++;uxState.previewController?.abort();uxState.previewController=null;uxState.previewKey='';uxState.pendingKey=''}
function captureControlIsBusy(){return uxState.capturePending}
function updateConnection(connected=true){
 const el=$('connectionHint');
 if(el){el.textContent=connected?'已连接 · 自动更新':'连接中断 · 正在重试';el.dataset.connected=String(connected)}
 updateConnectionType();
 const live=data?.devices?.find(d=>d.device_id===selected)?.live, r=live?.result;
 const hint=$('previewHint');if(hint)hint.textContent=!showPreview?'画面已隐藏，分析继续进行':r?.captured_at?(uxState.previewKey===selected+':'+r.frame_id?'与分析对应 · '+new Date(r.captured_at*1000).toLocaleTimeString('zh-CN',{hour12:false}):'正在同步分析画面'+(blobUrl?' · 当前仍显示上一帧':'')):'等待首张分析画面';
 if(typeof writePreviewHint==='function')writePreviewHint();
 const calibration=$('calibrationHint');if(calibration){const e=r?.evidence;calibration.hidden=!(e?.face_visible&&!e.fatigue_calibrated);if(!calibration.hidden)calibration.textContent='正在适应你的眼部特征 '+Math.min(60,e.calibration_samples||0)+' / 60，请保持自然坐姿。'}
 const current=data?.capture?.by_device?.[selected]||data?.capture;if(current?.identified){localStorage.setItem('lastCaptureIdentity',JSON.stringify({device_id:current.device_id,usb_serial:current.identity?.usb_serial}));}
}
/* 当前设备的接入方式：在"当前设备"选择框旁边显示 有线 USB / 无线 Wi-Fi（设备管理里也有一份） */
function ensureConnectionTypeBadge(){
 let badge=document.getElementById('connectionType');
 if(badge)return badge;
 const actions=document.querySelector('.header-actions');if(!actions)return null;
 badge=document.createElement('span');badge.id='connectionType';badge.className='badge';
 const label=actions.querySelector('label');
 if(label&&label.after)label.after(badge);else actions.prepend(badge);
 return badge;
}
function updateConnectionType(){
 const badge=ensureConnectionTypeBadge();if(!badge)return;
 const device=typeof data!=='undefined'&&data?.devices?data.devices.find(d=>d.device_id===selected):null;
 if(!device){badge.hidden=true;badge.textContent='';return}
 const link=device.live?.link;                     /* 最近一帧实际走的链路：usb / wifi */
 const wifi=link?link==='wifi':!!device.wireless;  /* 还没收到画面时按登记方式推断 */
 badge.hidden=false;
 badge.textContent=wifi?'无线 Wi-Fi':'有线 USB';
 badge.title=link?(wifi?'最近一次画面通过 Wi-Fi 上传':'最近一次画面通过 USB 线上传'):(wifi?'登记为无线接入，还没有收到画面':'用 USB 连接，还没有收到画面');
}
/* 切换设备后立刻更新徽标，不等下一次轮询 */
{
 const picker=document.getElementById('device');
 if(picker)picker.addEventListener('change',()=>setTimeout(updateConnectionType,0));
}
async function updatePreview(){
 if(typeof liveMode==='function'&&liveMode()){void startLivePreview();return;}
 if(!showPreview||page!=='live'||!selected||document.hidden)return;
 const id=selected, live=data?.devices?.find(d=>d.device_id===id)?.live, frame=live?.result?.frame_id;
 if(!live?.online||!frame)return;
 const key=id+':'+frame;if(key===uxState.previewKey||key===uxState.pendingKey)return;
 uxState.previewController?.abort();const controller=new AbortController();uxState.previewController=controller;
 const request=++uxState.previewRequest;uxState.pendingKey=key;let url=null;
 const timeout=setTimeout(()=>controller.abort(),6000);
 const current=()=>request===uxState.previewRequest&&id===selected&&showPreview&&page==='live'&&!document.hidden;
 try{
  const response=await fetch('/api/console/preview/'+encodeURIComponent(id)+'?analyzed=true&frame_id='+encodeURIComponent(frame),{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:controller.signal});
  if(!response.ok)return;
  const blob=await response.blob();if(!current())return;
  url=URL.createObjectURL(blob);const image=new Image();image.src=url;await image.decode();
  if(!current())return;
  const previous=blobUrl;blobUrl=url;url=null;$('preview').src=blobUrl;$('previewPanel')?.style?.setProperty('--camera-frame','url("'+blobUrl+'")');$('preview').hidden=false;$('placeholder').hidden=true;
  uxState.previewKey=key;if(typeof streamState!=='undefined'){streamState.displayedAt=live.result.captured_at;streamState.width=image.naturalWidth||0;streamState.height=image.naturalHeight||0}if(previous)URL.revokeObjectURL(previous);updateConnection(true);
 }catch(error){if(error.name!=='AbortError'&&current()&&$('previewHint'))$('previewHint').textContent='画面暂未更新，正在重试';}
 finally{clearTimeout(timeout);if(url)URL.revokeObjectURL(url);if(request===uxState.previewRequest){uxState.pendingKey='';uxState.previewController=null;}}
}
function scheduleRefresh(){
 clearTimeout(uxState.pollTimer);if(document.hidden)return;
 const interval=verifying||page==='live'?1000:4000;
 uxState.pollTimer=setTimeout(async()=>{await refresh();scheduleRefresh()},Math.min(15000,interval*Math.max(1,uxState.failures)));
}
async function toggleCapture(){
 if(uxState.capturePending)return;
 const selectedCapture=data?.capture?.by_device?.[selected];
 const running=!!selectedCapture?.running||(data?.capture?.device_id===selected&&!!data?.capture?.running);
 let port=null, expectedSerial=null;
 if(!running){
  let previous=null;try{previous=JSON.parse(localStorage.getItem('lastCaptureIdentity')||'null')}catch{}
  const candidates=data?.capture?.candidates||[];
  if(selectedCapture?.usb_serial){previous={device_id:selected,usb_serial:selectedCapture.usb_serial}}
  port=candidates.find(p=>previous?.device_id===selected&&p.usb_serial===previous?.usb_serial)?.port;
  if(!port){openWizard();return;}
  expectedSerial=previous.usb_serial;
 }
 uxState.capturePending=true;const button=$('captureBtn');button.disabled=true;button.setAttribute('aria-busy','true');button.textContent=running?'正在暂停…':'正在恢复…';
 try{
  await api('/console/capture/'+(running?'stop':'start'),{method:'POST',body:JSON.stringify(port?{port,expected_usb_serial:expectedSerial,device_id:selected}:{device_id:selected})});
  notify(running?'已暂停采集，历史记录已保留':'已恢复采集，正在读取设备画面');
  if(busy)await refresh();
  await refresh();
 }catch(error){if(typeof showOperationError==='function')showOperationError('监测操作未确认',error,refresh);else notify(error.message)}
 finally{uxState.capturePending=false;button.removeAttribute('aria-busy');renderLive();scheduleRefresh()}
}
document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(uxState.pollTimer);cancelPreview()}else{refresh().finally(scheduleRefresh)}});

document.addEventListener('DOMContentLoaded',()=>{const mode=document.getElementById('previewMode');if(mode){mode.value=localStorage.getItem('previewMode')||'live';mode.onchange=()=>{localStorage.setItem('previewMode',mode.value);clearPreview();updateConnection();void updatePreview()};}});
