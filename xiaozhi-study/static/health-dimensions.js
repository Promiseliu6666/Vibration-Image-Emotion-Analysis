/* 健康维度分类与呈现。

   分类表必须与 app/analysis/health_dimensions.py 保持一致。
   这是"标签式归属"：同一状态可同时计入多个维度（阅读既是用眼负荷也是久坐），
   因此各维度占比之和会大于 100%，界面上必须如实说明。

   本文件在 console.js 之前加载，但只在渲染时才调用 console.js 提供的
   $() / element() / labels / renderHistory()，加载阶段不引用它们。 */
const HEALTH_DIMENSIONS=[
 {key:'vision',   label:'用眼负荷',   hint:'持续近距离与屏幕用眼'},
 {key:'sedentary',label:'久坐与体态', hint:'静态久坐、坐姿与活动'},
 {key:'attention',label:'注意力与心理',hint:'学习活动、手机使用与视线变化'},
 {key:'rhythm',   label:'作息与休息', hint:'休息与疲劳节律'}
];
const HEALTH_STATES={
 vision:['engaged_reading','engaged_writing','engaged_screen','engaged_computer','distracted_phone','fatigued'],
 sedentary:['engaged_reading','engaged_writing','engaged_screen','engaged_computer','engaged_discussing','distracted_phone','standing','resting'],
 attention:['engaged_reading','engaged_writing','engaged_screen','engaged_computer','engaged_hand_raising','engaged_discussing','distracted_phone','distracted_away','resting','fatigued'],
 rhythm:['resting','fatigued']
};
let HEALTH_SUMMARY=null;


function healthDimensionLabel(key){const d=HEALTH_DIMENSIONS.find(x=>x.key===key);return d?d.label:key}
function noteHealthSummary(s){HEALTH_SUMMARY=s||null;if(typeof renderHealthAnalysis==='function')renderHealthAnalysis()}


/* 生成一个指标格：大数字 + 单位 + 说明 + 可选进度条 */
/* 生成一个指标格：分类名 + 一句人话现状 + 一句判断词 */
function healthCell(host,spec){
 const cell=element('div',undefined,'health-cell');
 cell.dataset.tone=spec.tone||'normal';
 cell.append(element('small',spec.label,'health-label'));
 cell.append(element('p',spec.value,'health-value'));
 if(spec.note)cell.append(element('p',spec.note,'health-note'));
 host.append(cell);
}

/* 画面活动 → 人话分类；判断词只在确实需要提醒时给出 */
const HEALTH_ACTIVITY_TEXT={engaged_reading:'正专注阅读',engaged_writing:'正专注书写',engaged_screen:'正专注听讲',engaged_computer:'正专注用电脑',engaged_hand_raising:'举手互动',engaged_discussing:'讨论交流',distracted_phone:'在看手机',distracted_away:'视线离开了',resting:'正在休息',fatigued:'有点累了',standing:'站着活动',thinking:'正在确认活动',absent:'没看到人'};
const HEALTH_ACTIVITY_NOTE={distracted_phone:'把手机放到一边再继续',distracted_away:'把注意力放回桌面',fatigued:'有点累了，先歇一会儿',thinking:'让画面同时拍到双手和桌面',absent:'坐回书桌前就会重新记录'};
function healthActivityText(state){return HEALTH_ACTIVITY_TEXT[state]||(typeof labels!=='undefined'?labels[state]:'')||state||'—'}
function healthActivityNote(state){return HEALTH_ACTIVITY_NOTE[state]||''}

/* 用眼疲劳只在完成个人基线标定后才给结论，标定不足就不下判断 */
function fatigueStatus(value){
 if(value===null||value===undefined||value===''||!Number.isFinite(Number(value)))return '暂无法判断';
 const n=Number(value);return n>=0.6?'疲劳迹象较明显':n>=0.4?'有一些疲劳迹象':'疲劳迹象较少';
}
function eyeFatigueWord(value){return fatigueStatus(value)}
function coverageStatus(value){if(value==null)return '暂无法判断';return Number(value)>=70?'多数画面可判断':Number(value)>=40?'部分画面可判断':'可判断画面较少'}
function attentionStatus(value){if(value==null||!Number.isFinite(Number(value)))return '暂无法判断';return Number(value)>=0.6?'频繁出现分心迹象':Number(value)>=0.35?'偶有分心迹象':'分心迹象较少'}


