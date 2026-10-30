/* Cross-page affordances. Data loading remains owned by console.js. */
function renderMonitorContext(){
 const host=$('monitorContext');if(!host)return;
 const device=data?.devices?.find(d=>d.device_id===selected),live=device?.live||{},result=live.result||{};
 const captured=typeof streamState!=='undefined'?streamState.displayedAt:null;
 const time=value=>value?new Date(value*1000).toLocaleTimeString('zh-CN',{hour12:false}):'等待画面';
 const assign=(id,value)=>{if($(id)&&$(id).textContent!==value)$(id).textContent=value;};
 assign('monitorVideoTime',time(captured));assign('monitorAnalysisTime',time(result.captured_at));
 const gap=captured&&result.captured_at?captured-result.captured_at:null;
 const paused=typeof streamState!=='undefined'&&streamState.frozen;
 const mode=typeof liveMode==='function'&&liveMode();
 let state=!selected?'尚未选择设备':!live.online?'等待设备连接':!live.analysis_fresh?'正在分析新画面':!mode?'正在查看判断依据':paused?'预览暂停，分析继续':gap===null?'视频正在连接':Math.abs(gap)<.001?'视频与分析为同一帧':'分析与视频相差 '+Math.abs(gap).toFixed(1)+' 秒';
 assign('monitorSync',state);host.dataset.state=live.online&&live.analysis_fresh?'ready':'waiting';
 const action=$('showAnalysisFrame');if(action){action.disabled=!live.analysis_fresh||!result.frame_id;action.textContent=mode?'查看本次分析画面':'返回实时视频';}
}

document.addEventListener('DOMContentLoaded',()=>{
 $('loadMoreHistory').onclick=loadMoreRecords;$('loadMoreAnalysis').onclick=loadMoreRecords;
 $('showAnalysisFrame').onclick=()=>{
  const mode=$('previewMode');mode.value=liveMode()?'analysis':'live';mode.dispatchEvent(new Event('change'));
  if(!showPreview)$('previewBtn').click();renderMonitorContext();
 };
 const nav=$('settingsQuickNav');
 for(const [index,article] of [...document.querySelectorAll('#settings>article')].entries()){
  const heading=article.querySelector('h2');if(!heading)continue;
  article.id=article.id||'settings-section-'+index;
  const b=element('button',heading.textContent);b.type='button';
  if(article.classList.contains('admin-only'))b.classList.add('admin-only');
  b.onclick=()=>{
   const toggle=article.querySelector('[role=button][aria-expanded]');
   if(toggle?.getAttribute('aria-expanded')==='false')toggle.click();
   article.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
   toggle?.focus({preventScroll:true});
  };
  nav.append(b);
 }
 document.addEventListener('workspace:device',renderMonitorContext);
 document.addEventListener('workspace:page',renderMonitorContext);
 renderMonitorContext();updateRecordLoading();
});
