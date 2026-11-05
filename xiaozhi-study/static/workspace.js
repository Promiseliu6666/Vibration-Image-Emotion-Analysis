let workspaceUser=null;
async function initializeWorkspace(){
 try{workspaceUser=await api('/workspace/me');document.body.dataset.role=workspaceUser.role;$('accountLabel').textContent=workspaceUser.username+' · '+(workspaceUser.role==='admin'?'管理员':'共享查看账号');
 if(workspaceUser.must_change_password)notify('当前使用初始密码。启用局域网前，请到系统设置更改密码。');
 if(page==='settings'){loadWorkspace();}if(page==='settings'&&workspaceUser.role==='admin')loadNetworks();renderDevices();renderLive();document.dispatchEvent(new Event('workspace:ready'));
 }catch(e){notify(e.message)}
}
async function loadWorkspace(){
 if(!workspaceUser)return;const admin=workspaceUser.role==='admin';$('adminSettings').hidden=!admin;
 if(!admin){$('workspaceIntro').textContent='这是共享空间。你可以查看设备、健康记录、导出记录，并修改自己的密码。';loadFeedback();return}
 $('workspaceIntro').textContent='在这里管理共享访问、账号和数据保存；网络相关的设置请在运行本机的电脑上操作。';
 loadFeedback();
 try{const [settings,system,accounts]=await Promise.all([api('/workspace/settings'),api('/workspace/system'),api('/workspace/accounts')]);
 $('lanEnabled').checked=settings.lan_enabled;$('retentionDays').value=settings.frame_retention_days;$('onlyAlerts').checked=!settings.save_all_frames;void loadFrames();
 $('systemState').textContent=`数据存储正常 · 已运行 ${Math.floor(system.uptime_seconds/60)} 分钟 · 待处理画面 ${system.queue_used} 个 · 硬盘剩余 ${system.free_disk_gb} GB`;
 $('lanState').textContent=system.lan_listening?'其他设备可以通过本机地址访问':'目前只允许本机访问';if(system.saved_lan_enabled!==system.lan_listening)$('lanState').textContent+=' · 网络设置将在重启后生效';
 $('lanAddresses').replaceChildren();for(const address of system.addresses){const line=element('div',address.adapter+' · '+address.url,'device-id');$('lanAddresses').append(line)}
 if(!system.addresses.length)$('lanAddresses').textContent='没找到可用的网络地址，请检查 Wi-Fi 或网线。';
 $('accountsList').replaceChildren();for(const row of accounts){const line=element('div',undefined,'row');line.append(element('span',row.username+' · '+(row.role==='admin'?'管理员':row.enabled?'可查看':'已停用')));if(row.role!=='admin')line.append(button(row.enabled?'停用':'启用',async()=>{await api('/workspace/accounts/'+encodeURIComponent(row.username),{method:'PATCH',body:JSON.stringify({enabled:!row.enabled})});loadWorkspace()}));$('accountsList').append(line)}
}catch(e){$('systemState').textContent=e.message}
}
async function loadNetworks(){
 if(workspaceUser?.role!=='admin')return;
 try{const rows=await api('/workspace/network-devices');$('networkList').replaceChildren();if(!rows.length)$('networkList').append(element('p','尚未登记网络设备。输入真实 MAC 地址，为每台物理设备生成专属密钥。','muted'));
 for(const row of rows){const line=element('div',undefined,'row');const live=row.live,stage=!row.enabled?'密钥已撤销':live.analysis_fresh?'真实画面与分析正常':live.online?'画面已到达，等待分析':row.network_online?'网络心跳已到达，尚无新画面':'已登记，等待连接';const info=element('div');info.append(element('strong',row.name),element('div',row.hardware_id+' · '+stage,'device-id'),element('small','累计接收 '+row.received_frames+' 帧 · 最近通信 '+dt(row.last_seen)));line.append(info,button(row.enabled?'撤销接入':'重新启用',async()=>{await api('/workspace/network-devices/'+encodeURIComponent(row.device_id),{method:'PATCH',body:JSON.stringify({enabled:!row.enabled})});loadNetworks()}));$('networkList').append(line)}
 const existing=$('networkExisting');const current=existing.value;existing.replaceChildren(element('option','创建独立设备记录'));existing.firstChild.value='';for(const d of data?.devices||[]){const o=element('option',d.name+' · '+d.device_id);o.value=d.device_id;existing.append(o)}existing.value=current;
 }catch(e){$('networkList').textContent=e.message}
}

