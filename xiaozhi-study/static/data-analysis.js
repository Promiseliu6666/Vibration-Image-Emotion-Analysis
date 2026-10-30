/* Consolidated analysis services. Records, CSV and reports each have one owner. */
/* 小节标题行：解释性小字收进标题旁的问号，小节里只留结论、图表和可点的按钮。 */
function sectionHead(title,note){const row=element('div',undefined,'analysis-head-row');row.append(element('h3',title));if(note)row.append(helpBox(title,note));return row}
function openDataAnalysis(report=false){
 goPage('analytics');renderDataAnalysis();
 if(report){$('habitReports').open=true;document.dispatchEvent(new Event('analysis:report'))}
 $('dataAnalysisPanel').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
}
function dataRangeLabel(){return {today:'今天',week:'近7天',all:'全部已载入记录'}[$('dataRange').value]||'当前范围'}
function analysisRows(){return AnalysisMetrics.inRange(historyRows||[],$('dataRange').value)}
let analysisRenderKey='';
function renderDataAnalysis(){
 const host=$('analysisOverview');if(!host)return;
 const rows=analysisRows();
 if(historyLoading&&!rows.length){analysisRenderKey='';host.replaceChildren(element('p','正在读取所选范围的分析数据…','report-loading'));$('analysisExtensions').replaceChildren();$('analysisRangeNote').textContent=dataRangeLabel()+' · 正在更新';$('exportAnalysisSummary').disabled=true;return;}
 const key=JSON.stringify([selected,$('dataRange').value,recordLimit,rows]);if(key===analysisRenderKey)return;analysisRenderKey=key;const s=AnalysisMetrics.summarize(rows);host.replaceChildren();
 $('analysisRangeNote').textContent=dataRangeLabel()+' · '+s.records+' 段记录 · '+s.samples+' 个有人样本（当前载入上限 '+recordLimit+' 段）';
 $('exportAnalysisSummary').disabled=!s.samples;
 const layout=element('div',undefined,'analysis-overview-grid'),graph=element('section',undefined,'analysis-behavior'),quality=element('section',undefined,'analysis-confidence');
 graph.append(sectionHead('活动分布','每个样本仅归入一类；其他活动包括站立等未单列行为。比例不等于持续时长。'));const wrap=element('div',undefined,'analysis-ring-layout'),ring=element('div',undefined,'analysis-ring'),center=element('div',undefined,'analysis-ring-center');center.append(element('strong',String(s.samples)),element('span','有人样本'));ring.append(center);
 const specs=[['engaged','学习活动','#638574'],['phone','使用手机','#c9a35b'],['away','视线离开','#8d9baa'],['rest','休息','#b19e82'],['fatigue','疲劳迹象','#b9826e'],['other','其他 / 未确认活动','#dbe2d1']],legend=element('div',undefined,'analysis-ring-legend');let degree=0;const stops=[];
 for(const [key,label,color] of specs){const count=s.behaviors[key];if(!count)continue;const start=degree,pct=count/s.samples*100;degree+=pct*3.6;stops.push(color+' '+start+'deg '+degree+'deg');const row=element('div',undefined,'analysis-legend-row'),dot=element('i');dot.style.background=color;row.append(dot,element('span',label),element('strong',pct.toFixed(1)+'%'),element('small',count+' 个'));legend.append(row)}
 ring.style.background=stops.length?'conic-gradient('+stops.join(',')+')':'#e4e9db';ring.setAttribute('role','img');ring.setAttribute('aria-label',s.samples?'活动分布：'+specs.filter(([key])=>s.behaviors[key]).map(([key,label])=>label+' '+Math.round(s.behaviors[key]/s.samples*100)+'%').join('，'):'暂无活动样本');if(!s.samples)legend.append(element('p','这个范围还没有可分析的记录。','muted'));wrap.append(ring,legend);graph.append(wrap);
 quality.append(element('h3','这些记录有多清楚？'));const pct=element('strong',s.confirmedPct===null?'—':s.confirmedPct+'%','analysis-confidence-value');quality.append(pct,element('p','活动确认率'),element('p',s.samples?'已确认 '+s.confirmed+' 个 · 未确认 '+s.unknown+' 个':'记录产生后，会显示活动确认情况。','muted'));
 const bar=element('div',undefined,'bar'),fill=element('i');fill.style.width=(s.confirmedPct||0)+'%';bar.append(fill);quality.append(bar);
 quality.append(element('p',s.confirmedPct===null?'先积累一些记录，再回顾行为变化。':s.confirmedPct<50?'当前有较多活动未确认。回顾时优先查看有明确行为与截图的片段，不把未确认当作分心。':'已确认的活动可用于回顾习惯；仍需结合具体片段理解。','analysis-verdict'));
 layout.append(graph,quality);host.append(layout);
 const bottom=element('div',undefined,'analysis-insight-grid'),daily=element('section'),priority=element('section');daily.append(sectionHead('每天的活动变化','绿色为学习活动，金色为手机使用。每天只统计已载入范围的记录。'));
 if(!s.days.length)daily.append(element('p','有记录后，将按日期展示变化。','muted'));
 for(const day of s.days){const row=element('div',undefined,'analysis-day'),track=element('div',undefined,'analysis-day-track');for(const [count,color,label] of [[day.engaged,'#638574','学习活动'],[day.phone,'#c9a35b','使用手机'],[Math.max(0,day.samples-day.engaged-day.phone),'#dbe2d1','其余活动']]){if(!count)continue;const seg=element('i');seg.style.width=count/day.samples*100+'%';seg.style.background=color;seg.title=label+' '+count+' 个样本';track.append(seg)}row.append(element('time',day.date.slice(5)),track,element('small',day.samples+' 个'));daily.append(row)}
 priority.append(element('h3','先回顾这几段'));const notable=rows.filter(r=>(r.behaviors?.phone||0)+(r.behaviors?.fatigue||0)>0).sort((a,b)=>(b.behaviors?.phone||0)+(b.behaviors?.fatigue||0)-(a.behaviors?.phone||0)-(a.behaviors?.fatigue||0)).slice(0,3);
 for(const row of notable){const b=element('button',undefined,'analysis-priority');b.type='button';b.append(element('span',new Date(row.start_time).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})),element('small','手机 '+(row.behaviors?.phone||0)+' 个 · 疲劳 '+(row.behaviors?.fatigue||0)+' 个'));b.onclick=()=>openDetail(row.id);priority.append(b)}
 if(!notable.length)priority.append(element('p','这个范围没有手机使用或疲劳迹象的记录。','muted'));
 bottom.append(daily,priority);host.append(bottom);renderAnalysisExtensions(rows,s);
}
function exportAnalysisSummary(){
 const rows=analysisRows(),s=AnalysisMetrics.summarize(rows);if(!selected||!s.samples)return;
 const name=$('device').selectedOptions[0]?.textContent||selected;
 const records=[['设备',name],['统计范围',dataRangeLabel()],['统计口径','当前载入范围内的记录（上限 '+recordLimit+' 段），样本占比不代表时长'],['记录段数',s.records],['有人样本',s.samples],['已确认活动',s.confirmed],['未确认活动',s.unknown],['活动确认率',s.confirmedPct+'%'],[],['日期','有人样本','学习活动样本','手机使用样本','未确认样本','记录段数'],...s.days.map(d=>[d.date,d.samples,d.engaged,d.phone,d.unknown,d.records])];
 const blob=new Blob([AnalysisMetrics.csv(records)],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=element('a');a.href=url;a.download='数据分析摘要-'+AnalysisMetrics.dateKey(new Date())+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('分析摘要已导出');
}
$('exportAnalysisSummary').onclick=exportAnalysisSummary;
$('openMonthlyFromLive').onclick=()=>openDataAnalysis();
$('discussAnalysis').onclick=()=>window.XiaozhiAssistant?.open();
document.addEventListener('workspace:device',()=>{historyRows=[];HEALTH_ROWS=[];HEALTH_SUMMARY=null;analysisRenderKey='';renderHealthAnalysis();});
$('dataRange').onchange=()=>void loadHistory();
$('refreshData').onclick=()=>loadHistory();
function renderAnalysisExtensions(rows,s){
 const host=$('analysisExtensions');host.replaceChildren();
 const section=(title,note)=>{const box=element('section',undefined,'analysis-deep-section');box.append(sectionHead(title,note));return box};
 const compare=section('前后阶段，有什么变化？','按有记录的日期分为前、后两组；比较样本占比，不能代表全天表现。');
 if(s.days.length<2)compare.append(element('p','至少积累两天记录后，这里会比较学习活动、手机使用和活动确认情况。','muted'));
 else {const comparison=AnalysisMetrics.compareDays(s.days),{early,late}=comparison;compare.append(element('p',early[0].date+' 至 '+early.at(-1).date+'  /  '+late[0].date+' 至 '+late.at(-1).date,'muted'));const grid=element('div',undefined,'analysis-comparison');for(const metric of comparison.metrics){const labels={engaged:'学习活动',phone:'手机使用',unknown:'活动确认'},x=metric.before,y=metric.after,box=element('div');box.append(element('span',labels[metric.key]),element('strong',x===null||y===null?'暂无可比较样本':x.toFixed(1)+'% → '+y.toFixed(1)+'%'),element('small',metric.change===null?'':Math.abs(metric.change)<.05?'基本持平':(metric.change>0?'增加 ':'减少 ')+Math.abs(metric.change).toFixed(1)+' 个百分点'));grid.append(box)}compare.append(grid)}

 const periods=section('手机记录更常从哪个时段开始？','按记录开始时间归组，一段中的样本全部归入该时段；用于寻找回看线索，不是逐小时使用时长。');const bins=[{name:'清晨 · 00–06',samples:0,phone:0,records:0},{name:'上午 · 06–12',samples:0,phone:0,records:0},{name:'下午 · 12–18',samples:0,phone:0,records:0},{name:'晚间 · 18–24',samples:0,phone:0,records:0}];
 for(const r of rows){const date=new Date(r.start_time);if(Number.isNaN(date.getTime()))continue;const hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',hour:'2-digit',hourCycle:'h23'}).format(date));const bin=bins[Math.floor(hour/6)];if(!bin)continue;bin.samples+=Number(r.valid_samples)||0;bin.phone+=Number(r.behaviors?.phone)||0;bin.records++}
 const max=Math.max(1,...bins.map(x=>x.phone));for(const bin of bins){const line=element('div',undefined,'analysis-period-row'),bar=element('div',undefined,'analysis-period-bar'),fill=element('i');fill.style.width=bin.phone/max*100+'%';bar.append(fill);line.append(element('span',bin.name),bar,element('small',bin.phone+' 个手机样本 / '+bin.records+' 段'));periods.append(line)}
 const plan=section('下一步，可以从这里开始','建议只围绕日常行为，结合实际情况选择一项尝试。');const tips=[];if(s.behaviors.phone)tips.push(['减少手机打断','开始下一段学习前，把手机放到伸手拿不到的位置；需要查看时集中处理，再回到当前任务。']);if(s.behaviors.away)tips.push(['给注意力一个落点','每段开始前写下一个明确的小目标；发现走神时，先完成眼前的一小步，再决定是否休息。']);if(s.behaviors.fatigue)tips.push(['给休息留出位置','出现疲劳感时，暂停当前任务，起身活动或看看远处，状态恢复后再继续。']);if(!s.samples)tips.push(['先留下一段记录','有记录后，再结合具体行为选择需要调整的习惯。']);if(!tips.length)tips.push(['保持有节奏的学习','把大任务拆成能完成的小段，段间留出短暂休息；结束时写下完成的内容和下一步。']);for(const [title,text] of tips){const item=element('div',undefined,'analysis-action');item.append(element('strong',title),element('p',text));plan.append(item)}
 const daily=section('每日明细','将每日观察集中查看，点击日期回到当天记录。');const table=element('table',undefined,'analysis-daily-table'),head=element('thead'),tr=element('tr');for(const title of ['日期','记录段数','有人样本','学习活动占比','手机样本','确认率'])tr.append(element('th',title));head.append(tr);table.append(head);const body=element('tbody');for(const d of [...s.days].reverse()){const line=element('tr'),cell=element('td'),link=element('button',d.date);link.type='button';link.onclick=()=>{historyDayFilter=d.date;$('historyDate').value=d.date;$('historyRange').value='all';$('historyBehavior').value='all';if(typeof HEALTH_FLAG_FILTER!=='undefined')HEALTH_FLAG_FILTER.clear();goPage('history');renderHistory();$('historyDate').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})};cell.append(link);line.append(cell);for(const value of [d.records,d.samples,d.samples?(d.engaged/d.samples*100).toFixed(1)+'%':'—',d.phone,d.samples?Math.round((d.samples-d.unknown)/d.samples*100)+'%':'—'])line.append(element('td',String(value)));body.append(line)}table.append(body);daily.append(table);if(!s.days.length)daily.append(element('p','所选范围还没有记录。可以切换范围，或完成一次监测后再来回顾。','muted'));
 const pair=element('div',undefined,'analysis-deep-grid');pair.append(periods,plan);host.append(compare,pair,daily);
}
