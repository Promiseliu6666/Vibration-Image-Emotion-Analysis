const $=id=>document.getElementById(id), token=xiaozhiAuth.get();
if(!token) xiaozhiAuth.expire();
let historyDayFilter='',historyController=null;
let historyLoading=false,historyRequest=0,summaryRequest=0;
let recordLimit=50,recordScope='',recordRenderKey='';
const pageScroll=new Map();
let data=null,selected=localStorage.getItem('selectedDevice')||'',page='live',showPreview=localStorage.getItem('previewVisible')==='true',blobUrl=null,editing='',removing='',verifying=0,busy=false,historyRows=[],toastTimer=null,detailRequest=0,wizardPid=null;
const labels={offline:'未收到新画面',processing:'画面已到达 · 分析中',waiting_person:'在线 · 等待入座',monitoring:'在线 · 监测中',error:'在线 · 分析异常',engaged_hand_raising:'举手互动',engaged_discussing:'讨论交流',standing:'站立活动',engaged_computer:'电脑操作',engaged_screen:'听讲 / 朝向学习区',engaged_reading:'投入阅读',engaged_writing:'投入书写',absent:'无人',thinking:'活动未确认',resting:'休息',distracted_phone:'使用手机',distracted_away:'视线离开',distracted:'分心',fatigued:'疲劳迹象'};
function notify(text){clearTimeout(toastTimer);$('notice').textContent=text;$('notice').hidden=!text;if(text)toastTimer=setTimeout(()=>$('notice').hidden=true,6500)}
function showOperationError(title,error,retry){const panel=$('operationError');if(!panel){notify(error.message);return}panel.hidden=false;$('operationErrorTitle').textContent=title;$('operationErrorText').textContent=error.message;const b=$('operationErrorRetry');b.hidden=!retry;b.onclick=async()=>{b.disabled=true;try{const result=await retry();if(result===true)panel.hidden=true}catch(e){$('operationErrorText').textContent=e.message}finally{b.disabled=false}};$('operationErrorDismiss').onclick=()=>panel.hidden=true;}
function renderAnalysisContext(live,r){
 const set=(id,text)=>{const el=$(id);if(el)el.textContent=text};
 const unavailable=!live.online?'尚未收到新画面':!live.analysis_fresh?'等待最新分析':!r.person_present?'未识别到人':'';
 set('fatigueReason',unavailable||(r.evidence?.version===2?(!r.evidence.face_visible?'面部未清晰可见':!r.evidence.fatigue_calibrated?'正在建立个人基线':''):''));set('distractionReason',unavailable);
 const lag=r.captured_at?Math.max(0,Date.now()/1000-r.captured_at):0;set('analysisFreshness',r.captured_at?(live.analysis_fresh?'当前分析画面 · ':'上次分析画面 · ')+new Date(r.captured_at*1000).toLocaleTimeString('zh-CN',{hour12:false})+' · 距现在 '+Math.round(lag)+' 秒'+(r.camera_rotation?' · 已校正横置方向':''):'尚无分析结果');
 if(typeof renderMonitorContext==='function')renderMonitorContext();
 set('captureExplanation',data?.capture?.running?'暂停画面仅冻结预览，分析继续；暂停监测停止采集与分析。':'监测已停止。开始监测后恢复采集与分析。');
}
async function api(path,options={}){
 const controller=new AbortController();const external=options.signal,onAbort=()=>controller.abort();if(external?.aborted)controller.abort();else external?.addEventListener('abort',onAbort,{once:true});const timeout=setTimeout(()=>controller.abort(),path.includes('/agent/')?90000:15000);
 try{const r=await fetch('/api'+path,{...options,signal:controller.signal,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json',...options.headers}});
 if(r.status===401){xiaozhiAuth.expire();throw Error('登录已过期，请重新登录')}
 if(!r.ok){const b=await r.json().catch(()=>({}));throw Error(typeof b.detail==='string'?b.detail:'操作未完成，请稍后重试')}return await r.json();
 }catch(e){if(external?.aborted)throw new DOMException('请求已取消','AbortError');if(e.name==='AbortError'||e instanceof TypeError){const writing=(options.method||'GET').toUpperCase()!=='GET';throw Error(writing?'连接中断或等待超时，暂不能确认操作结果。请重新读取状态，核对是否已生效后再操作；输入内容已保留。':'暂时无法读取数据。请确认项目服务正在运行，再重新读取。')}throw e}finally{clearTimeout(timeout);external?.removeEventListener('abort',onAbort)}
}

function element(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el}
/* 统一的"问号"入口：把解释性小字收进浮层，页面只留标题、数字和可点的按钮。
   label 用当前小节标题，便于读屏与键盘聚焦时知道这是哪一段的说明。 */
function helpBox(label,texts){const box=element('div',undefined,'help'),btn=element('button','?','help-btn'),pop=element('div',undefined,'help-pop');btn.type='button';btn.setAttribute('aria-label',(label||'说明')+' · 口径说明');for(const t of [].concat(texts||[]))if(t)pop.append(element('p',t));box.append(btn,pop);return box}
function button(text,action){const b=element('button',text);b.onclick=async()=>{if(b.disabled)return;b.disabled=true;try{await action()}catch(e){notify(e.message)}finally{b.disabled=false}};return b}
const dt=t=>t?new Date(t).toLocaleString('zh-CN',{hour12:false}):'—';
function clearPreview(){if(typeof cancelPreview==='function')cancelPreview();if(blobUrl)URL.revokeObjectURL(blobUrl);blobUrl=null;$('previewPanel')?.style?.removeProperty('--camera-frame');$('preview').hidden=true;$('preview').removeAttribute('src');$('placeholder').hidden=false}
function clearDeviceRecords(){
 historyController?.abort();historyRequest++;summaryRequest++;
 historyRows=[];recordScope='';recordRenderKey='';recordLimit=50;
 if(typeof HEALTH_ROWS!=='undefined')HEALTH_ROWS=[];
 if(typeof HEALTH_SUMMARY!=='undefined')HEALTH_SUMMARY=null;
 for(const id of ['samples','focus','average'])if($(id))$(id).textContent='—';
 if($('distribution'))$('distribution').replaceChildren();
 if(typeof renderHistory==='function')renderHistory();
}
function choose(id){
 historyDayFilter='';$('historyDate').value='';
 if(typeof invalidateMonthlyReport==='function')invalidateMonthlyReport();
 selected=id;localStorage.setItem('selectedDevice',id);
 clearPreview();clearDeviceRecords();renderLive();
 loadSummary().catch(e=>notify(e.message));
 if(page==='history'||page==='analytics')void loadHistory();
 publishAssistantContext();
 if(typeof resetHealthView==='function')resetHealthView();
 document.dispatchEvent(new Event('workspace:device'));
}
function renderLive(){if(!data){$('testVoice').disabled=true;$('captureBtn').disabled=true;$('previewBtn').disabled=true;$('captureBtn').hidden=typeof workspaceUser!=='undefined'&&workspaceUser?.role==='viewer';return}$('captureBtn').disabled=typeof captureControlIsBusy==='function'&&captureControlIsBusy();const dev=data?.devices?.find(d=>d.device_id===selected),live=dev?.live||{},r=live.result||{};const state=live.state||'offline';renderAnalysisContext(live,r);renderPhoneWarning(live,r);if(typeof renderRecognitionEvidence==='function')renderRecognitionEvidence(live,r);if(typeof renderStudyInsights==='function')renderStudyInsights(live,r);if(typeof renderHealthCard==='function')renderHealthCard(live,r);$('state').textContent=labels[state];$('state').className='badge'+(live.online?' good':'');$('activity').textContent=state==='monitoring'?(r.learning_state==='thinking'&&r.evidence?.candidate_state&&r.evidence.candidate_state!=='thinking'?'正在确认'+(labels[r.evidence.candidate_state]||'当前活动')+'（'+(r.evidence.window?.samples||0)+'/'+(r.evidence.window?.required_samples||3)+'）':labels[r.learning_state]||r.learning_state||'正在监测'):labels[state];$('guidance').textContent=({offline:'检查 USB 连接并启动采集。也可以到“设置”的设备管理中运行完整检测。',processing:'已收到设备图像，正在等待分析结果。',waiting_person:'分析画面暂未识别到人；若实时画面中有人，请核对对应截图并调整取景。',monitoring:r.learning_state==='thinking'?(r.evidence?.recognition_reason||'已识别到人，具体活动证据不足；请让画面覆盖双手和桌面。'):'',error:live.error||'分析暂未完成，请重试采集。'})[state];$('fatigue').textContent=live.analysis_fresh&&r.person_present?(r.evidence?.version===2?(!r.evidence.face_visible?'—':!r.evidence.fatigue_calibrated?'标定中':fatigueStatus(r.fatigue_level)):fatigueStatus(r.fatigue_level)):'—';$('distraction').textContent=live.analysis_fresh&&r.person_present?attentionStatus(r.distraction_level):'—';$('received').textContent=live.last_received?'收到画面 '+dt(live.last_received*1000)+(r.captured_at?' · 分析画面 '+dt(r.captured_at*1000):''):'尚未收到真实画面';const sharedSource=selectedSharedCameraSource();const captureRunning=sharedSource?data?.camera_bridges?.[sharedSource]?.running:(data?.capture?.by_device?.[selected]?.running||(data?.capture?.device_id===selected&&data?.capture?.running));if(typeof captureControlIsBusy!=='function'||!captureControlIsBusy())$('captureBtn').textContent=captureRunning?'暂停监测':'开始监测';$('captureBtn').hidden=(typeof workspaceUser!=='undefined'&&workspaceUser?.role==='viewer')||(!sharedSource&&!!data?.capture?.device_id&&!!selected&&selected!==data?.capture?.device_id&&!data?.capture?.by_device?.[selected]);$('previewBtn').disabled=!live.online;if(!live.online){clearPreview();$('placeholder').textContent='暂无新画面，请检查连接'}else $('placeholder').textContent=showPreview?'正在获取设备画面…':'点击“查看画面”，检查摄像头位置';}
function renderDevices(){
 const list=$('deviceList');if(!data){if(list.dataset.key!=='loading'){list.dataset.key='loading';list.replaceChildren(element('p','正在读取设备，请稍候…','empty-state'))}return}const key=JSON.stringify([typeof workspaceUser!=='undefined'?workspaceUser?.role:'unknown',selected,$('showTests').checked,data.devices.map(d=>[d.device_id,d.name,d.live.state,d.live.link,d.wireless])]);if(list.dataset.key===key){for(const d of data.devices){const row=[...list.children].find(x=>x.dataset.deviceId===d.device_id),time=row?.querySelector('.device-time');if(time)time.textContent='最近画面 '+(d.live.last_received?new Date(d.live.last_received*1000).toLocaleTimeString('zh-CN',{hour12:false}):'—')+' · 最近分析 '+(d.live.result?.captured_at?new Date(d.live.result.captured_at*1000).toLocaleTimeString('zh-CN',{hour12:false}):'—');}return;}list.dataset.key=key;list.replaceChildren();
 const devices=data.devices.filter(d=>$('showTests').checked||!d.test);$('deviceCount').textContent=devices.length+' 台设备 · '+devices.filter(d=>d.live.online).length+' 台在线';
 if(!devices.length)list.append(element('p','还没有设备。点上面的“接入新设备”，插好 USB 线后开始检测。','empty-state'));
 for(const d of devices){const row=element('div',undefined,'row'),info=element('div');row.dataset.selected=String(d.device_id===selected);row.dataset.deviceId=d.device_id;const hhmm=t=>t?new Date(t*1000).toLocaleTimeString('zh-CN',{hour12:false}):'—';const wifi=d.live.link?d.live.link==='wifi':!!d.wireless;info.append(element('div',undefined,'device-symbol'),element('strong',d.name||d.device_id),element('div',d.device_id+(d.test?' · 测试设备':'')+' · '+(d.device_id.startsWith('vibration-')?'共享摄像头':wifi?'无线 Wi-Fi':'有线 USB'),'device-id'),element('span',labels[d.live.state],'badge'+(d.live.online?' good':'')),element('small','最近画面 '+hhmm(d.live.last_received)+' · 最近分析 '+hhmm(d.live.result?.captured_at),'muted device-time'));
 const actions=element('div',undefined,'row');actions.append(button('查看',async()=>{choose(d.device_id);$('device').value=selected;goPage('live')}),button('改名',async()=>{editing=d.device_id;$('newName').value=d.name||'';$('renameError').textContent='';$('edit').showModal();$('newName').focus()}),button('删除',async()=>{const c=await api('/console/devices/'+encodeURIComponent(d.device_id)+'/deletion');removing=d.device_id;$('deleteDescription').textContent=`“${d.name||d.device_id}”包含 ${c.sessions} 个学习时段、${c.records} 条分析记录。`;$('confirmDelete').checked=false;$('deleteBtn').disabled=true;$('deleteError').textContent='';$('remove').showModal()}),button('Wi-Fi 接入',async()=>{if(typeof startWirelessSetup!=='function')throw Error('页面脚本还没准备好，请刷新后重试');await startWirelessSetup(d.device_id,d.name||d.device_id)}));if(typeof workspaceUser!=='undefined'&&workspaceUser?.role==='viewer'){while(actions.children.length>1)actions.lastChild.remove()}row.append(info,actions);list.append(row)}
}

function renderWizard(){if(!data||!verifying||!wizardPid)return;const c=(data.capture?.collectors||[]).find(x=>x.collector_pid===wizardPid&&x.port===$('usbPort').value)||data.capture,l=data.devices.find(d=>d.device_id===c.device_id)?.live||{};
 const matching=c.collector_pid===wizardPid&&c.port===$('usbPort').value;
 const checks=[(data.capture.ports||[]).includes($('usbPort').value),matching&&c.identified,matching&&(l.last_received||0)>=verifying,matching&&(l.last_analyzed||0)>=verifying&&l.analysis_fresh&&!l.error];
 [...$('steps').children].forEach((el,i)=>{el.classList.toggle('done',checks[i]);el.textContent=['发现所选 USB 摄像头','读取物理设备标识','收到本次检测的真实画面','完成本次图像分析'][i]});
 if(matching&&c.identity)$('physicalIdentity').textContent=`物理设备：${c.device_id} · USB ${c.identity.usb_serial} · 摄像头 ${c.identity.camera_id}`;
 if(checks.every(Boolean)){$('wizardMessage').textContent='接入验证成功。图像与记录将归入上述物理设备；已有设备会保留原名称。';verifying=0;$('usbPort').disabled=false;$('verify').disabled=false;choose(c.device_id);$('device').value=selected;document.dispatchEvent(new CustomEvent('workspace:device-detected',{detail:{deviceId:c.device_id}}))}
 else if(Date.now()/1000-verifying>35){$('wizardMessage').textContent=c.error||(!checks[0]?'所选 USB 设备已断开。':!checks[1]?'未能读取物理设备标识，已阻止误归入已有设备。':!checks[2]?'身份已识别，但尚未收到真实画面。':'图像已收到，但分析尚未完成，请稍后重试。');verifying=0;$('verify').disabled=false}}

function notifyPhoneWarnings(devices){for(const d of devices){const live=d.live||{},alert=live.phone_alert||{},result=live.result||{};if(live.online&&live.analysis_fresh&&!alert.stale&&result.person_present&&(result.learning_state==='distracted_phone'||alert.confirmed===true)&&alert.event_id&&phoneToastEvents.get(d.device_id)!==alert.event_id){phoneToastEvents.set(d.device_id,alert.event_id);showPersistentBehaviorAlert(d.device_id,alert.event_id,d.name||d.device_id,result.captured_at?result.captured_at*1000:Date.now(),result.record?.session_id);if((page==='history'||page==='analytics')&&d.device_id===selected)void loadHistory(true)}}while(phoneToastEvents.size>64)phoneToastEvents.delete(phoneToastEvents.keys().next().value)}

let statusFlight=null;
async function refresh(){if(statusFlight)return statusFlight;statusFlight=refreshStatus();try{return await statusFlight}finally{statusFlight=null}}
function selectedSharedCameraSource(){
 return /^vibration-(local|rtsp)$/.exec(selected)?.[1]||'';
}
function ensureSelectedSharedCamera(status){
 if(!document.body.classList.contains('health-embedded')||!Array.isArray(status?.devices))return;
 const source=selectedSharedCameraSource();
 status.devices=status.devices.filter(d=>typeof d?.device_id==='string'&&d.device_id&&!d.test&&(!d.device_id.startsWith('vibration-')||(page==='live'&&d.device_id===selected)));
 if(page!=='live'||!source||status.devices.some(d=>d.device_id===selected))return;
 const bridge=status.camera_bridges?.[source]||{};
 status.devices.push({device_id:selected,name:'共享摄像头 · '+(source==='local'?'本地':'海康 RTSP'),wireless:false,test:false,link:'shared-camera',live:{state:bridge.running?'processing':'offline',online:Boolean(bridge.online),error:bridge.error||(bridge.running?'正在等待共享摄像头画面':'共享监测已暂停'),received:bridge.received||0,processed:0,dropped:0,last_received:bridge.last_frame_at||0,result:null,analysis_fresh:false,phone_alert:{enabled:false,stale:true}}});
}
async function refreshStatus(){if(busy||document.hidden)return;busy=true;try{const initial=!data;const status=await api('/console/status');ensureSelectedSharedCamera(status);if(!status||!Array.isArray(status.devices)||!status.capture)throw Error('设备状态响应不完整，请稍后重试');data=status;document.documentElement.style.visibility='visible';const key=JSON.stringify(data.devices.map(d=>[d.device_id,d.name]));if($('device').dataset.key!==key){$('device').replaceChildren(...data.devices.map(d=>{const o=element('option',(d.name||d.device_id)+(d.test?'（测试）':''));o.value=d.device_id;return o}));$('device').dataset.key=key}if(!data.devices.some(d=>d.device_id===selected)){selected=(data.devices.find(d=>d.live.online&&!d.test)||data.devices.find(d=>!d.test)||data.devices[0])?.device_id||'';localStorage.setItem('selectedDevice',selected);clearPreview();clearDeviceRecords();document.dispatchEvent(new Event('workspace:device'));loadSummary().catch(e=>notify(e.message));if(!initial&&(page==='history'||page==='analytics'))void loadHistory()}$('device').value=selected;if(page==='live')renderLive();if(page==='settings')renderDevices();renderWizard();notifyPhoneWarnings(data.devices);if(initial){loadSummary().catch(e=>notify(e.message));if((page==='history'||page==='analytics'))loadHistory().catch(e=>notify(e.message));}publishAssistantContext();if(typeof updateConnection==='function')updateConnection(true);if(typeof uxState!=='undefined')uxState.failures=0;if($('operationErrorTitle')?.textContent==='后台连接中断')$('operationError').hidden=true;if(typeof updatePreview==='function')void updatePreview();}catch(e){if(xiaozhiAuth.get())document.documentElement.style.visibility='visible';if(typeof uxState==='undefined'||uxState.failures===0)showOperationError('后台连接中断',e,refresh);if(typeof uxState!=='undefined')uxState.failures++;if(typeof updateConnection==='function')updateConnection(false);$('state').textContent='后台连接中断';$('activity').textContent='暂停更新';$('fatigue').textContent='—';$('distraction').textContent='—';for(const id of ['fatigueReason','distractionReason','analysisFreshness'])if($(id))$(id).textContent='后台连接中断，等待更新'}finally{busy=false}}
async function loadSummary(){const request=++summaryRequest,id=selected;if(!id){['samples','focus','average'].forEach(x=>$(x).textContent='—');$('distribution').replaceChildren();return}try{const s=await api('/console/summary/'+encodeURIComponent(id));if(id!==selected||request!==summaryRequest)return;if(typeof noteHealthSummary==='function')noteHealthSummary(s);$('samples').textContent=s.samples;$('focus').textContent=s.focus_pct===null?'—':s.focus_pct+'%';$('average').textContent=fatigueStatus(s.fatigue);if($('averageReason'))$('averageReason').textContent=s.fatigue==null?'观察不足，暂不能判断':'根据今天可评估的画面归纳';$('distribution').replaceChildren();$('distribution').append(element('p',s.samples?'详细活动构成、识别覆盖与导出已统一到数据分析。':'今天还没有有效观察样本。','muted'));if($('summaryError'))$('summaryError').hidden=true;if($('retrySummary'))$('retrySummary').hidden=true;}catch(e){if(id!==selected||request!==summaryRequest)return;if($('summaryError')){$('summaryError').textContent='统计暂未更新。'+e.message;$('summaryError').hidden=false;$('retrySummary').hidden=false;$('retrySummary').onclick=()=>loadSummary()}else notify(e.message)}}
function recordQuery(){
 const range=page==='analytics'?$('dataRange').value:$('historyRange').value;
 const day=page==='history'?historyDayFilter:'';
 const scope=JSON.stringify([selected,range,day]);
 if(scope!==recordScope){recordLimit=50;recordScope=scope;recordRenderKey='';historyRows=[];}
 const params=new URLSearchParams({device_id:selected,period:range,limit:String(recordLimit)});
 if(day)params.set('day',day);
 return {params,scope};
}
function updateRecordLoading(){
 for(const id of ['loadMoreHistory','loadMoreAnalysis']){
  const b=$(id);if(!b)continue;
  b.hidden=!selected||historyRows.length<recordLimit||recordLimit>=500;
  b.disabled=historyLoading;b.textContent=historyLoading?'正在读取…':'继续加载更早记录';
 }
 const note=$('recordLoadNote');if(note)note.textContent=historyRows.length>=500?'已载入 500 段，可按日期缩小范围，或导出完整记录。':historyRows.length?'已载入 '+historyRows.length+' 段记录':'';
}
async function loadMoreRecords(){if(historyLoading)return;recordLimit=Math.min(500,recordLimit+50);await loadHistory();}
async function loadHistory(quiet=false){
 if(quiet&&(historyLoading||document.querySelector('#sessionDetail[open],#monthlyReportDialog[open]')||document.activeElement?.closest('#analysisOverview,#analysisExtensions,#sessions')))return;
 const {params,scope}=recordQuery();
 historyController?.abort();historyController=new AbortController();
 const controller=historyController,request=++historyRequest,id=selected;
 historyLoading=true;$('refreshHistory').disabled=true;$('refreshData').disabled=true;
 $(page==='analytics'?'analytics':'history').setAttribute('aria-busy','true');updateRecordLoading();
 if(!quiet){$('dataLoadStatus').textContent='正在更新分析…';if(!historyRows.length){$('sessions').textContent='正在读取健康记录…';if(typeof renderDataAnalysis==='function')renderDataAnalysis();}}
 try{
  if(!id){historyRows=[];renderHistory();$('dataLoadStatus').textContent='连接设备后即可查看分析。';return;}
  const rows=await api('/sessions?'+params,{signal:controller.signal});
  if(id!==selected||request!==historyRequest||scope!==recordScope)return;
  if(!Array.isArray(rows))throw Error('记录响应不完整，请重新刷新');
  const key=JSON.stringify([scope,rows]);historyRows=rows;
  // Unchanged polling must not replace focused controls, expanded rows or charts.
  if(!quiet||key!==recordRenderKey){
   const opened=[...document.querySelectorAll('#sessions details[open]')].map(el=>el.dataset.group);
   renderHistory();for(const el of document.querySelectorAll('#sessions details'))if(opened.includes(el.dataset.group))el.open=true;
   recordRenderKey=key;
  }
  $('dataLoadStatus').textContent='更新于 '+new Date().toLocaleTimeString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});
 }catch(e){
  if(id!==selected||request!==historyRequest||e.name==='AbortError')return;
  $('dataLoadStatus').textContent=(historyRows.length?'更新失败，当前显示上次读取的记录：':'分析暂未加载：')+e.message;
  if(!historyRows.length)$('sessions').replaceChildren(element('p','记录暂未更新。'+e.message,'error-text'),button('重新读取记录',()=>loadHistory()));
 }finally{if(request===historyRequest){historyLoading=false;$('refreshHistory').disabled=false;$('refreshData').disabled=false;for(const id of ['analytics','history'])$(id).removeAttribute('aria-busy');updateRecordLoading();}}
}