/* 数据管理 · 纠正记录：核对时提交的对照，本人与查看账号（家长）都能看 */
const FEEDBACK_LABELS={engaged_reading:'阅读',engaged_writing:'书写',engaged_screen:'听讲 / 朝向学习区',engaged_computer:'电脑操作',engaged_hand_raising:'举手互动',engaged_discussing:'讨论交流',standing:'站立活动',distracted_phone:'使用手机',distracted_away:'视线离开',resting:'休息',fatigued:'疲劳信号',thinking:'无法确认具体行为',absent:'无人'};
function feedbackLabel(code){const shared=typeof reviewLabels!=='undefined'?reviewLabels:FEEDBACK_LABELS;return shared[code]||FEEDBACK_LABELS[code]||code}
function fillFeedbackDevices(){
 const select=$('feedbackDevice');if(!select)return;
 const key=(data?.devices||[]).map(d=>d.device_id).join(',');
 if(select.dataset.devices===key)return;
 const current=select.value;
 select.replaceChildren(element('option','全部设备'));select.firstChild.value='';
 for(const d of data?.devices||[]){const option=element('option',d.name||d.device_id);option.value=d.device_id;select.append(option)}
 select.dataset.devices=key;
 if(current&&[...select.options].some(option=>option.value===current))select.value=current;
}
async function loadFeedback(){
 const host=$('feedbackList');if(!host)return;
 fillFeedbackDevices();
 host.textContent='正在读取纠正记录…';
 try{
  const params=new URLSearchParams({device_id:$('feedbackDevice')?.value||'',limit:50});
  const result=await api('/study/feedback?'+params);
  $('feedbackCount').textContent=result.total?'共 '+result.total+' 条（显示最近 '+result.items.length+' 条）':'共 0 条';
  host.replaceChildren();
  if(!result.items.length){host.append(element('p','还没有纠正记录。在实时监控页点“核对并纠正识别”提交后，这里会按时间列出。','muted'));return}
  for(const item of result.items){
   const row=element('div',undefined,'feedback-row');
   const head=element('div',undefined,'row');
   head.append(element('strong',feedbackLabel(item.predicted)+' → '+feedbackLabel(item.corrected)));
   head.append(element('span',new Date(item.created_at).toLocaleString('zh-CN',{hour12:false}),'muted'));
   row.append(head);
   row.append(element('small',(item.device_id||'未知设备')+(item.username?' · '+item.username:'')+(item.has_image?'':' · 没有留图（提交时未勾选“另存这张图片”）')+(item.note?' · 备注：'+item.note:''),'muted'));
   if(item.has_image){
    const box=element('div',undefined,'feedback-shot');
    const toggle=element('button','查看画面');toggle.type='button';
    let shotUrl=null,shot=null;
    toggle.onclick=async()=>{
     if(shot){shot.remove();shot=null;if(shotUrl){URL.revokeObjectURL(shotUrl);shotUrl=null}toggle.textContent='查看画面';return}
     toggle.disabled=true;const label=toggle.textContent;toggle.textContent='正在读取…';
     try{
      const response=await fetch('/api/study/feedback/'+encodeURIComponent(item.id)+'/image',{headers:{Authorization:'Bearer '+token},cache:'no-store'});
      if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.detail||'图片暂未读取')}
      shotUrl=URL.createObjectURL(await response.blob());
      shot=element('img',undefined,'feedback-shot-image');shot.src=shotUrl;shot.alt='这条纠正记录对应的画面';
      box.append(shot);toggle.textContent='收起画面';
     }catch(e){toggle.textContent=label;notify(e.message)}
     finally{toggle.disabled=false}
    };
    box.append(toggle);row.append(box);
   }
   host.append(row);
  }
 }catch(e){host.replaceChildren(element('p','纠正记录暂未读取：'+e.message,'error-text'))}
}
/* 数据管理 · 照片过期管理：统计本机画面占用，按保存天数手动清理一次 */
let framesTimer=null,framesRequest=0;
function framesDays(){const value=Number($('retentionDays')?.value);return Number.isFinite(value)&&value>=1&&value<=90?Math.round(value):null}
function markRangeChips(){const days=framesDays();document.querySelectorAll('.range-chips button').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.days)===days)))}
/* 右侧试算：按当前选择的范围算出"会留多少、会删多少" */
async function loadFrames(days){
 const stats=$('framesStats');if(!stats||workspaceUser?.role!=='admin')return;
 const want=days||framesDays()||7,request=++framesRequest;
 stats.textContent='正在按最近 '+want+' 天试算…';
 try{
  const f=await api('/workspace/frames?days='+want);
  if(request!==framesRequest||want!==framesDays())return;
  stats.textContent=['保存范围：最近 '+f.retention_days+' 天',
   '范围内保留：'+f.kept_files+' 张 · '+f.kept_mb+' MB',
   '超出范围将被删除：'+f.expired_files+' 张 · '+f.expired_mb+' MB',
   '长期保留（提醒截图与纠正图）：'+f.alert_files+' 张 · '+f.alert_mb+' MB'].join('\n');
  const warning=$('framesWarning');
  if(warning){warning.hidden=!f.expired_files;warning.textContent=f.expired_files?'保存后，早于最近 '+f.retention_days+' 天的 '+f.expired_files+' 张普通图片（'+f.expired_mb+' MB）会被清理程序删除；提醒截图与纠正图不受影响。':''}
  markRangeChips();
 }catch(e){if(request===framesRequest)stats.textContent='试算暂未完成：'+e.message}
}
$('passwordForm').onsubmit=async e=>{e.preventDefault();const b=$('changePassword');b.disabled=true;$('passwordError').textContent='';try{const r=await api('/workspace/password',{method:'POST',body:JSON.stringify({current_password:$('currentPassword').value,new_password:$('newPassword').value})});xiaozhiAuth.set(r.access_token);location.replace(xiaozhiAuth.url('/static/dashboard.html?v=19&view=settings#settings'))}catch(e){$('passwordError').textContent=e.message}finally{b.disabled=false}};
$('settingsForm').onsubmit=async e=>{e.preventDefault();$('saveSettings').disabled=true;$('settingsFeedback').textContent='';try{await api('/workspace/settings',{method:'PUT',body:JSON.stringify({lan_enabled:$('lanEnabled').checked})});$('settingsFeedback').textContent='设置已保存。重启程序后生效（先运行 stop.cmd 停止，再运行 start.cmd 启动）。';loadWorkspace()}catch(e){$('settingsFeedback').textContent=e.message}finally{$('saveSettings').disabled=false}};
$('accountForm').onsubmit=async e=>{e.preventDefault();$('createAccount').disabled=true;try{await api('/workspace/accounts',{method:'POST',body:JSON.stringify({username:$('accountName').value,password:$('accountPassword').value})});e.target.reset();notify('共享查看账号已创建');loadWorkspace()}catch(e){notify(e.message)}finally{$('createAccount').disabled=false}};
$('checkSystem').onclick=loadWorkspace;
$('refreshFeedback').onclick=loadFeedback;
$('feedbackDevice').onchange=loadFeedback;
$('retentionDays').oninput=()=>{markRangeChips();clearTimeout(framesTimer);framesTimer=setTimeout(()=>loadFrames(),400)};
document.querySelectorAll('.range-chips button').forEach(b=>b.onclick=()=>{const input=$('retentionDays');if(input)input.value=b.dataset.days;clearTimeout(framesTimer);loadFrames(Number(b.dataset.days))});
markRangeChips();
$('framesForm').onsubmit=async e=>{
 e.preventDefault();
 if(!workspaceUser||workspaceUser.role!=='admin')return;
 const days=framesDays();if(!days){$('framesFeedback').textContent='保存天数请填 1–90 之间的整数。';return}
 const onlyAlerts=$('onlyAlerts').checked;
 let expired={expired_files:0,expired_mb:0};
 try{expired=await api('/workspace/frames?days='+days)}catch{}
 if(expired.expired_files&&!confirm('保存后，早于最近 '+days+' 天的 '+expired.expired_files+' 张普通图片（'+expired.expired_mb+' MB）会在后台被自动清理。\n提醒截图与纠正图长期保留，不受影响。\n\n确定保存这个范围吗？'))return;
 const b=$('saveFramesSettings');b.disabled=true;$('framesFeedback').textContent='';
 try{
 await api('/workspace/settings',{method:'PUT',body:JSON.stringify({frame_retention_days:days,save_all_frames:!onlyAlerts})});
 $('framesFeedback').textContent='已保存：保存最近 '+days+' 天'+(onlyAlerts?'，之后只新增重点关注照片':'，之后保存全部拍到的画面')+'。'
   +(expired.expired_files?'范围以外的 '+expired.expired_files+' 张（'+expired.expired_mb+' MB）正在后台清理…':'当前没有超出范围的图片。');
 /* 界面不提供手动清理按钮：这里直接触发后台清理，并在完成后把右侧数字刷新掉 */
 if(expired.expired_files)void runCleanupQuietly();else loadFrames(days);
 }catch(e){$('framesFeedback').textContent=e.message}finally{b.disabled=false}
};
/* 保存设置后由后台自动清理超出范围的图片：界面不提供手动按钮，只报告结果 */
async function waitCleanup(){for(let i=0;i<180;i++){const state=await api('/workspace/frames/cleanup');if(state.state!=='running')return state;await new Promise(resolve=>setTimeout(resolve,1000))}throw Error('清理时间较长，请稍后刷新查看结果')}
async function runCleanupQuietly(){
 const line=$('framesFeedback');
 try{
  await api('/workspace/frames/cleanup',{method:'POST'});
  const state=await waitCleanup();
  if(state.error)throw Error(state.error);
  if(line)line.textContent+=' 后台清理完成：删除 '+state.deleted_files+' 张过期图片'+(state.deleted_rows?'，更新 '+state.deleted_rows+' 条记录':'')+'。';
  loadFrames();
 }catch(e){
  if(line)line.textContent+=' 后台清理未完成：'+e.message;
 }
}
async function waitWireless(){for(let i=0;i<60;i++){const state=await api('/workspace/wireless-setup');if(state.state!=='running')return state;await new Promise(resolve=>setTimeout(resolve,1000))}throw Error('接入时间超过 60 秒，请重试')}
/* 设备卡片里的「Wi-Fi 接入」按钮调用这里：把这一台设备接到 Wi-Fi */
async function startWirelessSetup(deviceId,deviceName){
 const line=$('wifiSetupFeedback'),who=deviceName||deviceId;
 if(line)line.textContent='正在接入“'+who+'”：读设备 MAC、登记、把配置写进设备，请保持 USB 连接（大约 10 秒）…';
 try{
  await api('/workspace/wireless-setup',{method:'POST',body:JSON.stringify({expected_device_id:deviceId})});
  const state=await waitWireless();
  if(state.error)throw Error(state.error);
  const info=state.result||{};
  if(line)line.textContent='已接入：'+(info.device_id||who)+'（MAC '+(info.mac||'—')+' → '+(info.url||'—')+'）';
  notify('无线设备已接入');
  await refresh();renderDevices();loadFeedback();
 }catch(e){
  if(line)line.textContent=/^接入|^服务端出错|^插在 USB/.test(e.message)?e.message:'接入没有完成：'+e.message;
 }
}
$('networkForm').onsubmit=async e=>{e.preventDefault();$('pairNetwork').disabled=true;$('networkError').textContent='';try{const r=await api('/workspace/network-devices',{method:'POST',body:JSON.stringify({hardware_id:$('networkMac').value,name:$('networkName').value,existing_device_id:$('networkExisting').value||null})});const system=await api('/workspace/system');const base=system.addresses[0]?.url||location.origin;
 $('networkConfig').value=JSON.stringify({server_url:base,device_id:r.device_id,hardware_id:r.hardware_id,device_key:r.device_key,frame_url:base+r.upload_path,vision_url:base+r.vision_path,heartbeat_url:base+r.heartbeat_path},null,2);$('networkResult').hidden=false;
 $('networkResultNote').textContent='密钥仅在本次显示，请保存到设备配置中。同一 MAC 重新登记会更换密钥，旧密钥立即失效。';await refresh();loadNetworks();
 }catch(e){$('networkError').textContent=e.message}finally{$('pairNetwork').disabled=false}};
