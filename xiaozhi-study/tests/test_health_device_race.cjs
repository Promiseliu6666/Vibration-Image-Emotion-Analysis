const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/health-habits.js'),'utf8').split("$('healthDone').onclick")[0];
let resolveRequest,written=[];const elements=new Map();
const context={selected:'device-a',workspaceUser:{username:'test'},performance:{now:()=>0},Date,localStorage:{setItem:(k,v)=>written.push(k),getItem:()=>null},document:{hidden:false,querySelectorAll:()=>[]},$:id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id)},api:()=>new Promise(r=>resolveRequest=r),notify:()=>{},data:{devices:[]}};
vm.createContext(context);vm.runInContext(source,context);vm.runInContext('renderHealthWindow=()=>{};renderHealthHabits=()=>{};',context);
(async()=>{
 vm.runInContext("healthWindow={id:1};",context);const stop=vm.runInContext('stopHealthWindow()',context);
 context.selected='device-b';vm.runInContext('healthWindow={id:2};',context);resolveRequest({});await stop;
 assert.equal(vm.runInContext('healthWindow.id',context),2);
 context.selected='device-a';vm.runInContext("healthKind='break';healthWindowPromptId=1;",context);const response=vm.runInContext("respondHealth('done')",context);
 context.selected='device-b';resolveRequest({});await response;
 assert.ok(written.includes('health-window:test:device-a:1'));
 assert.ok(!written.includes('health-window:test:device-b:1'));
 console.log('PASS stop response and reminder acknowledgement remain isolated after device switch');
})().catch(e=>{console.error(e);process.exitCode=1});
