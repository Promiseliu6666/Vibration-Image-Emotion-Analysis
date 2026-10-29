(()=>{
 if(new URLSearchParams(location.search).get('embedded')!=='health')return;
 document.body.classList.add('health-embedded');
 const params=new URLSearchParams(location.search),view=params.get('view')||'live';
 const sheet=document.createElement('link');sheet.rel='stylesheet';sheet.href='/static/health-embedded.css?v=20261028';document.head.append(sheet);
 const task=document.getElementById('studyTaskForm');if(task){const section=task.closest('article,section,details');if(section)section.hidden=true}
 const names={live:'实时健康监测',history:'健康记录',analytics:'数据分析',settings:'设备管理'};
 if(typeof goPage==='function')goPage(view,{replace:true});
 const title=document.getElementById('title');if(title)title.textContent=names[view]||names.live;
 document.querySelectorAll('h2').forEach(el=>{if(el.textContent.includes('学习空间'))el.textContent='摄像头实时画面'});
 document.querySelectorAll('[id*=assistant],[class*=assistant-orb]').forEach(el=>el.style.setProperty('display','none','important'));
 document.addEventListener('workspace:page',()=>{document.querySelectorAll('h2').forEach(el=>{if(el.textContent.includes('学习空间'))el.textContent='摄像头实时画面'});});
 document.title=(names[view]||names.live)+' · 健康监测平台';
})();
