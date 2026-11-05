/* Behavior reminders remain until explicitly acknowledged. */
const behaviorAlertKey=(()=>{try{const part=(xiaozhiAuth.get()||'').split('.')[1].replace(/-/g,'+').replace(/_/g,'/');return 'behavior-alerts:'+JSON.parse(atob(part)).sub}catch{return 'behavior-alerts:session'}})();
let behaviorAlertStore={items:[],acknowledged:{}};
try{const saved=JSON.parse(sessionStorage.getItem(behaviorAlertKey)||'null');if(saved&&Array.isArray(saved.items)&&saved.acknowledged)behaviorAlertStore=saved}catch{}
function saveBehaviorAlerts(){try{sessionStorage.setItem(behaviorAlertKey,JSON.stringify(behaviorAlertStore))}catch{}}
function renderBehaviorAlerts(){
 if(typeof data!=='undefined'&&Array.isArray(data?.devices)){
  const disabled=new Set(data.devices.filter(d=>d.live?.phone_alert?.enabled===false).map(d=>d.device_id));
  const next=behaviorAlertStore.items.filter(item=>!disabled.has(item.device));
  if(next.length!==behaviorAlertStore.items.length){behaviorAlertStore.items=next;saveBehaviorAlerts()}
 }
 const panel=document.getElementById('behaviorAlerts'),list=document.getElementById('behaviorAlertList');if(!panel||!list)return;
 panel.hidden=!behaviorAlertStore.items.length;
 list.replaceChildren(...behaviorAlertStore.items.map(item=>{
  const row=document.createElement('div');row.className='behavior-alert-row';
  const body=document.createElement('div'),name=document.createElement('strong'),message=document.createElement('p'),stamp=document.createElement('small');
  name.textContent=item.name+' · 使用手机';message.textContent='请放下手机，回到学习。';stamp.textContent=new Date(item.time).toLocaleString('zh-CN',{hour12:false})+' 检测到';body.append(name,message,stamp);
  const close=document.createElement('button');close.type='button';close.textContent='我知道了';close.setAttribute('aria-label','确认 '+item.name+' 的行为提醒');
  close.onclick=()=>{behaviorAlertStore.acknowledged[item.device]=item.event;behaviorAlertStore.items=behaviorAlertStore.items.filter(x=>x.device!==item.device);saveBehaviorAlerts();renderBehaviorAlerts()};const actions=document.createElement('div');actions.className='behavior-alert-actions';
  const view=document.createElement('button');view.type='button';view.textContent='查看相关记录';
  view.onclick=()=>{if(selected!==item.device)choose(item.device);historyDayFilter=AnalysisMetrics.dateKey(item.time);$('historyDate').value=historyDayFilter;$('historyRange').value='all';$('historyBehavior').value='phone';goPage('history');if(item.sessionId)void openDetail(item.sessionId);};
  actions.append(view,close);row.append(body,actions);return row;
 }));
}
function showPersistentBehaviorAlert(device,event,name,time,sessionId){
 if(!event||behaviorAlertStore.acknowledged[device]===event)return;
 const previous=behaviorAlertStore.items.find(x=>x.device===device);
 if(previous?.event===event)return;
 const item={device,event,name,time:time||Date.now(),sessionId};
 behaviorAlertStore.items=behaviorAlertStore.items.filter(x=>x.device!==device);behaviorAlertStore.items.push(item);
 // Keep all unacknowledged physical-device reminders; no automatic timeout or eviction.
 saveBehaviorAlerts();renderBehaviorAlerts();
}
function clearPersistentBehaviorAlert(device){
 const next=behaviorAlertStore.items.filter(x=>x.device!==device);
 if(next.length===behaviorAlertStore.items.length)return;
 behaviorAlertStore.items=next;saveBehaviorAlerts();renderBehaviorAlerts();
}
document.addEventListener('DOMContentLoaded',renderBehaviorAlerts);
