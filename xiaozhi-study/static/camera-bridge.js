/* Shared camera controls use the analysis service, never the USB command channel. */
(()=>{
 let pending=false;
 const source=()=>/^vibration-(local|rtsp)$/.exec(selected||'')?.[1];
 const originalRender=renderLive;
 renderLive=function(){
  originalRender();const s=source();if(!s)return;
  const bridge=data?.camera_bridges?.[s]||{},live=data?.devices?.find(d=>d.device_id===selected)?.live||{};
  const viewer=typeof workspaceUser!=='undefined'&&workspaceUser?.role==='viewer';
  $('captureBtn').hidden=viewer;$('captureBtn').disabled=pending;$('captureBtn').textContent=pending?'正在处理…':bridge.running?'暂停共享监测':'开始共享监测';
  $('testVoice').disabled=true;
  if(!live.online)$('guidance').textContent=bridge.running?(bridge.error||'正在等待共享摄像头画面，请检查本地摄像头或 RTSP 连接。'):'共享监测已暂停。点击“开始共享监测”恢复。';
  if($('captureExplanation'))$('captureExplanation').textContent='画面来自振动图像项目的'+(s==='local'?'本地摄像头':'海康 RTSP 摄像头')+'，共用采集连接；暂停共享监测不影响原项目。';
 };
 const originalConnection=updateConnectionType;
 updateConnectionType=function(){originalConnection();if(!source())return;const b=ensureConnectionTypeBadge();if(b){b.hidden=false;b.textContent='共享摄像头';b.title='与振动图像项目共用视频源'}};
 $('captureBtn').addEventListener('click',async event=>{
  const s=source();if(!s)return;event.preventDefault();event.stopImmediatePropagation();if(pending)return;
  pending=true;renderLive();
  try{const running=data?.camera_bridges?.[s]?.running;await api('/console/camera-bridge/'+(running?'stop':'start'),{method:'POST',body:JSON.stringify({source:s})});await refresh();notify(running?'已暂停小智共享监测':'已启动共享监测，正在等待新画面')}
  catch(error){notify(error.message)}finally{pending=false;renderLive()}
 },true);
})();