/* 作息与休息：先读今天最近的休息记录，页面打开期间由实时画面修正 */
const REST_TRACK={deviceId:'',lastRestAt:null,count:0,loadedAt:0,loading:false,resting:false};
function noteLiveRest(deviceId,live,result){
 if(!deviceId)return;
 if(REST_TRACK.deviceId!==deviceId){REST_TRACK.deviceId=deviceId;REST_TRACK.lastRestAt=null;REST_TRACK.count=0;REST_TRACK.loadedAt=0;REST_TRACK.resting=false}
 const resting=!!(live&&live.analysis_fresh&&result&&result.learning_state==='resting');
 REST_TRACK.resting=resting;
 const at=result&&result.captured_at?Number(result.captured_at)*1000:0;
 if(resting&&at&&(!REST_TRACK.lastRestAt||at>REST_TRACK.lastRestAt))REST_TRACK.lastRestAt=at;
}
async function loadRestToday(deviceId,force){
 if(!deviceId||REST_TRACK.loading)return;
 if(!force&&REST_TRACK.deviceId===deviceId&&REST_TRACK.loadedAt&&Date.now()-REST_TRACK.loadedAt<120000)return;
 REST_TRACK.loading=true;
 /* 无论成功失败都记一次时间，避免读不到时反复重试 */
 REST_TRACK.deviceId=deviceId;REST_TRACK.loadedAt=Date.now();
 try{
  const rows=await api('/sessions?device_id='+encodeURIComponent(deviceId));
  const midnight=new Date();midnight.setHours(0,0,0,0);
  const today=(rows||[]).filter(s=>s&&s.behaviors&&Number(s.behaviors.rest)>0&&s.start_time&&new Date(s.start_time).getTime()>=midnight.getTime());
  if(REST_TRACK.deviceId!==deviceId)return;REST_TRACK.count=today.length;
  if(today.length){
   const detail=await api('/sessions/'+encodeURIComponent(today[0].id));
   if(REST_TRACK.deviceId!==deviceId)return;const last=((detail&&detail.behavior_samples)||[]).filter(s=>s&&s.state==='resting'&&s.timestamp).map(s=>new Date(s.timestamp).getTime()).filter(t=>!isNaN(t)).sort((a,b)=>a-b).pop();
   if(last&&(!REST_TRACK.lastRestAt||last>REST_TRACK.lastRestAt))REST_TRACK.lastRestAt=last;
  }
 }catch(e){/* 读不到今天的记录时只保留实时观测到的休息，不打断实时监测 */}
 finally{REST_TRACK.loading=false;if(REST_TRACK.deviceId===deviceId&&typeof renderLive==='function')renderLive()}
}
function restAgoText(at){
 const minutes=Math.floor((Date.now()-at)/60000);
 if(minutes<=0)return '刚刚休息过';
 if(minutes<60)return '上次休息 '+minutes+' 分钟前';
 return '上次休息 '+Math.floor(minutes/60)+' 小时前';
}



/* ① 今日分布图：按健康维度分组 */
function renderDimensions(s){
 const host=$('distribution');if(!host)return;
 const dims=(s&&s.dimensions)||[];
 if(!dims.length){
  for(const x of ((s&&s.distribution)||[]))host.append(element('div',(labels[x.state]||x.state)+' · '+x.count+' 个样本','muted'));
  return;
 }
 for(const d of dims){
  const box=element('div',undefined,'dim-row');
  const head=element('div',undefined,'dim-head');
  head.append(element('strong',d.label));
  head.append(element('span',d.pct===null||d.pct===undefined?'—':d.pct+'%'+(d.samples?' · '+d.samples+' 个样本':''),'dim-value'));
  box.append(head);
  const bar=element('div',undefined,'bar'),fill=element('i');
  fill.style.width=Math.min(100,Number(d.pct)||0)+'%';bar.append(fill);box.append(bar);
  if(d.hint)box.append(element('small',d.hint,'dim-hint'));
  const split=[];
  if(d.positive_pct)split.push('偏正向 '+d.positive_pct+'%');
  if(d.risk_pct)split.push('偏风险 '+d.risk_pct+'%');
  if(split.length)box.append(element('small',split.join(' · '),'dim-split'));
  host.append(box);
 }
}

