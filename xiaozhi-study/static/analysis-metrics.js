/* Deterministic aggregation of the exact record range displayed in the UI. */
(function(exports){
 const num=v=>Math.max(0,Number(v)||0);
 function summarize(rows=[]){
  const result={records:rows.length,samples:0,unknown:0,behaviors:{engaged:0,phone:0,away:0,rest:0,fatigue:0,other:0},days:[]},days=new Map();
  for(const row of rows){
   const total=num(row.valid_samples);result.samples+=total;result.unknown+=num(row.primary?.data);
   let classified=0;for(const key of ['engaged','phone','away','rest','fatigue']){const count=num(row.behaviors?.[key]);result.behaviors[key]+=count;classified+=count}result.behaviors.other+=Math.max(0,total-classified);
   const stamp=new Date(row.start_time);if(Number.isNaN(stamp.getTime()))continue;
   const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(stamp);
   if(!days.has(date))days.set(date,{date,samples:0,phone:0,engaged:0,unknown:0,records:0});const day=days.get(date);day.samples+=total;day.phone+=num(row.behaviors?.phone);day.engaged+=num(row.behaviors?.engaged);day.unknown+=num(row.primary?.data);day.records++;
  }
  result.unknown=Math.min(result.samples,result.unknown);result.confirmed=result.samples-result.unknown;result.confirmedPct=result.samples?Math.round(result.confirmed/result.samples*100):null;
  result.days=[...days.values()].sort((a,b)=>a.date.localeCompare(b.date));
  return result;
 }
 function dateKey(value){const d=new Date(value);return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(d)}
 function inRange(rows=[],range='all',now=new Date()){
  if(range==='all')return rows;
  const today=dateKey(now),base=new Date(today+'T00:00:00Z');if(range==='week')base.setUTCDate(base.getUTCDate()-6);const first=base.toISOString().slice(0,10);
  return rows.filter(row=>{const day=dateKey(row.start_time);return day&&day>=first&&day<=today});
 }
 function compareDays(days=[]){
  if(days.length<2)return null;const split=Math.floor(days.length/2),early=days.slice(0,split),late=days.slice(split),sum=(ds,key)=>ds.reduce((n,d)=>n+num(d[key]),0),a=sum(early,'samples'),b=sum(late,'samples');
  const metrics=['engaged','phone','unknown'].map(key=>{const rate=(ds,total)=>total?(key==='unknown'?1-sum(ds,key)/total:sum(ds,key)/total)*100:null;const before=rate(early,a),after=rate(late,b);return {key,before,after,change:before===null||after===null?null:after-before}});
  return {early,late,metrics};
 }
 function csvCell(value){let s=String(value??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'}
 function csv(rows){return '\uFEFF'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n')}
 exports.dateKey=dateKey;exports.inRange=inRange;exports.compareDays=compareDays;exports.summarize=summarize;exports.csv=csv;
})(typeof module!=='undefined'?module.exports:(window.AnalysisMetrics={}));