function historySpecial(s){return ['phone','away','rest','fatigue'].some(k=>s.behaviors?.[k]>0)||Object.entries(s.risk_flags||{}).some(([key,n])=>Number(n)>0&&key!=='quality_poor'&&!key.startsWith('mood_'))}
function historyBrief(s){return !historySpecial(s)&&s.valid_samples<3&&!!s.end_time}
function renderHistory(){
 document.querySelectorAll('[data-range]').forEach(b=>b.setAttribute('aria-pressed',String(!historyDayFilter&&b.dataset.range===$('historyRange').value)));
 const range=$('historyRange').value;
 const behavior=$('historyBehavior')?.value||'all',priority=$('historySort')?.value==='priority',showBrief=$('showBriefHistory')?.checked;
 const ranged=AnalysisMetrics.inRange(historyRows,range).filter(s=>!historyDayFilter||AnalysisMetrics.dateKey(s.start_time)===historyDayFilter),rows=ranged.filter(s=>(['vision','sedentary','attention','rhythm'].includes(behavior)?historyDimensionMatch(s):behavior==='all'||(behavior==='special'?historySpecial(s):s.behaviors?.[behavior]>0))&&(typeof historyFlagMatch==='function'?historyFlagMatch(s):true));if(typeof renderHistoryColumns==='function')renderHistoryColumns(page==='analytics'&&typeof analysisRows==='function'?analysisRows():ranged);if(typeof renderHistoryComposition==='function')renderHistoryComposition(page==='analytics'&&typeof analysisRows==='function'?analysisRows():ranged);if(typeof renderHealthAnalysis==='function')renderHealthAnalysis(ranged);
 const special=ranged.filter(historySpecial).length,short=rows.filter(historyBrief).length;
 const highlights=$('historyHighlights');if(highlights){highlights.replaceChildren();for(const [key,name,count] of [['phone','手机使用记录',ranged.filter(s=>s.behaviors?.phone>0).length],['special','值得回看的记录',ranged.filter(historySpecial).length],['all','此范围全部记录',ranged.length]]){const b=button(name,()=>{$('historyBehavior').value=key;renderHistory()});b.append(element('strong',String(count)));b.setAttribute('aria-pressed',String(behavior===key));highlights.append(b)}}

 $('historyCount').textContent=rows.length+' / '+ranged.length+' 段';if($('historyOverview'))$('historyOverview').textContent='当前范围 '+ranged.length+' 段记录 · '+special+' 段有特别行为'+(short&&!showBrief?' · '+short+' 段普通短记录已折叠':'');$('sessions').replaceChildren();
 if(!rows.length){$('sessions').append(element('p','没有符合当前筛选的记录。试试全部记录或其他时间范围。','empty-state'));return}
 const groups=new Map();for(const s of rows){const day=new Date(s.start_time).toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'short'});if(!groups.has(day))groups.set(day,[]);groups.get(day).push(s)}
 const makeRow=s=>{const featured=historySpecial(s),row=element('div',undefined,'session-row history-record'+(featured?' history-featured':'')),info=element('div',undefined,'session-main'),start=new Date(s.start_time),end=s.end_time?new Date(s.end_time):null;
 info.append(element('strong',start.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit',hour12:false})),element('small',(end?'记录跨度 '+(end-start<60000?Math.max(0,Math.round((end-start)/1000))+' 秒':Math.round((end-start)/60000)+' 分钟'):'记录进行中')+' · '+s.valid_samples+' 个有效样本'));
 const tags=element('div',undefined,'history-behaviors');if(s.primary){const order=['vision','sedentary','attention','data'];let top='',topN=0;for(const k of order){const n=Number(s.primary[k]||0);if(n>topN){top=k;topN=n}}if(top&&topN)tags.append(element('span','主要 '+healthPrimaryLabel(top)+' · '+topN+' 样本','behavior-chip behavior-dim-'+top));}for(const [key,label] of [['phone','手机使用'],['away','视线离开'],['rest','休息'],['fatigue','疲劳迹象']])if(s.behaviors?.[key]>0)tags.append(element('span',label+' · '+s.behaviors[key]+' 样本','behavior-chip behavior-'+key));
 for(const [key,label] of [['posture_tilt','肩部持续倾斜'],['posture_lying','疑似趴桌'],['eye_nearwork','连续用眼较久'],['sedentary_due','连续在位较久']])if(Number(s.risk_flags?.[key]||0)>0)tags.append(element('span',label+' · '+s.risk_flags[key]+' 样本','behavior-chip'));
 if(!featured)tags.append(element('span',s.valid_samples<3?'样本较少':s.behaviors?.engaged?'学习活动 · '+s.behaviors.engaged+' 样本':'未确认特别行为','behavior-chip behavior-neutral'));
 row.append(info,tags,button(featured?'回看特别行为':'查看记录',()=>openDetail(s.id)));return row};
 for(const [day,records] of groups){$('sessions').append(element('h3',day+' · '+records.length+' 段','history-day-heading'));if(priority)records.sort((a,b)=>Number(historySpecial(b))-Number(historySpecial(a))||new Date(b.start_time)-new Date(a.start_time));const brief=[];for(const s of records){if(!showBrief&&behavior==='all'&&historyBrief(s)){brief.push(s);continue}$('sessions').append(makeRow(s))}if(brief.length){const details=element('details',undefined,'brief-history');details.dataset.group=day;details.append(element('summary','普通短记录 · '+brief.length+' 段（样本较少）'));brief.forEach(s=>details.append(makeRow(s)));$('sessions').append(details)}}
}

let detailImageUrls=[];
function releaseDetailImages(){detailRequest++;for(const url of detailImageUrls)URL.revokeObjectURL(url);detailImageUrls=[];}
$('sessionDetail').addEventListener('close',releaseDetailImages);
async function openDetail(id){
 releaseDetailImages();const request=detailRequest;$('detailBody').textContent='正在整理这一段学习…';$('sessionDetail').showModal();
 try{const s=await api('/sessions/'+id);if(request!==detailRequest)return;const body=$('detailBody');body.replaceChildren(element('p',dt(s.start_time)+' 至 '+(s.end_time?dt(s.end_time):'记录进行中'),'muted'));
 const dist=Object.entries(s.state_distribution||{}).filter(([,n])=>n>0),total=s.valid_records??s.total_records,overview=element('div',undefined,'dialog-behavior-overview'),ring=element('div',undefined,'dialog-behavior-ring'),center=element('div');
 center.append(element('strong',String(total)),element('small','有效样本'));ring.append(center);let angle=0;const colors={distracted_phone:'#d7ac69',distracted_away:'#8ca9bc',resting:'#b2c198',thinking:'#d6dfd1'};
 const sum=dist.reduce((n,[,v])=>n+Number(v),0);const stops=dist.map(([key,value])=>{const start=angle;angle+=value/Math.max(1,sum)*360;return (colors[key]||'#678a68')+' '+start+'deg '+angle+'deg'});ring.style.background=stops.length?'conic-gradient('+stops.join(',')+')':'#e4eadf';ring.setAttribute('role','img');ring.setAttribute('aria-label',dist.map(([key,value])=>(labels[key]||key)+' '+value+'%').join('，')||'无有效样本');
 const legend=element('div');for(const [key,value] of dist)legend.append(element('p',(labels[key]||key)+'　'+value+'%','muted'));overview.append(ring,legend);body.append(overview,element('h3','值得回看的时刻'));
 const events=[];for(const event of s.events||[]){const previous=events[events.length-1];if(previous&&previous.label===event.label&&Math.abs(new Date(previous.timestamp)-new Date(event.timestamp))<30000)previous.nearby++;else events.push({...event,nearby:1});}
 for(const e of events.slice(0,12)){const row=element('div',undefined,'detail-event'),head=element('div',undefined,'row');head.append(element('strong',e.label.replace(/玩手机.*/,'使用手机')+(e.nearby>1?' · '+e.nearby+' 次相近提示':'')),element('small',dt(e.timestamp)));row.append(head,element('p',e.detail,'muted'));
  if(e.frame_path&&e.image_available){const b=button('查看对应截图',async()=>{const response=await fetch('/api/frame-image?path='+encodeURIComponent(e.frame_path),{headers:{Authorization:'Bearer '+token}});if(!response.ok)throw Error('这张截图暂时无法读取');const blob=await response.blob();if(request!==detailRequest||!row.isConnected)return;const url=URL.createObjectURL(blob);detailImageUrls.push(url);const image=element('img');image.src=url;image.alt='与此行为事件对应的保存截图';row.append(image);b.hidden=true;const save=button('保存原始截图',()=>{const a=element('a');a.href=url;a.download='行为截图-'+new Date(e.timestamp).toISOString().replace(/[:.]/g,'-')+'.jpg';a.click()});row.append(save);});row.append(b);}else row.append(element('small','此事件没有可用截图'));body.append(row);
 }
 if(!events.length)body.append(element('p','这一段没有记录到需要提示的事件。','muted'));
 const link=element('a','打开完整图表与事件回顾');link.href=xiaozhiAuth.url('/static/session.html?id='+encodeURIComponent(s.id));body.append(element('p',undefined),link);
 const scope=element('details');scope.append(element('summary','查看记录说明'),element('p','统计当前时段保存的分析样本；样本占比不等于学习时长。相近30秒的同类提示合并展示，截图对应组内最新事件。此窗口展示最近12组事件，完整回顾包含全部事件。','muted'));body.append(scope);
 }catch(e){if(request===detailRequest)$('detailBody').textContent='读取失败：'+e.message}
}
function goPage(next,options={}){
 if(next==='devices')next='settings';
 if(next==='assistant'){
  if(window.XiaozhiAssistant)window.XiaozhiAssistant.open();else window.openAssistantOnReady=true;
  return;
 }
 if(next==='eyes'||next==='posture'){next='analytics';$('habitReports').open=true;}
 if(!['live','history','analytics','settings'].includes(next))next='live';
 const changed=next!==page;
 if(changed)pageScroll.set(page,window.scrollY);
 page=next;
 document.querySelectorAll('.page').forEach(x=>x.hidden=x.id!==page);
 document.querySelectorAll('[data-page]').forEach(x=>{
  x.classList.toggle('active',x.dataset.page===page);
  if(x.dataset.page===page)x.setAttribute('aria-current','page');else x.removeAttribute('aria-current');
 });
 $('title').textContent={live:'健康看板',history:'健康记录',analytics:'数据分析',settings:'设置'}[page];
 $('pageIntro').textContent={live:'',history:'把行为片段和健康观察放在一起，找到下一步调整方向。',analytics:'回顾变化、发现规律，让下一步更有方向。',settings:'管理设备接入、账号与记录留存。'}[page];
 if(!options.fromHistory&&location.hash!=='#'+page)history[options.replace?'replaceState':'pushState'](null,'','#'+page);
 if(page==='settings'&&typeof loadWorkspace==='function')void loadWorkspace();
 if(page==='settings'&&typeof loadNetworks==='function'&&typeof workspaceUser!=='undefined'&&workspaceUser?.role==='admin')void loadNetworks();
 if(page==='history'||page==='analytics')void loadHistory();
 if(page!=='live')clearPreview();else renderLive();
 void refresh();if(typeof scheduleRefresh==='function')scheduleRefresh();
 if(changed)window.scrollTo({top:pageScroll.get(page)||0,behavior:'instant'});
 document.dispatchEvent(new Event('workspace:page'));
}
window.addEventListener('popstate',()=>goPage(location.hash.slice(1)||'live',{fromHistory:true}));

document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>goPage(b.dataset.page));
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());$('wizard').addEventListener('close',()=>{verifying=0;$('usbPort').disabled=false;$('verify').disabled=false});
$('device').onchange=()=>choose($('device').value);$('logout').onclick=()=>{xiaozhiAuth.expire()};$('previewBtn').onclick=()=>{showPreview=!showPreview;$('previewBtn').textContent=showPreview?'隐藏画面':'查看画面';localStorage.setItem('previewVisible',String(showPreview));if(!showPreview)clearPreview();if(typeof updateConnection==='function')updateConnection();if(showPreview)void updatePreview();};
$('captureBtn').onclick=toggleCapture;
$('add').onclick=openWizard;$('verify').onclick=async()=>{const port=$('usbPort').value;if(!port){$('wizardMessage').textContent='请先连接 USB 摄像头，并选择设备端口。';return}$('verify').disabled=true;$('usbPort').disabled=true;verifying=Date.now()/1000;wizardPid=null;$('wizardMessage').textContent='正在重新读取所选设备的物理标识…';try{const c=await api('/console/capture/start',{method:'POST',body:JSON.stringify({port})});wizardPid=c.collector_pid;await refresh()}catch(e){verifying=0;$('usbPort').disabled=false;$('verify').disabled=false;$('wizardMessage').textContent=e.message}finally{if(!verifying)$('usbPort').disabled=false}};
$('renameForm').onsubmit=async e=>{e.preventDefault();const save=e.currentTarget.querySelector('button.primary');save.disabled=true;save.textContent='正在保存…';$('renameError').textContent='';try{await api('/console/devices/'+encodeURIComponent(editing),{method:'PATCH',body:JSON.stringify({name:$('newName').value.trim()})});$('edit').close();await refresh();notify('设备名称已保存')}catch(e){$('renameError').textContent=e.message}finally{save.disabled=false;save.textContent='保存名称'}};
$('confirmDelete').onchange=()=>{$('deleteBtn').disabled=!$('confirmDelete').checked};$('deleteBtn').onclick=async()=>{$('deleteBtn').disabled=true;try{await api('/console/devices/'+encodeURIComponent(removing),{method:'DELETE',body:JSON.stringify({confirm_device_id:removing})});$('remove').close();await refresh();await loadSummary();notify('设备及其历史记录已删除。需要使用时，请重新运行接入检测。')}catch(e){$('deleteError').textContent=e.message}finally{$('deleteBtn').disabled=!$('confirmDelete').checked}};
$('refreshHistory').onclick=()=>loadHistory().catch(e=>notify(e.message));
async function openWizard(){verifying=0;wizardPid=null;$('verify').disabled=true;$('wizardMessage').textContent='正在查找 USB 设备…';$('physicalIdentity').textContent='识别后将在这里显示物理设备编号。';[...$('steps').children].forEach((el,i)=>{el.className='';el.textContent=['发现所选 USB 摄像头','读取物理设备标识','收到本次检测的真实画面','完成本次图像分析'][i]});$('wizard').showModal();try{const current=await api('/console/status');data=current;$('usbPort').replaceChildren(...current.capture.candidates.map(p=>{const o=element('option',p.label);o.value=p.port;return o}));$('verify').disabled=!current.capture.available;$('wizardMessage').textContent=current.capture.available?'选择端口后开始检测。重新插拔后仍按物理标识关联，名称可以自行修改。':'没有发现 USB 摄像头。请接好数据线后点击“重新查找”。';}catch(e){$('wizardMessage').textContent=e.message}}