/* ② 健康指标条：实时四维大指标 */
function renderHealthCard(live,result){
 const host=$('healthDimensions');if(!host)return;
 const deviceId=(typeof selected!=='undefined'?selected:'');
 noteLiveRest(deviceId,live,result);
 if(deviceId)void loadRestToday(deviceId);
 const fresh=!!(live&&live.analysis_fresh&&result&&result.person_present);
 const o=(result&&result.evidence&&result.evidence.observations)||{};
 const state=(result&&result.learning_state)||'';
 const seconds=fresh?Number(o.near_work_seconds!==undefined?o.near_work_seconds:(o.focus_seconds||0)):null;
 const seated=fresh?Number(o.presence_seconds||0):null;
 const seatedMinutes=seated===null?null:Math.floor(seated/60);
 const minutes=seconds===null?null:Math.floor(seconds/60);
 const remain=seconds===null?null:Math.max(0,20-minutes);
 const calibrated=!(result&&result.evidence&&result.evidence.version===2&&!result.evidence.fatigue_calibrated);
 const fatigue=fresh&&calibrated?Number(result.fatigue_level||0):null;
 const eyeWord=fatigue===null?'还在熟悉你的用眼状态':eyeFatigueWord(fatigue);
 const alertState=['distracted_phone','distracted_away','fatigued'].includes(state);
 const restMinutes=REST_TRACK.lastRestAt?Math.floor((Date.now()-REST_TRACK.lastRestAt)/60000):null;
 const restLong=restMinutes!==null&&restMinutes>=45;

 const eyeValue=minutes===null?'等待画面':(minutes<1?'刚刚开始':'连续 '+minutes+' 分钟');
 const eyeNote=minutes===null?'画面里出现人就开始计时'
  :o.break_due?'已连续用眼约 20 分钟，起来远眺一下'
  :minutes<1?'刚坐下，先不用休息'
  :(remain<=0?eyeWord+'，先起来远眺':eyeWord+'，还有 '+remain+' 分钟就该远眺');
 const seatValue=seatedMinutes===null?'等待画面':(seatedMinutes<1?'刚刚入座':'连续在位 '+seatedMinutes+' 分钟');
 const seatNote=seatedMinutes===null?'画面里出现人就开始计时'
  :o.posture_tilt?(seatedMinutes>=45?'坐姿有点歪，也该起来走两步了':'坐姿有点歪，坐直一点')
  :seatedMinutes>=45?'已连续在位较久，起来走两步'
  :(o.posture_assessable?'未见持续肩部倾斜':'坐姿暂无法评估');

 host.replaceChildren();

 healthCell(host,{
  label:'用眼负荷',
  value:eyeValue,
  tone:(fresh&&(o.break_due||(fatigue!==null&&fatigue>=0.6)))?'warn':'normal',
  note:eyeNote
 });

 healthCell(host,{
  label:'久坐与体态',
  value:seatValue,
  tone:(fresh&&(o.posture_tilt||seatedMinutes>=45))?'warn':'normal',
  note:seatNote
 });

 healthCell(host,{
  label:'注意力与心理',
  value:fresh?healthActivityText(state):'等待画面',
  tone:(fresh&&alertState)?'warn':'normal',
  note:fresh?(healthActivityNote(state)||'画面里没有需要提醒的地方'):'画面里出现人就会显示当前活动'
 });

 healthCell(host,{
  label:'作息与休息',
  value:REST_TRACK.resting?'正在休息':(REST_TRACK.lastRestAt?restAgoText(REST_TRACK.lastRestAt):'还没有休息记录'),
  tone:restLong?'warn':'normal',
  note:REST_TRACK.resting?'休息也是学习的一部分'
   :restMinutes===null?'今天还没有休息记录，记得起身活动'
   :restLong?'距建议休息已经超时，起身活动一下'
   :'休息节奏正常'
 });
}

