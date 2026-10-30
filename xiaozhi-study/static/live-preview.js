/* One incoming pending frame, no playback queue; preview and analysis stay independent. */
const streamState={controller:null,device:'',generation:0,pending:null,decoding:false,displayedAt:null,lastPacketAt:0,frozen:false,mirrored:false,nativeSize:false,times:[],paintTimes:[],width:0,height:0,retryAt:0,paintedAt:0};
const previewNow=()=>typeof performance!=='undefined'?performance.now():Date.now();
function liveMode(){return $('previewMode')?.value!=='analysis'}
function stopLivePreview(){streamState.generation++;streamState.controller?.abort();streamState.controller=null;streamState.device='';streamState.pending=null;streamState.displayedAt=null;streamState.lastPacketAt=0;streamState.times=[];streamState.paintTimes=[];streamState.frozen=false;streamState.width=0;streamState.height=0;streamState.paintedAt=0;renderPreviewControls()}
function renderPreviewControls(){
 const ready=!!blobUrl&&showPreview;
 for(const id of ['freezePreview','savePreview','fullscreenPreview']){const el=$(id);if(el)el.disabled=!ready||(id==='freezePreview'&&!liveMode())}
 const freeze=$('freezePreview');if(freeze){freeze.textContent=streamState.frozen?'恢复画面':'暂停画面';freeze.setAttribute?.('aria-pressed',String(streamState.frozen))}
 const mirror=$('mirrorPreview');if(mirror){mirror.setAttribute?.('aria-pressed',String(streamState.mirrored));mirror.textContent=streamState.mirrored?'取消镜像':'镜像查看'}
 $('preview')?.classList?.toggle('mirrored',streamState.mirrored);$('preview')?.classList?.toggle('native-size',streamState.nativeSize);const size=$('nativePreview');if(size){size.textContent=streamState.nativeSize?'适应窗口':'原始尺寸';size.setAttribute?.('aria-pressed',String(streamState.nativeSize))}
}
function writePreviewHint(){
 const hint=$('previewHint');if(!hint||!showPreview)return;if(!liveMode()){const badge=$('previewHealth');if(badge){badge.textContent='对选取画面进行分析';badge.dataset.health='paused'}renderPreviewControls();return;}
 const live=data?.devices.find(d=>d.device_id===selected)?.live, r=live?.result;
 const rate=times=>times.length>1&&times.at(-1)>times[0]?((times.length-1)/(times.at(-1)-times[0])).toFixed(1):null;const fps=rate(streamState.paintTimes),receivedFps=rate(streamState.times);
 const age=streamState.paintedAt?Math.max(0,(previewNow()-streamState.paintedAt)/1000):0;
 let text=streamState.frozen?'画面已暂停 · 后台分析继续':!live?.online?'设备未在线':age>3?'画面暂未更新 · 正在检查连接':'实时预览'+(fps?' · '+fps+' 帧/秒':'');
 if(receivedFps&&fps&&Math.abs(Number(receivedFps)-Number(fps))>1)text+=' · 接收 '+receivedFps+' 帧/秒';
 if(streamState.width)text+=' · '+streamState.width+'×'+streamState.height;
 if(streamState.displayedAt)text+=' · 画面 '+new Date(streamState.displayedAt*1000).toLocaleTimeString('zh-CN',{hour12:false});
/* 画面帧与"分析用的那一帧"不是同一帧：预览永远是最新收到的，分析结果来自稍早的一帧。
   两个时间戳都取服务端收到该帧的时刻（同一时钟可直接相减），后面跟上相差秒数。 */
if(r?.captured_at){
 text+=' · 分析 '+new Date(r.captured_at*1000).toLocaleTimeString('zh-CN',{hour12:false});
 if(streamState.displayedAt){
  const frameGap=streamState.displayedAt-r.captured_at;
  text+=Math.abs(frameGap)<.001?' · 同一帧':' · 分析'+(frameGap>=0?'落后':'领先')+Math.abs(frameGap).toFixed(1)+' 秒';
 }
}
 if(hint.textContent!==text)hint.textContent=text;
 if(typeof renderMonitorContext==='function')renderMonitorContext();
 const health=$('previewHealth');if(health){const message=streamState.frozen?'画面暂停中':!live?.online?'等待设备':age>3?'连接恢复中':fps?'实时 · '+fps+' FPS':'正在连接';if(health.textContent!==message)health.textContent=message;health.dataset.health=streamState.frozen?'paused':age>3||!live?.online?'waiting':'live'}
 const quality=$('previewQuality');if(quality){quality.hidden=!(streamState.width&&streamState.width<480);if(!quality.hidden)quality.textContent='设备原始画面为 '+streamState.width+'×'+streamState.height+'，放大不会增加细节；可选择“原始尺寸”查看。'}renderPreviewControls();
}
async function displayLiveFrame(bytes,capturedAt,generation){
 if(generation!==streamState.generation||streamState.frozen)return;
 streamState.pending={bytes,capturedAt,generation};if(streamState.decoding)return;
 streamState.decoding=true;
 try{
  while(streamState.pending){
   const frame=streamState.pending;streamState.pending=null;let url=null;
   try{
    url=URL.createObjectURL(new Blob([frame.bytes],{type:'image/jpeg'}));const image=new Image();image.decoding='async';image.src=url;await image.decode();
    if(frame.generation!==streamState.generation||streamState.frozen||!showPreview||page!=='live'||!liveMode()||document.hidden)continue;
    // If decoding fell behind, discard this image and paint only the latest pending frame.
    if(streamState.pending?.generation===frame.generation&&streamState.pending.capturedAt>frame.capturedAt&&streamState.paintedAt&&previewNow()-streamState.paintedAt<200)continue;
    const old=blobUrl;blobUrl=url;url=null;$('preview').src=blobUrl;$('previewPanel')?.style?.setProperty('--camera-frame','url("'+blobUrl+'")');$('preview').hidden=false;$('placeholder').hidden=true;
    streamState.displayedAt=frame.capturedAt;streamState.paintedAt=previewNow();streamState.paintTimes.push(streamState.paintedAt/1000);if(streamState.paintTimes.length>32)streamState.paintTimes.shift();streamState.width=image.naturalWidth||0;streamState.height=image.naturalHeight||0;
    if(old)URL.revokeObjectURL(old);if(!streamState.lastHintAt||previewNow()-streamState.lastHintAt>500){streamState.lastHintAt=previewNow();writePreviewHint()}
   }finally{if(url)URL.revokeObjectURL(url)}
  }
 }catch{}finally{streamState.decoding=false}
}
function headerEnd(buffer){for(let i=0;i+3<buffer.length;i++)if(buffer[i]===13&&buffer[i+1]===10&&buffer[i+2]===13&&buffer[i+3]===10)return i;return -1}
function extractMjpeg(buffer){
 const end=headerEnd(buffer);if(end<0){if(buffer.length>4096)throw Error('视频头异常');return null}
 const header=new TextDecoder().decode(buffer.slice(0,end));const match=header.match(/Content-Length:\s*(\d+)/i);
 if(!match)throw Error('视频长度缺失');const length=Number(match[1]);if(length<4||length>4*1024*1024)throw Error('视频帧大小异常');
 const begin=end+4;if(buffer.length<begin+length+2)return null;
 const at=Number(header.match(/X-Captured-At:\s*([\d.]+)/i)?.[1])||Date.now()/1000;
 return {bytes:buffer.slice(begin,begin+length),capturedAt:at,rest:buffer.slice(begin+length+2)};
}
async function startLivePreview(){
 if(!showPreview||page!=='live'||!selected||document.hidden||!liveMode())return;
 if(!data?.devices.find(d=>d.device_id===selected)?.live?.online)return;
 if(streamState.controller&&streamState.device===selected||Date.now()<streamState.retryAt)return;
 stopLivePreview();const id=selected,generation=streamState.generation,controller=new AbortController();
 streamState.controller=controller;streamState.device=id;streamState.lastPacketAt=previewNow();
 let reader=null;const watchdog=setInterval(()=>{if(generation===streamState.generation&&previewNow()-streamState.lastPacketAt>4500)controller.abort()},1000);
 try{
  const response=await fetch('/api/console/stream/'+encodeURIComponent(id),{headers:{Authorization:'Bearer '+token},signal:controller.signal,cache:'no-store'});
  if(!response.ok||!response.body)throw Error('视频预览暂未连接');reader=response.body.getReader();let buffer=new Uint8Array();
  while(generation===streamState.generation){
   const {done,value}=await reader.read();if(done)break;
   if(buffer.length+value.length>8*1024*1024)throw Error('视频缓冲异常，正在重新连接');
   const merged=new Uint8Array(buffer.length+value.length);merged.set(buffer);merged.set(value,buffer.length);buffer=merged;
   let frame,latest=null;while((frame=extractMjpeg(buffer))){buffer=frame.rest;latest=frame;streamState.times.push(frame.capturedAt);if(streamState.times.length>32)streamState.times.shift()}
   if(latest){streamState.lastPacketAt=previewNow();void displayLiveFrame(latest.bytes,latest.capturedAt,generation)}
  }
 }catch(error){if(error.name!=='AbortError'&&generation===streamState.generation&&$('previewHint'))$('previewHint').textContent='实时预览连接中断，正在重连';}
 finally{clearInterval(watchdog);if(reader)try{await reader.cancel()}catch{}if(generation===streamState.generation){streamState.controller=null;streamState.device='';streamState.retryAt=Date.now()+800}}
}
function reconnectPreview(){streamState.retryAt=0;clearPreview();if(showPreview)void updatePreview()}
async function savePreview(){
 if(!blobUrl)return;try{const image=await(await fetch(blobUrl)).blob();const url=URL.createObjectURL(image),link=document.createElement('a');link.href=url;link.download='学习画面-'+new Date((streamState.displayedAt||Date.now()/1000)*1000).toISOString().replace(/[:.]/g,'-')+'.jpg';link.click();setTimeout(()=>URL.revokeObjectURL(url),1500);notify('已保存当前显示的原图；镜像仅影响预览')}catch{notify('保存失败，请等待新画面后重试')}
}
document.addEventListener?.('DOMContentLoaded',()=>{
 $('freezePreview').onclick=()=>{streamState.frozen=!streamState.frozen;streamState.pending=null;if(!streamState.frozen)streamState.paintTimes=[];renderPreviewControls();writePreviewHint();if(!streamState.frozen)void updatePreview()};
 $('mirrorPreview').onclick=()=>{streamState.mirrored=!streamState.mirrored;localStorage.setItem('previewMirror',String(streamState.mirrored));renderPreviewControls()};
 streamState.mirrored=localStorage.getItem('previewMirror')==='true';streamState.nativeSize=localStorage.getItem('previewNativeSize')==='true';$('nativePreview').onclick=()=>{streamState.nativeSize=!streamState.nativeSize;localStorage.setItem('previewNativeSize',String(streamState.nativeSize));renderPreviewControls()};
 $('savePreview').onclick=savePreview;$('reconnectPreview').onclick=reconnectPreview;
 $('fullscreenPreview').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('previewPanel').requestFullscreen()}catch{notify('浏览器暂不支持全屏，请尝试最大化窗口')}};
 setInterval(()=>{if(page==='live'&&!document.hidden){writePreviewHint();if(showPreview&&liveMode()&&!streamState.controller)void startLivePreview()}},1000);renderPreviewControls();
});