$('heroConnect').onclick=openWizard;$('rescanUsb').onclick=async()=>{if(verifying)return;await openWizard()};$('historyRange').onchange=()=>void loadHistory();$('showTests').onchange=renderDevices;
$('todayLabel').textContent=new Date().toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'long'});
$('previewBtn').textContent=showPreview?'隐藏画面':'查看画面';
$('refreshNow').onclick=async()=>{const button=$('refreshNow');button.disabled=true;try{await refresh();if(page==='live')await loadSummary();if((page==='history'||page==='analytics'))await loadHistory()}catch(e){notify(e.message)}finally{button.disabled=false}};
$('sessionDetail').addEventListener('close',()=>detailRequest++);
const initialPage=location.hash.slice(1);if(['history','analytics','devices','assistant','settings','eyes','posture'].includes(initialPage))goPage(initialPage,{replace:true});
if(page==='live')$('pageIntro');refresh().finally(scheduleRefresh);setInterval(()=>{if(!document.hidden&&page==='live')loadSummary().catch(()=>{})},30000);

function renderPhoneWarning(live,result){
 const alert=live.phone_alert||result.phone_alert||{};
 $('phoneWarning').hidden=!(live.online&&live.analysis_fresh&&!alert.stale&&result.person_present&&(result.learning_state==='distracted_phone'||alert.confirmed===true));

 const feedback={idle:'持续识别到手机使用后，小智将语音提醒。',sending:'正在发送小智语音提醒…',played:'小智已返回播放完成回执，将按当前设置控制重复提醒。',busy:'小智正在对话，稍后重试提醒。',muted:'小智当前静音。',unavailable:'小智语音暂不可用。',failed:'语音提醒未完成。',device:'小智正在处理本次语音提醒。'};
 feedback.scheduler='达到设定的持续时长后，小智会提醒。';
 $('voiceFeedback').textContent=(alert.enabled===false?'自动语音已关闭，本次行为仍会记录。':feedback[alert.voice_status||'idle'])+(alert.error?' '+alert.error:'');
 $('testVoice').hidden=(typeof workspaceUser!=='undefined'&&workspaceUser?.role==='viewer');
 $('testVoice').disabled=voiceTesting||!selected||!data?.capture?.running||selected!==data?.capture?.device_id;
 const tested=data.devices?.find(d=>d.device_id===voiceTestDevice),testAlert=tested?.live.phone_alert||{};
 if(voiceTesting&&testAlert.voice_status&&testAlert.voice_status!=='sending'){
  voiceTesting=false;$('testVoice').textContent='测试小智语音';$('testVoice').disabled=!data?.capture?.running||selected!==data?.capture?.device_id;
  notify((tested?.name||voiceTestDevice)+'：'+(testAlert.voice_status==='played'?'已完成语音播放，请确认是否听到。':testAlert.error||'语音测试未完成，请重试。'));
 }
}
const phoneToastEvents=new Map();
let voiceTesting=false,voiceTestDevice='';
$('testVoice').onclick=async()=>{if(voiceTesting||!selected)return;voiceTesting=true;voiceTestDevice=selected;$('testVoice').disabled=true;$('testVoice').textContent='正在测试语音…';try{const response=await api('/console/devices/'+encodeURIComponent(selected)+'/voice-test',{method:'POST'});notify(response.message);await refresh()}catch(e){voiceTesting=false;$('testVoice').textContent='测试小智语音';notify(e.message);renderLive()}};

