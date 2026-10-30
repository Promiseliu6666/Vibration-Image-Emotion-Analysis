const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/console.js'),'utf8');
const code=source.slice(source.indexOf('function recordQuery()'),source.indexOf('\nfunction historySpecial'));
const els=new Map(),pending=[];let paints=0;
const get=id=>{if(!els.has(id))els.set(id,{value:'all',textContent:'',setAttribute(){},removeAttribute(){},replaceChildren(){}});return els.get(id)};
const c={selected:'a',page:'history',historyDayFilter:'',recordScope:'',recordLimit:50,recordRenderKey:'',historyRows:[],historyRequest:0,historyLoading:false,historyController:null,
 URLSearchParams,AbortController,Date,JSON,document:{activeElement:null,querySelector:()=>null,querySelectorAll:()=>[]},$:get,
 api:url=>new Promise((resolve,reject)=>pending.push({url,resolve,reject})),renderHistory:()=>paints++,element:()=>({}),button:()=>({})};
vm.createContext(c);vm.runInContext(code,c);
(async()=>{
 const first=c.loadHistory();assert.match(pending[0].url,/period=all/);
 c.selected='b';const second=c.loadHistory();pending[1].resolve([{id:2,device_id:'b'}]);await second;
 pending[0].resolve([{id:1,device_id:'a'}]);await first;
 assert.equal(c.historyRows[0].device_id,'b');assert.equal(paints,1);
 const unchanged=c.loadHistory(true);pending[2].resolve([{id:2,device_id:'b'}]);await unchanged;
 assert.equal(paints,1,'unchanged poll must preserve current DOM');
 c.recordLimit=100;c.recordQuery();assert.equal(c.recordLimit,100);
 get('historyRange').value='week';c.recordQuery();assert.equal(c.recordLimit,50);assert.equal(c.historyRows.length,0);
 c.historyDayFilter='2026-10-01';assert.equal(c.recordQuery().params.get('day'),'2026-10-01');
 const more=c.loadMoreRecords();assert.match(pending[3].url,/limit=100/);pending[3].resolve([]);await more;
 console.log('PASS device races, unchanged polling, calendar scope and incremental record loading');
})().catch(e=>{console.error(e);process.exitCode=1});