$('hideNetworkKey').onclick=()=>{$('networkConfig').value='';$('networkResult').hidden=true};
$('copyNetwork').onclick=async()=>{try{await navigator.clipboard.writeText($('networkConfig').value);notify('设备配置已复制')}catch(e){$('networkConfig').select();notify('请选择配置文本后手动复制')}};
$('checkNetworks').onclick=loadNetworks;

$('exportForm').onsubmit=async e=>{e.preventDefault();if(!selected){notify('请先选择设备');return}if($('exportFrom').value>$('exportTo').value){notify('开始日期不能晚于结束日期');return}const exportDevice=selected;$('exportRecords').disabled=true;try{const params=new URLSearchParams({device_id:exportDevice,from_date:$('exportFrom').value,to_date:$('exportTo').value});const response=await fetch('/api/workspace/export?'+params,{headers:{Authorization:'Bearer '+token},signal:AbortSignal.timeout(30000)});if(!response.ok){const body=await response.json().catch(()=>({}));throw Error(body.detail||'导出未完成')}const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=url;link.download='健康记录-'+$('exportFrom').value+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('健康记录已导出')}catch(e){notify(e.message)}finally{$('exportRecords').disabled=false}};

$('wifiSetup').onclick=()=>startWirelessSetup(selected,$('device').selectedOptions[0]?.textContent||selected);
const calendar=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai'}).format(new Date());$('exportFrom').value=calendar;$('exportTo').value=calendar;
initializeWorkspace();

