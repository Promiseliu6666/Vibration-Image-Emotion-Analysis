<template>
 <section class="xiaozhi-workspace">
  <div class="xiaozhi-camera-bar">
   <div class="xiaozhi-camera-bar__copy">
    <span>CAMERA ROUTE</span>
    <small>切换摄像头后自动重连监测画面</small>
   </div>
   <CameraSwitcher compact />
  </div>
  <div v-if="error" class="xiaozhi-error"><el-alert :title="error" type="warning" :closable="false" show-icon/><el-button type="primary" @click="connect">重新连接小智</el-button></div>
  <div v-else-if="loading" class="xiaozhi-loading">正在连接小智监测服务…</div>
  <iframe v-if="frameUrl" ref="frame" :src="frameUrl" title="小智健康监测" class="xiaozhi-frame" allow="fullscreen"/>
 </section>
</template>
<script setup>
import {ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {useRoute} from 'vue-router'
import request from '@/utils/request'
import CameraSwitcher from '@/components/CameraSwitcher/index.vue'
import useCameraStore from '@/store/modules/camera'
import {CAMERA_STORAGE_KEY,toCameraId,toXiaozhiDeviceId} from '@/utils/camera'
const route=useRoute(),frame=ref(null),frameUrl=ref(''),loading=ref(true),error=ref('')
const cameraStore=useCameraStore()
let token=null,attempt=0,timeout=null
let cameraWatchReady=false
const origin='http://127.0.0.1:8000'
async function connect(){
 const id=++attempt;loading.value=true;error.value='';frameUrl.value=''
 try{const data=await request({url:'/integration/xiaozhi/launch',method:'get'});if(id!==attempt)return;token=data.token;frameUrl.value=origin+'/static/portal-bridge.html?portal='+encodeURIComponent(location.origin)+'&embedded=health&view='+encodeURIComponent(route.meta.xiaozhiView||'live')+'&cameraBridge=20261103';clearTimeout(timeout);timeout=setTimeout(()=>{if(loading.value)error.value='小智页面未能加载，请确认后台服务正在运行'},20000)}catch(e){if(id===attempt){error.value=e.message||'小智服务连接失败';loading.value=false}}
}
function receive(e){if(e.origin!==origin||e.source!==frame.value?.contentWindow)return;if(e.data?.type==='employee-bridge-ready')frame.value.contentWindow.postMessage({type:'employee-bridge-auth',token,deviceId:toXiaozhiDeviceId(cameraStore.cameraId)},origin);if(e.data?.type==='employee-bridge-complete'){loading.value=false;token=null;clearTimeout(timeout)}}
onMounted(async()=>{window.addEventListener('message',receive);try{await cameraStore.loadXiaozhiDevices()}catch{}
 const routeCamera=new URLSearchParams(location.search).get('camera'),hasExplicitSelection=Boolean(localStorage.getItem(CAMERA_STORAGE_KEY)||routeCamera)
 if(!hasExplicitSelection){const online=cameraStore.xiaozhiDevices.find(device=>device.online);if(online)cameraStore.selectCamera(toCameraId('xiaozhi',online.device_id))}
 cameraWatchReady=true;connect()})
watch(()=>[route.meta.xiaozhiView,cameraStore.cameraId].join('|'),()=>{if(cameraWatchReady)connect()})
onBeforeUnmount(()=>{attempt++;token=null;clearTimeout(timeout);window.removeEventListener('message',receive)})
</script>
<style scoped>
.xiaozhi-workspace{position:relative;background:#f4f7fb;min-height:calc(100vh - 94px)}
.xiaozhi-camera-bar{display:flex;min-height:58px;box-sizing:border-box;align-items:center;justify-content:space-between;gap:18px;padding:8px 18px;background:rgba(255,255,255,.72);border-bottom:1px solid rgba(209,221,232,.8);backdrop-filter:blur(10px)}
.xiaozhi-camera-bar__copy{display:flex;min-width:0;flex-direction:column;gap:2px}.xiaozhi-camera-bar__copy span{color:#7a8999;font-size:10px;font-weight:700;letter-spacing:.16em}.xiaozhi-camera-bar__copy small{color:#596b7e;font-size:12px}
.xiaozhi-frame{display:block;width:100%;height:calc(100vh - 152px);border:0;background:#f4f7fb}.xiaozhi-loading{position:absolute;inset:94px 24px auto;color:#6d8095;font-size:14px;text-align:center;padding:30px}.xiaozhi-error{padding:28px}.xiaozhi-error .el-button{margin-top:18px}
@media(max-width:640px){.xiaozhi-camera-bar{align-items:stretch;flex-direction:column;padding:10px 14px}.xiaozhi-camera-bar__copy small{display:none}.xiaozhi-frame{height:calc(100vh - 151px)}}
</style>
