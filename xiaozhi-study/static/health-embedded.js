(()=>{
 if(new URLSearchParams(location.search).get('embedded')!=='health')return;
 document.body.classList.add('health-embedded');
 const params=new URLSearchParams(location.search),view=params.get('view')||'live';
 const sheet=document.createElement('link');sheet.rel='stylesheet';sheet.href='/static/health-embedded.css?v=20261128';document.head.append(sheet);
 const task=document.getElementById('studyTaskForm');if(task){const section=task.closest('article,section,details');if(section)section.hidden=true}
 const names={live:'实时健康监测',history:'健康记录',analytics:'数据分析',settings:'设备管理'};
 if(typeof goPage==='function')goPage(view,{replace:true});
 const title=document.getElementById('title');if(title)title.textContent=names[view]||names.live;
 document.querySelectorAll('h2').forEach(el=>{if(el.textContent.includes('学习空间'))el.textContent='摄像头实时画面'});
 document.querySelectorAll('[id*=assistant],[class*=assistant-orb]').forEach(el=>el.style.setProperty('display','none','important'));
 document.addEventListener('workspace:page',()=>{document.querySelectorAll('h2').forEach(el=>{if(el.textContent.includes('学习空间'))el.textContent='摄像头实时画面'});});
 document.title=(names[view]||names.live)+' · 健康监测平台';
 if(params.get('action')==='detect-device'&&window.parent!==window){
  const portal=params.get('portal');
  if(!['http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:8800','http://localhost:8800'].includes(portal))return;
  document.body.classList.add('health-device-detection');
  showPreview=false;clearPreview();
  const wizard=document.getElementById('wizard');
  const post=(type,extra={})=>window.parent.postMessage({type,...extra},portal);
  wizard.showModal();
  document.getElementById('wizardMessage').textContent='正在读取设备检测权限…';
  document.getElementById('verify').disabled=true;document.getElementById('rescanUsb').hidden=true;
  const permissionTimeout=setTimeout(()=>{document.getElementById('wizardMessage').textContent='读取设备检测权限超时，请关闭窗口后重新检测。'},15000);
  // Wait for account permissions before offering the existing USB wizard.
  const start=()=>{
   clearTimeout(permissionTimeout);
   if(workspaceUser?.role==='admin'){document.getElementById('rescanUsb').hidden=false;void openWizard();}
   else{document.getElementById('wizardMessage').textContent='当前账号仅可查看，请使用管理员账号检测设备。';}
  };
  if(workspaceUser)start();else document.addEventListener('workspace:ready',start,{once:true});
  wizard.addEventListener('close',()=>post('xiaozhi-detection-closed'));
  document.addEventListener('workspace:device-detected',event=>post('xiaozhi-device-detected',{deviceId:event.detail.deviceId}));
 }
})();
