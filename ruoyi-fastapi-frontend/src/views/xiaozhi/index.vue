<template>
 <section class="xiaozhi-workspace">
  <div v-if="error" class="xiaozhi-error"><el-alert :title="error" type="warning" :closable="false" show-icon/><el-button type="primary" @click="connect">重新连接小智</el-button></div>
  <div v-else-if="loading" class="xiaozhi-loading">正在连接小智监测服务…</div>
  <iframe v-if="frameUrl" ref="frame" :src="frameUrl" title="小智健康监测" class="xiaozhi-frame" allow="fullscreen"/>
 </section>
</template>
<script setup>
import {ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {useRoute} from 'vue-router'
import request from '@/utils/request'
const route=useRoute(),frame=ref(null),frameUrl=ref(''),loading=ref(true),error=ref('')
let token=null,attempt=0,timeout=null
const origin='http://127.0.0.1:8000'
async function connect(){
 const id=++attempt;loading.value=true;error.value='';frameUrl.value=''
 try{const data=await request({url:'/integration/xiaozhi/launch',method:'get'});if(id!==attempt)return;token=data.token;frameUrl.value=origin+'/static/portal-bridge.html?portal='+encodeURIComponent(location.origin)+'&embedded=health&view='+encodeURIComponent(route.meta.xiaozhiView||'live');clearTimeout(timeout);timeout=setTimeout(()=>{if(loading.value)error.value='小智页面未能加载，请确认后台服务正在运行'},20000)}catch(e){if(id===attempt){error.value=e.message||'小智服务连接失败';loading.value=false}}
}
function receive(e){if(e.origin!==origin||e.source!==frame.value?.contentWindow)return;if(e.data?.type==='employee-bridge-ready')frame.value.contentWindow.postMessage({type:'employee-bridge-auth',token},origin);if(e.data?.type==='employee-bridge-complete'){loading.value=false;token=null;clearTimeout(timeout)}}
onMounted(()=>{window.addEventListener('message',receive);connect()})
watch(()=>route.meta.xiaozhiView,connect)
onBeforeUnmount(()=>{attempt++;token=null;clearTimeout(timeout);window.removeEventListener('message',receive)})
</script>
<style scoped>
.xiaozhi-workspace{position:relative;background:#f4f7fb;min-height:calc(100vh - 94px)}.xiaozhi-frame{display:block;width:100%;height:calc(100vh - 94px);border:0;background:#f4f7fb}.xiaozhi-loading{position:absolute;inset:36px 24px auto;color:#6d8095;font-size:14px;text-align:center;padding:30px}.xiaozhi-error{padding:28px}.xiaozhi-error .el-button{margin-top:18px}
</style>