/* 设置模块 · 折叠：每张设置卡平时只露一行标题，点标题才展开表单与清单。
   标题行里的按钮（重新检查 / 添加检测 / 刷新连接状态）和问号说明照旧可点，不会顺带折叠。 */
(function(){
 const page=$('settings');if(!page)return;
 for(const article of page.querySelectorAll('article')){
  if(article.dataset.settingsSection)continue;
  const head=article.querySelector(':scope > .row')||article.querySelector(':scope > h2');
  if(!head)continue;
  article.dataset.settingsSection='1';
  const body=document.createElement('div');body.className='settings-body';
  for(let node=head.nextSibling;node;){
   const next=node.nextSibling;
   /* 卡片右上角的问号留在外面，收起时也还能点 */
   if(!(node.nodeType===1&&node.classList.contains('help-corner')))body.append(node);
   node=next;
  }
  article.append(body);
  head.classList.add('settings-head');
  article.classList.add('settings-section','collapsed');
  head.tabIndex=0;head.setAttribute('aria-expanded','false');
  if(head.tagName!=='H2')head.setAttribute('role','button');
  const toggle=()=>{const collapsed=article.classList.toggle('collapsed');head.setAttribute('aria-expanded',String(!collapsed))};
  head.addEventListener('click',event=>{if(event.target.closest('button,a,input,select,textarea,.help'))return;toggle()});
 head.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();toggle()}});
 }
})();

/* 运行与网络卡 · 诊断信息：把运行状态与访问地址收进默认折叠的一块，普通用户不必看到这些字。
   「重新检查」按钮仍在卡片标题行里，点它照旧刷新这些内容。 */
(function(){
 const state=$('systemState'),list=$('lanAddresses');if(!state||!list)return;
 const host=state.parentElement;if(!host)return;
 const box=document.createElement('details');box.className='settings-diagnostics';
 const summary=document.createElement('summary');summary.textContent='诊断信息（运行状态与访问地址）';
 box.append(summary);
 for(const node of [state,$('lanState'),list])if(node)box.append(node);
 host.insertBefore(box,host.firstChild);
})();
