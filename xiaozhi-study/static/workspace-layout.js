// Keep quick record filters attached to the existing, single source of range state.
document.querySelectorAll('[data-range]').forEach(button=>button.onclick=()=>{historyDayFilter='';$('historyDate').value='';
 $('historyRange').value=button.dataset.range;
 document.querySelectorAll('[data-range]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));
 void loadHistory();
});

$("exitFullscreen").onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen()}catch{notify("请按 Esc 退出全屏")}};

// One source of truth for the prominent video/evidence switch.
document.addEventListener('DOMContentLoaded',()=>{
 const select=$('previewMode'),buttons=[...document.querySelectorAll('[data-preview]')];
 const sync=()=>{buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.preview===select.value)));$('previewModeNote');};
 buttons.forEach(b=>b.onclick=()=>{select.value=b.dataset.preview;select.dispatchEvent(new Event('change'));if(!showPreview)$('previewBtn').click();sync();});
 select.addEventListener('change',sync);sync();
});