/* ④ 健康记录分栏：四个维度各一栏，点击即筛选 */
function renderHistoryColumns(rows){
 const host=$('historyColumns');if(!host)return;
 const current=($('historyBehavior')&&$('historyBehavior').value)||'all';
 const totals={};for(const d of HEALTH_DIMENSIONS)totals[d.key]={samples:0,sessions:0};
 let valid=0;
 for(const s of rows||[]){
  valid+=Number((s&&s.valid_samples)||0);
  const dims=(s&&s.dimensions)||{};
  for(const d of HEALTH_DIMENSIONS){
   const n=Number(dims[d.key]||0);
   if(n>0){totals[d.key].samples+=n;totals[d.key].sessions+=1}
  }
 }
 host.replaceChildren();
 for(const d of HEALTH_DIMENSIONS){
  const t=totals[d.key];
  const share=valid?Math.round(t.samples/valid*100):null;
  const btn=element('button',undefined,'history-column');
  btn.type='button';
  btn.dataset.dim=d.key;
  btn.setAttribute('aria-pressed',String(current===d.key));
  btn.append(element('small',d.label));
  btn.append(element('strong',t.samples?String(t.samples):'—'));
  btn.append(element('span',t.sessions?t.sessions+' 段 · 占有效样本 '+share+'%':'当前范围暂无相关样本'));
  btn.onclick=()=>{
   const next=current===d.key?'all':d.key;
   if($('historyBehavior'))$('historyBehavior').value=next;
   renderHistory();
  };
  host.append(btn);
 }
}

/* 历史记录按健康维度筛选：使用后端按维度精确计数 */
function historyDimensionMatch(s){
 const dim=($('historyBehavior')&&$('historyBehavior').value)||'all';
 if(dim==='all')return true;
 const dims=(s&&s.dimensions)||null;
 if(!dims)return false;
 return Number(dims[dim]||0)>0;
}

/* ================= 互斥主归属（可加总 100%） =================
   与后端 health_dimensions.PRIMARY 对应：每个状态只归一个主维度，
   用于"时间构成"这类需要加总的呈现；与上面的可重叠维度分栏并存。 */
const HEALTH_PRIMARY_ORDER=[
 {key:'vision',   label:'用眼负荷'},
 {key:'sedentary',label:'久坐与体态'},
 {key:'attention',label:'注意力'},
 {key:'data',     label:'数据状态'}
];
function healthPrimaryLabel(key){const d=HEALTH_PRIMARY_ORDER.find(x=>x.key===key);return d?d.label:key}

/* ① 样本构成：互斥堆叠条 + 图例 */
function renderHistoryComposition(rows){
 const host=$('historyComposition');if(!host)return;
 const totals={};let total=0;
 for(const s of rows||[]){
  const p=(s&&s.primary)||{};
  for(const k in p){totals[k]=(totals[k]||0)+Number(p[k]||0);total+=Number(p[k]||0)}
 }
 host.replaceChildren();
 const compHead=element('div',undefined,'composition-head');
 compHead.append(element('h3','样本构成'),helpBox('样本构成','每个状态只归入一个主维度（按最该被干预的方向），因此四项之和为 100%。同一状态在下方"维度分栏"里可能同时出现。'));
 host.append(compHead);
 if(!total){
  host.append(element('p','当前范围还没有有效观察样本。设备识别到人后会自动开始记录。','muted'));
  return;
 }
 const track=element('div',undefined,'composition-bar');
 for(const d of HEALTH_PRIMARY_ORDER){
  const n=totals[d.key]||0;if(!n)continue;
  const seg=element('i',undefined,'composition-seg seg-'+d.key);
  seg.style.width=(n/total*100)+'%';
  seg.title=d.label+' · '+n+' 个样本';
  track.append(seg);
 }
 host.append(track);
 const legend=element('div',undefined,'composition-legend');
 for(const d of HEALTH_PRIMARY_ORDER){
  const n=totals[d.key]||0;if(!n)continue;
  const item=element('span',undefined,'composition-item');
  item.append(element('i',undefined,'seg-'+d.key));
  item.append(element('b',d.label));
  item.append(element('em',(n/total*100).toFixed(1)+'% · '+n+' 个'));
  legend.append(item);
 }
 host.append(legend);
}

/* ================= 健康分析的子模块（小界面选项） =================
   五个子标签：用眼健康 / 久坐与姿态 / 疲劳与节律 / 注意力与心理 / 数据分析。
   分工：能"度量"的用独立物理量（时长、连续值），只能"解释"的用状态分类。 */
