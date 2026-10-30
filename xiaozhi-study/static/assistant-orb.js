/* One assistant shared by every authenticated workspace, with isolated device conversations. */
(()=>{
 'use strict';
 if(!localStorage.getItem('token'))return;
 const face='<svg class="assistant-face" viewBox="0 0 36 36" aria-hidden="true"><rect x="5" y="8" width="26" height="21" rx="9"/><path d="M18 8V5m-3-1h6M11 16v3m14-3v3m-12 4q5 4 10 0"/></svg>';
 const host=document.createElement('div');host.className='xiaozhi-assistant';
 host.innerHTML=`<section class="assistant-panel" id="xiaozhiAssistantPanel" role="dialog" aria-modal="false" aria-labelledby="xiaozhiAssistantTitle" hidden>
  <div class="assistant-panel-header">${face}<div class="assistant-heading"><h2 id="xiaozhiAssistantTitle">小智助手</h2><p id="xiaozhiAssistantContext">结合近期记录，聊聊下一步</p></div><button class="assistant-close" type="button" aria-label="收起小智助手">×</button></div>
  <div class="assistant-messages" role="log" aria-label="与小智的对话" aria-live="polite" aria-relevant="additions"></div>
  <form class="assistant-compose"><p class="assistant-status" role="status" hidden></p><p class="assistant-error" role="alert" hidden></p><label for="xiaozhiAssistantQuestion">向小智提问</label><textarea id="xiaozhiAssistantQuestion" maxlength="2000" placeholder="问问小智，怎样安排下一段学习？" rows="2" required></textarea><div class="assistant-compose-actions"><button class="assistant-clear" type="button">新对话</button><button class="assistant-send" type="submit">发送</button></div><p class="assistant-input-hint">Enter 发送 · Shift + Enter 换行</p></form>
 </section><button type="button" class="assistant-launcher" aria-label="唤醒小智助手" aria-controls="xiaozhiAssistantPanel" aria-expanded="false"><span class="assistant-launcher-label">问问小智</span><span class="assistant-sphere">${face}</span></button>`;
 const topbar=document.querySelector('body.study-atelier > aside');
 if(topbar){host.classList.add('assistant-in-topbar');topbar.classList.add('has-top-assistant');topbar.insertBefore(host,topbar.querySelector('.account-menu'));}else document.body.append(host);
 const find=s=>host.querySelector(s),panel=find('.assistant-panel'),launcher=find('.assistant-launcher'),messages=find('.assistant-messages'),form=find('form'),input=find('textarea'),send=find('.assistant-send'),clear=find('.assistant-clear'),error=find('.assistant-error'),status=find('.assistant-status');
 const conversations=new Map();let context={deviceId:'',deviceName:'',configured:null},active=null,sequence=0,checking=null;
 const turns=()=>{if(!conversations.has(context.deviceId))conversations.set(context.deviceId,[]);return conversations.get(context.deviceId)};
 function setError(message){error.textContent=message;error.hidden=!message}
 function sync(){
  find('#xiaozhiAssistantContext').textContent=context.deviceId?(context.deviceName||context.deviceId)+' · 近期行为摘要':'结合近期记录，聊聊下一步';
  const note=context.configured===false?'AI 服务尚未配置，请联系管理员。':!context.deviceId?'请先选择一台设备，再向小智提问。':'';
  status.textContent=note;status.hidden=!note;send.disabled=!active&&(!context.deviceId||context.configured!==true||!input.value.trim());send.textContent=active?'停止':'发送';send.type=active?'button':'submit';clear.disabled=!!active||!turns().length;
 }
 function appendMessage(turn){const item=document.createElement('div');item.className='assistant-message '+turn.role;const label=document.createElement('span');label.className='assistant-message-label';label.textContent=turn.role==='user'?'你':'小智';const text=document.createElement('p');
  // Only bold/code emphasis is parsed; provider output never becomes HTML.
  if(turn.role==='assistant'){for(const part of turn.content.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)){if(part.startsWith('**')&&part.endsWith('**')){const strong=document.createElement('strong');strong.textContent=part.slice(2,-2);text.append(strong)}else if(part.startsWith('`')&&part.endsWith('`'))text.append(document.createTextNode(part.slice(1,-1)));else text.append(document.createTextNode(part))}}else text.textContent=turn.content;
  item.append(label,text);messages.append(item)}
 function render(){
  messages.replaceChildren();const list=turns();
  if(!list.length){const welcome=document.createElement('div');welcome.className='assistant-welcome';welcome.innerHTML='<h3>让下一段，轻松一点。</h3><p>聊聊注意力、休息与日常习惯。小智会结合所选设备近期的行为摘要，给你一些可执行的建议。</p><div class="assistant-prompts"></div>';messages.append(welcome);
   for(const [title,question] of [['找到容易分心的时刻','最近有哪些容易分心的时刻？'],['安排一次用眼休息','根据近期的学习状态，我应该怎样安排用眼休息？'],['规划下一段学习','我可以怎样调整下一段学习，让注意力更集中？']]){const b=document.createElement('button');b.type='button';b.textContent=title;b.onclick=()=>{input.value=question;sync();input.focus()};welcome.querySelector('.assistant-prompts').append(b)}
  }else list.forEach(appendMessage);
  if(active){const p=document.createElement('p');p.className='assistant-pending';p.textContent='小智正在结合记录思考…';messages.append(p)}
  messages.scrollTop=messages.scrollHeight;sync();
 }
 function update(next){const changed=next.deviceId!==context.deviceId;context={...context,...next};if(changed){stop();input.value='';setError('');render()}else sync()}
 function stop(){if(!active)return;const run=active;active=null;sequence++;run.controller.abort();clearTimeout(run.timeout);const list=conversations.get(run.deviceId);if(list?.at(-1)===run.turn)list.pop();if(context.deviceId===run.deviceId)input.value=run.turn.content;render()}
 async function checkContext(){
  if(checking)return checking;
  checking=(async()=>{try{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);let response;try{response=await fetch('/api/console/status',{headers:{Authorization:'Bearer '+localStorage.getItem('token')},signal:controller.signal})}finally{clearTimeout(timer)}
   if(response.status===401){location.replace('/static/login.html');return}if(!response.ok)throw Error('暂时无法连接助手，请稍后再试。');const result=await response.json();
   const isReview=location.pathname.endsWith('/session.html'),deviceId=isReview?window.xiaozhiReviewDevice:(context.deviceId||localStorage.getItem('selectedDevice'));
   const device=result.devices?.find(d=>d.device_id===deviceId)||(!isReview?result.devices?.[0]:null);
   update({deviceId:device?.device_id||'',deviceName:device?.name||'',configured:!!result.assistant_configured});
  }catch(e){setError(e.name==='AbortError'?'连接超时，请重新打开助手。':e.message)}finally{checking=null}})();return checking;
 }
 function open(){panel.hidden=false;launcher.setAttribute('aria-expanded','true');launcher.setAttribute('aria-label','收起小智助手');find('.assistant-launcher-label').hidden=true;render();input.focus();if(context.configured===null||!context.deviceId)void checkContext()}
 function close(){panel.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-label','唤醒小智助手');find('.assistant-launcher-label').hidden=false;launcher.focus()}
 launcher.onclick=()=>panel.hidden?open():close();find('.assistant-close').onclick=close;send.onclick=()=>{if(active)stop()};
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden&&!document.querySelector('dialog[open]')){close();e.preventDefault()}});
 input.addEventListener('input',sync);input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!active&&!send.disabled)form.requestSubmit()}});
 clear.onclick=()=>{if(active)return;conversations.set(context.deviceId,[]);input.value='';setError('');render();input.focus()};
 form.onsubmit=async e=>{
  e.preventDefault();if(active){stop();return}const message=input.value.trim();if(!message||!context.deviceId||context.configured!==true)return;
  const deviceId=context.deviceId,history=turns().slice(-12).map(t=>({role:t.role,content:t.content.slice(0,6000)})),turn={role:'user',content:message},controller=new AbortController(),seq=++sequence;
  const run={deviceId,turn,controller,timeout:setTimeout(()=>controller.abort(),90000)};active=run;turns().push(turn);input.value='';setError('');render();
  try{const response=await fetch('/api/agent/chat',{method:'POST',headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json'},body:JSON.stringify({message,device_id:deviceId,history}),signal:controller.signal});
   if(response.status===401){location.replace('/static/login.html');return}if(!response.ok)throw Error(response.status===429?'提问过于频繁，请稍后再试。':'暂时无法获取回复，请稍后重试。');const result=await response.json();if(typeof result.reply!=='string'||!result.reply.trim())throw Error('没有收到回复，请再试一次。');
   if(seq!==sequence||context.deviceId!==deviceId)return;if(result.reply.startsWith('抱歉，我暂时无法回复'))throw Error(result.reply);conversations.get(deviceId).push({role:'assistant',content:result.reply});
   // Keep a bounded, session-only conversation. Reloading or logging out clears it.
   if(conversations.get(deviceId).length>40)conversations.set(deviceId,conversations.get(deviceId).slice(-40));
  }catch(err){if(seq===sequence){const list=conversations.get(deviceId);if(list.at(-1)===turn)list.pop();input.value=message;setError(err.name==='AbortError'?'等待回复超时，请重新发送。':err.message)}}
  finally{clearTimeout(run.timeout);if(seq===sequence){active=null;render()}}
 };
 window.XiaozhiAssistant={open,update};
 document.addEventListener('assistant:context',e=>update(e.detail));
 document.addEventListener('assistant:review',()=>{if(!panel.hidden)void checkContext()});
 window.addEventListener('pagehide',()=>{active?.controller.abort();conversations.clear()});
 render();if(window.openAssistantOnReady||location.hash==='#assistant')open();
})();