function renderStudyInsights(live,result){
 const host=$('studyInsights');if(!host)return;const o=result.evidence?.observations;
 if(!o||!live.analysis_fresh){host.replaceChildren();return;}
 const items=[];
 if(o.posture_assessable&&o.posture_tilt)items.push(['坐姿提醒','长时间保持不舒服姿势可能增加颈背不适；调整支撑并经常换姿势。']);
 if(o.break_due)items.push(['该休息了','已连续用眼 45 分钟，起身远眺片刻']);
 else if(o.focus_seconds>=60)items.push(['连续用眼',Math.floor(o.focus_seconds/60)+' 分钟']);
 const quality={dark:'光线偏暗，调整照明后识别更稳定',overexposed:'画面过亮，请避开直射灯光',soft:'画面细节不足，请调整摄像头位置'};
 if(quality[o.quality])items.push(['取景建议',quality[o.quality]]);
 host.replaceChildren(...items.map(([title,text])=>{const card=document.createElement('div');const name=document.createElement('strong');name.textContent=title;const value=document.createElement('span');value.textContent=text;card.append(name,value);return card;}));
}

for(const id of ['historyBehavior','historySort','showBriefHistory'])if($(id))$(id).onchange=renderHistory;

setInterval(()=>{if(!document.hidden&&(page==='history'||page==='analytics'))void loadHistory(true)},15000);


function publishAssistantContext(){const d=data?.devices?.find(d=>d.device_id===selected);document.dispatchEvent(new CustomEvent('assistant:context',{detail:{deviceId:d?.device_id||'',deviceName:d?.name||'',configured:data?!!data.assistant_configured:null}}));}

$('historyDate').onchange=()=>{historyDayFilter=$('historyDate').value;$('historyRange').value='all';document.querySelectorAll('[data-range]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.range==='all')));void loadHistory()};
$('clearHistoryDate').onclick=()=>{historyDayFilter='';$('historyDate').value='';void loadHistory()};
