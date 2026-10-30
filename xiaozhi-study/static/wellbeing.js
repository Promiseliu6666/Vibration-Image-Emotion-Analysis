/* Period reports connect evidence, calendar trends and explicit personal actions. */
(()=>{
 const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 let generation=0,controller=null,lastKey='',lastLoaded=0,currentReport=null,device=selected,pendingKey='';
 const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai'}).format(new Date());
 $('postureDate').value=today();
 const reportVisible=()=>page==='analytics'&&$('habitReports').open;
 function calendar(r){
  const days=[],map=new Map(r.days.map(d=>[d.date,d]));
  const stop=new Date(r.end+'T00:00:00Z');
  for(let date=new Date(r.start+'T00:00:00Z');date<=stop;date.setUTCDate(date.getUTCDate()+1)){
   const iso=date.toISOString().slice(0,10),key=iso.slice(5);
   days.push({iso,date:key,...map.get(key),future:iso>today()});
  }return days;
 }
 function metric(label,value,detail){const box=make('div');box.append(make('small',label),make('strong',value),make('span',detail));return box;}
 function delta(value){return value==null?'上一周期暂无可比较样本':(value===0?'与上一周期持平':(value>0?'较上一周期增加 ':'较上一周期减少 ')+Math.abs(value)+' 个百分点');}
 function chart(r,kind){
  const host=make('div',undefined,'habit-trend'),ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 640 230');svg.setAttribute('role','group');svg.setAttribute('aria-label',kind==='posture'?'每日肩部倾斜样本比例，空缺表示无可评估样本':'每日屏幕相关活动样本比例，空缺表示无可评估样本');
  const add=(tag,attrs,text,parent=svg)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;parent.append(e);return e;};
  const days=calendar(r),color=kind==='posture'?'#4b7968':'#ba8c46';
  for(const n of [0,25,50,75,100]){const y=185-n*1.5;add('line',{x1:42,x2:612,y1:y,y2:y,stroke:'#e5ebe5'});add('text',{x:30,y:y+4,'text-anchor':'end',fill:'#7a877f','font-size':11},n+'%');}
  const detail=make('p','选择日期圆点查看当天观察。','trend-selection');detail.setAttribute('aria-live','polite');let segment=[];
  function finish(){if(segment.length>1)add('polyline',{points:segment.join(' '),fill:'none',stroke:color,'stroke-width':2.5});segment=[];}
  days.forEach((day,i)=>{const x=42+i*570/Math.max(1,days.length-1),den=kind==='posture'?day.posture:day.eyes,count=kind==='posture'?day.tilted:day.screen;
   if(!den){finish();add('circle',{cx:x,cy:185,r:3,fill:day.future?'#edf0eb':'white',stroke:'#c9d3ca'});}
   else {const percent=Math.round(count/den*100),y=185-percent*1.5;segment.push(x+','+y);}
   if(i===0||i===days.length-1||i%Math.max(1,Math.round(days.length/5))===0)add('text',{x,y:214,'text-anchor':'middle',fill:'#6b7d72','font-size':11},day.date);
  });finish();
  days.forEach((day,i)=>{const den=kind==='posture'?day.posture:day.eyes,count=kind==='posture'?day.tilted:day.screen;if(!den)return;
   const percent=Math.round(count/den*100),x=42+i*570/Math.max(1,days.length-1),y=185-percent*1.5;
   const dot=add('circle',{cx:x,cy:y,r:5,fill:color,stroke:'#fff','stroke-width':2,tabindex:0,role:'button','aria-label':day.date+'，'+count+' / '+den+' 个样本，'+percent+'%'});
   const select=()=>{detail.textContent=day.date+'：'+count+' / '+den+' 个可评估样本（'+percent+'%）';};dot.addEventListener('click',select);dot.addEventListener('focus',select);dot.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select();}});add('title',{},day.date+'：'+percent+'%',dot);
  });host.append(svg,detail,make('small','比例按当天可评估样本计算，空缺日期不连线。'));return host;
 }
 function section(title,cls=''){const s=make('section',undefined,'habit-section '+cls);s.append(make('h3',title));return s;}
 function source(label,url){const a=make('a',label);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
 function render(r){
  const host=$('postureReport');host.replaceChildren();currentReport=r;
  const head=make('div',undefined,'habit-report-heading');head.append(make('strong',r.start.replaceAll('-','.')+' — '+r.end.replaceAll('-','.')),make('small',(r.active_days||r.days.length)+' 天有观察记录'));host.append(head);
  if(!r.samples){host.append(make('p','这个周期还没有健康观察记录。可先查看实时监测，记录后再来回顾。','empty-state'));return;}
  const overview=make('div',undefined,'wellbeing-overview');overview.append(metric('最长连续在位观察',(r.longest_presence_minutes||0)+' 分钟','描述有人出现的连续采样片段'),metric('肩部倾斜样本占比',r.tilted_pct==null?'—':r.tilted_pct+'%',delta(r.comparison?.tilted_change)),metric('屏幕相关活动占比',r.screen_pct==null?'—':r.screen_pct+'%',delta(r.comparison?.screen_change)));host.append(overview);
  const columns=make('div',undefined,'wellbeing-report-columns');
  const posture=section('坐姿与活动变化'),eyes=section('屏幕活动变化');
  posture.append(make('p',r.tilted_samples+' / '+r.posture_samples+' 个可评估样本','muted'),chart(r,'posture'));
  eyes.append(make('p',r.screen_samples+' / '+r.eye_samples+' 个可评估样本','muted'),chart(r,'eyes'));columns.append(posture,eyes);host.append(columns);
  const plans=section('把建议变成下一步','habit-plan');plans.append(make('p','选择一项加入待办，从下一段学习开始尝试。','muted'));
  for(const [title,text,task] of [['经常换一换姿势',r.posture_plan,'下一段学习：放松肩膀、双脚踩稳，间隙起身活动'],['给眼睛留出休息',r.eye_plan,'下一段学习：使用屏幕约20分钟后远眺至少20秒']]){
   const row=make('div',undefined,'habit-plan-row'),copy=make('div'),b=make('button','加入学习待办');copy.append(make('strong',title),make('p',text));
   b.onclick=async()=>{b.disabled=true;const reportDevice=selected;try{const board=await api('/study/board');if(!board.tasks.some(t=>!t.done&&t.title===task))await api('/study/tasks',{method:'POST',body:JSON.stringify({title:task})});if(reportDevice===selected){b.textContent='已加入待办';void loadStudyBoard();notify('已加入实时监测页的学习待办');}}catch(e){notify(e.message);b.disabled=false;}};row.append(copy,b);plans.append(row);
  }host.append(plans);
  const feedback=section('记录一次自己的行动','habit-feedback');
  const total=(r.self_reported_actions||[]).reduce((n,a)=>n+a.count,0);feedback.append(make('p','本周期已主动记录 '+total+' 次行动。这里记录你的反馈，帮助下次回顾。','muted'));
  const controls=make('div',undefined,'row');for(const [kind,label] of [['break','我已起身活动'],['posture','我已放松并调整坐姿']]){const b=make('button',label);b.onclick=async()=>{const id=selected;b.disabled=true;try{await api('/health/actions',{method:'POST',body:JSON.stringify({device_id:id,kind,response:'done'})});if(id===selected){notify('这次行动已记录');await load(true);if(typeof loadHealthSummary==='function')void loadHealthSummary();}}catch(e){notify(e.message);}finally{b.disabled=false;}};controls.append(b);}feedback.append(controls);host.append(feedback);
  const scope=make('details',undefined,'habit-method');scope.append(make('summary','查看统计口径与建议来源'),make('p',r.scope),make('p','最长屏幕活动观察 '+r.longest_screen_minutes+' 分钟；无法评估坐姿 '+(r.samples-r.posture_samples)+' 个样本。'),make('p','上一周期按相同已过时间范围对比；样本比例受行为与采样情况共同影响，不作为健康评分。'),source('用眼建议来源','https://www.nei.nih.gov/eye-health-information/healthy-vision/nei-for-kids/healthy-vision-tips'),document.createTextNode('　'),source('坐姿建议来源','https://www.kentcht.nhs.uk/leaflet/good-posture-programme/'));host.append(scope);
 }
 async function load(force=false){
  if(!selected||workspaceUser?.role!=='admin')return;
  const id=selected,key=[id,$('posturePeriod').value,$('postureDate').value].join('|');
  if(!force&&key===pendingKey)return;
  if(!force&&key===lastKey&&Date.now()-lastLoaded<60000)return;
  controller?.abort();pendingKey=key;controller=new AbortController();const seq=++generation;
  const b=$('postureReportForm').querySelector('button');b.disabled=true;$('postureReport').setAttribute('aria-busy','true');
  if(!currentReport||device!==id)$('postureReport').replaceChildren(make('p','正在整理健康记录…','report-loading'));
  device=id;
  try{const r=await api('/wellbeing/report?'+new URLSearchParams({device_id:id,period:$('posturePeriod').value,anchor:$('postureDate').value}),{signal:controller.signal});if(seq!==generation||id!==selected)return;render(r);lastKey=key;lastLoaded=Date.now();}
  catch(e){if(seq!==generation)return;lastKey='';currentReport=null;const p=make('p','报告暂未更新：'+e.message,'error-text');$('postureReport').replaceChildren(p);}
  finally{if(seq===generation){pendingKey='';b.disabled=false;$('postureReport').removeAttribute('aria-busy');}}
 }
 $('postureReportForm').onsubmit=e=>{e.preventDefault();void load(true);};
 $('posturePeriod').onchange=()=>{if(reportVisible())void load(true);};
 $('postureDate').onchange=()=>{if(reportVisible()&&$('postureDate').value)void load(true);};
 document.addEventListener('workspace:page',()=>{if(reportVisible())void load();else{controller?.abort();pendingKey='';generation++;$('postureReport').removeAttribute('aria-busy');$('postureReportForm').querySelector('button').disabled=false;}});
 document.addEventListener('workspace:device',()=>{generation++;controller?.abort();pendingKey='';currentReport=null;lastKey='';$('postureReport').replaceChildren();if(reportVisible())void load(true);});
 document.addEventListener('workspace:ready',()=>{$('habitReports').hidden=workspaceUser?.role!=='admin';if(reportVisible()){if(workspaceUser?.role==='admin')void load();else $('habitReports').open=false;}});
 $('habitReports').addEventListener('toggle',()=>{if(reportVisible())void load();});
 document.addEventListener('health:tab',()=>{if(reportVisible())void load();});
 document.addEventListener('analysis:report',()=>{if(reportVisible())void load();});
 if(reportVisible())void load();
})();