const HEALTH_TABS=[
 {key:'vision', label:'用眼健康'},
 {key:'posture',label:'久坐与姿态'},
 {key:'fatigue',label:'疲劳与节律'},
 {key:'mood',   label:'注意力与心理'}
];
let HEALTH_TAB='vision';

let HEALTH_ROWS=[];      // 当前时间范围内的记录，供各维度面板里的标志位统计使用

function healthTab(key){return HEALTH_TABS.find(t=>t.key===key)||{key:key,label:key}}
function panelHead(title,scope){
 const box=element('div',undefined,'panel-head');
 const row=element('div',undefined,'panel-head-row');
 row.append(element('h3',title),helpBox(title,scope));
 box.append(row);
 return box;
}
/* 面板里的解释性小字统一收进标题旁的问号：面板内只留数字、图表和可点的按钮；
   找不到问号时才退回可见段落，保证说明不会丢。 */
function panelNote(host,text){
 const scope=host&&host.closest?host.closest('.health-panel'):null;
 const pop=(host&&host.querySelector('.panel-head .help-pop'))||(scope&&scope.querySelector('.panel-head .help-pop'));
 if(pop){pop.append(element('p',text));return document.createDocumentFragment()}
 return element('p',text,'panel-note');
}
function metricTile(label,value,unit,pct,tone){
 const box=element('div',undefined,'metric-tile'+(tone?' tone-'+tone:''));
 box.append(element('small',label,'metric-label'));
 const figure=element('strong',value===null||value===undefined?'—':String(value),'metric-figure'+(typeof value==='string'&&/[\u4e00-\u9fff]/.test(value)?' metric-words':''));
 if(unit)figure.append(element('em',unit));
 box.append(figure);
 if(pct!==null&&pct!==undefined){
  const bar=element('div',undefined,'bar'),fill=element('i');
  fill.style.width=Math.max(0,Math.min(100,Number(pct)||0))+'%';bar.append(fill);box.append(bar);
 }
 return box;
}
function renderHealthTabs(){
 const host=$('healthTabs');if(!host)return;
 host.replaceChildren(...HEALTH_TABS.map(t=>{
  const b=element('button',t.label,'health-tab');
  b.type='button';
  b.dataset.tab=t.key;
  b.setAttribute('role','tab');
  b.setAttribute('aria-selected',String(HEALTH_TAB===t.key));
  b.onclick=()=>{HEALTH_TAB=t.key;renderHealthTabs();renderHealthPanels()};
  return b;
 }));
 document.querySelectorAll('.health-panel').forEach(p=>{p.hidden=p.dataset.panel!==HEALTH_TAB});document.dispatchEvent(new Event('health:tab'));
}

function renderVisionPanel(){
 const host=$('visionPanel');if(!host)return;
 const e=(HEALTH_SUMMARY&&HEALTH_SUMMARY.eye)||{};
 host.replaceChildren();
 host.append(panelHead('用眼健康','近距离用眼 = 看书 / 写字 / 看屏幕。它只依赖"画面可用 + 有脸 + 视线朝向"，不依赖状态分类，所以不受"活动未确认"影响。'));
 const grid=element('div',undefined,'metric-grid');
 const longest=e.longest_near_work_minutes;
 grid.append(metricTile('今日累计近距离用眼',e.near_work_minutes,'分钟'));
 grid.append(metricTile('最长连续用眼',longest,'分钟',longest==null?null:longest/20*100,(longest||0)>=20?'warn':''));
 grid.append(metricTile('今日屏幕暴露',e.screen_minutes,'分钟'));
 grid.append(metricTile('今日用眼状态',fatigueStatus(HEALTH_SUMMARY?.fatigue),null));
 host.append(grid);
 host.append(panelNote(host,'可评估样本 '+(e.assessable_pct==null?'—':e.assessable_pct+'%')+'（脸清晰可见才计入）。持续使用屏幕时由小智语音提醒休息。时长来自逐帧累积的秒数，不是样本数换算。'));
}

function renderPosturePanel(){
 const host=$('posturePanel');if(!host)return;
 const p=(HEALTH_SUMMARY&&HEALTH_SUMMARY.posture)||{};
 host.replaceChildren();
 host.append(panelHead('久坐与姿态','在位 = 画面中有人；它不等于久坐时长。坐姿只观察肩部持续倾斜，不诊断脊柱问题。'));
 const grid=element('div',undefined,'metric-grid');
 grid.append(metricTile('今日累计在位',p.presence_minutes,'分钟'));
 grid.append(metricTile('最长连续在位',p.longest_presence_minutes,'分钟'));
 grid.append(metricTile('坐姿倾斜样本',p.tilt_samples,'个',null,(p.tilt_samples||0)>0?'warn':''));
 grid.append(metricTile('坐姿判断情况',coverageStatus(p.assessable_pct),null));
 host.append(grid);
 if((p.reasons||[]).length){
  const list=element('div',undefined,'reason-list');
  list.append(element('small','姿态无法评估的原因（多数属于取景问题，可按提示调整）'));
  for(const r of p.reasons)list.append(element('span',r.label+' · '+r.count+' 个样本','reason-chip'));
  host.append(list);
 }
 host.append(panelNote(host,'姿态可评估要求肩、髋四个关键点都清晰可见。若原因集中在"肩或髋被遮挡""身体超出画面"，调整摄像头角度比调算法更有效。'));
}

function renderFatiguePanel(){
 const host=$('fatiguePanel');if(!host)return;
 host.replaceChildren();
 host.append(panelHead('疲劳与节律','结合闭眼、眨眼和打哈欠等画面迹象回顾疲劳变化；观察不足时显示暂无法判断。'));
 const grid=element('div',undefined,'metric-grid');
 grid.append(metricTile('今日疲劳观察',fatigueStatus(HEALTH_SUMMARY?.fatigue),null));
 const rows=HEALTH_ROWS||[];
 const buckets=new Array(24).fill(0);
 for(const s of rows){
  const h=new Date(s.start_time).getHours();
  buckets[h]+=Number(s.valid_samples||0);
 }
 let peak=-1,peakN=0;
 buckets.forEach((n,i)=>{if(n>peakN){peak=i;peakN=n}});
 grid.append(metricTile('记录最集中的时段',peak<0?null:(String(peak).padStart(2,'0')+':00'),null));
 grid.append(metricTile('该范围有效样本',rows.reduce((a,s)=>a+Number(s.valid_samples||0),0),'个'));
 host.append(grid);
 if(peakN>0){
  const max=Math.max.apply(null,buckets)||1;
  const bars=element('div',undefined,'hour-bars trend-bars');
  buckets.forEach((n,h)=>{
   const cell=element('div',undefined,'hour-bar');
   const track=element('div',undefined,'bar'),fill=element('i');
   fill.style.height=(n/max*100)+'%';track.append(fill);
   cell.append(track,element('small',h%3===0?String(h):''));
   bars.append(cell);
  });
  host.append(panelNote(host,'记录时段分布（按小时，柱高为相对样本数）'));
  host.append(bars);
 }
 host.append(panelNote(host,'样本数不等于时长；这里只描述"什么时候有记录"，不换算成分钟。'));
}

function renderQualityPanel(){
 const host=$('qualityPanel');if(!host)return;

 const s=HEALTH_SUMMARY||{};
 host.replaceChildren();
 host.append(panelHead('今日识别覆盖','本节仅统计今天，与上方所选记录范围分开。用于理解哪些样本可评估。'));
 const grid=element('div',undefined,'metric-grid');

 grid.append(metricTile('今日有效样本',s.samples,'个'));
 grid.append(metricTile('用眼判断情况',coverageStatus((s.eye||{}).assessable_pct),null));
 grid.append(metricTile('坐姿判断情况',coverageStatus((s.posture||{}).assessable_pct),null));
 host.append(grid);
 const unc=s.uncertainty||[];
 if(unc.length){
  const list=element('div',undefined,'reason-list');
  list.append(element('small','活动未确认的原因分布'));
  for(const r of unc)list.append(element('span',r.label+' · '+r.count+' 个样本','reason-chip'));
  host.append(list);
 }
 host.append(panelNote(host,'"活动未确认"不代表没有学习，也不计作分心——它只表示当前证据不足以确定具体行为。确认率偏低时优先改善取景与光线。'));
}

function renderHealthPanels(){
 renderVisionPanel();renderPosturePanel();renderFatiguePanel();renderQualityPanel();if(typeof renderDataAnalysis==='function')renderDataAnalysis();
 // 标志位筛选分发到各自所属的观测维度面板
 renderFlagChips($('visionPanel'),['eye'],HEALTH_ROWS);
 renderFlagChips($('posturePanel'),['posture'],HEALTH_ROWS);
 renderFocusPanel();renderFlagChips($('focusFlags'),['attention'],HEALTH_ROWS);
}
function renderHealthAnalysis(rows){
 if(rows)HEALTH_ROWS=rows;
 renderHealthTabs();renderHealthPanels();
}

/* ================= 风险标志位筛选（三态 · 可重叠 · OR） =================
   标志位由后端按测量值判定并落列：命中=1 / 未命中=0 / 无法判定=null。
   这里只做"命中任意一个选中标志位就显示该段"（OR），因为前端一次通常只看一个影响因素。 */
const HEALTH_FLAG_FILTER=new Set();

function flagDefs(){
 const s=(HEALTH_SUMMARY&&HEALTH_SUMMARY.risk&&HEALTH_SUMMARY.risk.flags)||[];
 return s.filter(f=>f.group!=='quality');   // 数据质量单独看，不算健康风险
}

/* 把某个分组的标志位按钮渲染进它所属的观测维度面板里。
   选中状态是全局的（HEALTH_FLAG_FILTER），所以切到别的维度再切回来仍然保留。 */
function renderFlagChips(host, groups, rows){
 if(!host)return;
 const defs=flagDefs().filter(f=>groups.includes(f.group));
 if(!defs.length)return;
 const counts={};
 for(const d of defs)counts[d.key]=0;
 for(const s of rows||[]){
  const rf=(s&&s.risk_flags)||{};
  for(const d of defs)if(Number(rf[d.key]||0)>0)counts[d.key]+=1;
 }
 // 复用同一个容器并整体替换内容，避免多次渲染叠加出多份
 let box=host.querySelector('.panel-flags');
 if(!box){box=element('div',undefined,'panel-flags');host.append(box)}
 box.replaceChildren();
 box.append(element('small','这一维度的风险标志位（可多选：命中任一条即筛出该段记录）'));
 const row=element('div',undefined,'flag-row');
 for(const d of defs){
  const on=HEALTH_FLAG_FILTER.has(d.key);
  const b=element('button',undefined,'flag-chip'+(on?' on':''));
  b.type='button';
  b.append(element('span',d.label));
  b.append(element('em',counts[d.key]+' 段'));
  b.title=(d.scope||'')+(d.unknown?('；今日 '+d.unknown+' 个样本无法判定'):'');
  b.onclick=()=>{on?HEALTH_FLAG_FILTER.delete(d.key):HEALTH_FLAG_FILTER.add(d.key);renderHistory()};
  row.append(b);
 }
 if(HEALTH_FLAG_FILTER.size){
  const clear=element('button','清除筛选','flag-clear');
  clear.type='button';
  clear.onclick=()=>{HEALTH_FLAG_FILTER.clear();renderHistory()};
  row.append(clear);
 }
 box.append(row);
 box.append(panelNote(host,'只匹配【命中】的样本；【无法判定】表示该维度本次没测出来，不等于没问题，也不会被筛进来。'));
 host.append(box);
}

function historyFlagMatch(s){
 if(!HEALTH_FLAG_FILTER.size)return true;
 const rf=(s&&s.risk_flags)||{};
 for(const k of HEALTH_FLAG_FILTER)if(Number(rf[k]||0)>0)return true;   // OR
 return false;
}

function resetHealthView(){HEALTH_SUMMARY=null;HEALTH_ROWS=[];}

function renderFocusPanel(){
 const host=$('stressTrend');if(!host)return;host.replaceChildren();
 host.append(panelHead('注意力与心理','回顾已观察到的行为，手机使用不代表娱乐，视线离开也可能是正常思考。'));
 const s=HEALTH_SUMMARY||{},rows=s.distribution||[],count=key=>rows.find(r=>r.state===key)?.count||0;
 const grid=element('div',undefined,'metric-grid');
 grid.append(metricTile('手机使用样本',count('distracted_phone'),'个'));
 grid.append(metricTile('视线离开样本',count('distracted_away'),'个'));
 grid.append(metricTile('已识别投入样本占比',s.focus_pct,'%'));
 host.append(grid,panelNote(host,'需要确认具体用途时，回看对应事件截图，再决定是否调整下一段学习安排。'));
}
