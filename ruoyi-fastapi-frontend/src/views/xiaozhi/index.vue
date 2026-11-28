<template>
 <section class="xiaozhi-workspace" :class="{ 'xiaozhi-workspace--detection': detectDevices }" :aria-busy="loading">
  <div v-if="!detectDevices" class="xiaozhi-camera-bar">
   <div class="xiaozhi-camera-bar__copy">
    <span>CAMERA ROUTE</span>
    <small>切换摄像头后自动重连监测画面</small>
   </div>
   <CameraSwitcher compact />
  </div>
  <div v-if="error" class="xiaozhi-error">
   <el-alert :title="error" type="warning" :closable="false" show-icon />
   <div class="xiaozhi-error-actions">
    <el-button type="primary" @click="connect">重新连接小智</el-button>
    <el-button v-if="loginRequired" @click="goLogin">重新登录主系统</el-button>
   </div>
  </div>
  <div v-else-if="loading" class="xiaozhi-loading" role="status">正在连接小智监测服务…</div>
  <iframe v-if="frameUrl && !error" ref="frame" :src="frameUrl" title="小智健康监测" class="xiaozhi-frame" allow="fullscreen" @error="frameFailed" />
 </section>
</template>
<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { getToken, removeToken } from '@/utils/auth'
import useUserStore from '@/store/modules/user'
import CameraSwitcher from '@/components/CameraSwitcher/index.vue'
import useCameraStore from '@/store/modules/camera'
import { CAMERA_STORAGE_KEY, toCameraId, toXiaozhiDeviceId } from '@/utils/camera'

const props = defineProps({ detectDevices: Boolean })
const emit = defineEmits(['detected', 'close'])
const route = useRoute(), router = useRouter()
const cameraStore = useCameraStore()
const frame = ref(null), frameUrl = ref(''), loading = ref(true), error = ref(''), loginRequired = ref(false)
// This client intentionally has no shared notification interceptor. The page
// displays one actionable connection error instead of a second generic toast.
// The backend allows 12 seconds for Xiaozhi, in addition to validating the main
// login session. Leave time for its actionable error response to reach the UI.
const client = axios.create({ baseURL: import.meta.env.VITE_APP_BASE_API, timeout: 20000 })
const origin = 'http://127.0.0.1:8000'
let token = null, attempt = 0, timeout = null, controller = null, disposed = false

function connectionError(cause) {
 const payload = cause?.response?.data || cause?.payload || {}
 const status = Number(payload.code || cause?.response?.status || cause?.status || 0)
 const detail = typeof payload.detail === 'string' ? payload.detail : typeof payload.msg === 'string' ? payload.msg : ''
 const translated = detail && /[\u3400-\u9fff]/.test(detail) ? detail : ''
 if (status === 401) return { message: translated || '主系统登录已失效，请重新登录后连接小智。', requiresLogin: true }
 if (status === 403) return { message: translated || '当前账号没有小智访问权限，请检查同名账号是否启用及其权限。', requiresLogin: false }
 if (translated) return { message: translated, requiresLogin: false }
 if (cause?.code === 'ECONNABORTED' || cause?.code === 'ETIMEDOUT') return { message: '连接小智超时，请检查小智后台服务后重试。', requiresLogin: false }
 if (status === 503 || status === 502) return { message: '小智服务尚未连接，请启动小智后台服务后重试。', requiresLogin: false }
 if (status === 404) return { message: '小智接入接口尚未就绪，请重启主系统后台后重试。', requiresLogin: false }
 if (status >= 500) return { message: '小智连接服务发生异常，请检查后台服务状态后重试。', requiresLogin: false }
 return { message: '无法连接小智服务，请检查主系统与小智后台是否已启动。', requiresLogin: false }
}
function clearHandshake() { clearTimeout(timeout); timeout = null; token = null }
function fail(message, requiresLogin = false) {
 clearHandshake(); frameUrl.value = ''; loading.value = false; error.value = message; loginRequired.value = requiresLogin
}
async function connect() {
 if (disposed) return
 const id = ++attempt
 controller?.abort(); controller = new AbortController()
 clearHandshake(); frameUrl.value = ''; loading.value = true; error.value = ''; loginRequired.value = false
 const bearer = getToken()
 if (!bearer) { controller = null; fail('请先登录健康监测平台，再连接小智。', true); return }
 try {
  const response = await client.get('/integration/xiaozhi/launch', { signal: controller.signal, headers: { Authorization: `Bearer ${bearer}` } })
  if (disposed || id !== attempt) return
  const payload = response.data || {}
  if (payload.code && payload.code !== 200) throw { payload }
  const data = payload.data || payload
  // A token is only posted to the known local bridge, never a returned URL.
  if (typeof data.token !== 'string' || !data.token || data.token.length > 8192 || (data.origin && new URL(data.origin).origin !== origin)) {
   fail('小智接入返回的信息不完整，请重新连接或检查后台配置。'); return
  }
  token = data.token
  const view = ['live','history','analytics','settings'].includes(route.meta.xiaozhiView) ? route.meta.xiaozhiView : 'live'
  frameUrl.value = `${origin}/static/portal-bridge.html?portal=${encodeURIComponent(location.origin)}&embedded=health&view=${encodeURIComponent(view)}${props.detectDevices ? '&action=detect-device' : ''}`
  timeout = setTimeout(() => {
   if (!disposed && id === attempt && loading.value) fail('小智页面连接超时，请确认小智后台服务正在运行，再重新连接。')
  }, 20000)
 } catch (cause) {
  if (disposed || id !== attempt || cause?.code === 'ERR_CANCELED') return
  const message = connectionError(cause); fail(message.message, message.requiresLogin)
 } finally {
  if (id === attempt) controller = null
 }
}
function frameFailed(event) { if (event?.target !== frame.value) return; if (!disposed && loading.value) fail('小智页面未能加载，请检查小智后台服务后重新连接。') }
function receive(event) {
 if (disposed || event.origin !== origin || event.source !== frame.value?.contentWindow) return
 if (props.detectDevices && event.data?.type === 'xiaozhi-device-detected') {
  const deviceId = event.data.deviceId
  if (typeof deviceId === 'string' && toCameraId('xiaozhi', deviceId) === `xiaozhi:${deviceId}` && !deviceId.startsWith('vibration-')) emit('detected', deviceId)
  return
 }
 if (props.detectDevices && event.data?.type === 'xiaozhi-detection-closed') { emit('close'); return }
 if (event.data?.type === 'employee-bridge-expired' && frameUrl.value) {
  fail('小智会话已失效，请重新连接小智。')
  return
 }
 if (!loading.value || !token) return
 if (event.data?.type === 'employee-bridge-ready') {
  frame.value.contentWindow.postMessage({
   type: 'employee-bridge-auth', token, deviceId: toXiaozhiDeviceId(cameraStore.cameraId)
  }, origin)
 }
 if (event.data?.type === 'employee-bridge-complete') { loading.value = false; clearHandshake() }
}
function goLogin() {
 // The user explicitly chooses to replace an expired local login. Do not
 // redirect automatically or silently remove a valid session on a 403.
 removeToken(); useUserStore().$reset()
 router.push({ path: '/login', query: { redirect: route.fullPath } })
}
let cameraWatchReady = false
onMounted(async () => {
 window.addEventListener('message', receive)
 if (props.detectDevices) { connect(); return }
 try { await cameraStore.loadXiaozhiDevices(false, true) } catch {}
 if (disposed) return
 const routeCamera = new URLSearchParams(location.search).get('camera')
 if (!routeCamera && !localStorage.getItem(CAMERA_STORAGE_KEY)) {
  const online = cameraStore.xiaozhiDevices.find(device => device.online)
  if (online) cameraStore.selectCamera(toCameraId('xiaozhi', online.device_id))
 }
 cameraWatchReady = true
 connect()
})
watch([() => route.meta.xiaozhiView, () => cameraStore.cameraId], () => {
 if (cameraWatchReady) connect()
}, { flush: 'sync' })
onBeforeUnmount(() => {
 disposed = true; attempt++; controller?.abort(); controller = null; clearHandshake(); window.removeEventListener('message', receive)
})
</script>
<style scoped>
.xiaozhi-workspace{position:relative;background:#f4f7fb;min-height:calc(100vh - 94px)}
.xiaozhi-camera-bar{display:flex;min-height:58px;box-sizing:border-box;align-items:center;justify-content:space-between;gap:18px;padding:8px 18px;background:rgba(255,255,255,.72);border-bottom:1px solid rgba(209,221,232,.8);backdrop-filter:blur(10px)}
.xiaozhi-camera-bar__copy{display:flex;min-width:0;flex-direction:column;gap:2px}.xiaozhi-camera-bar__copy span{color:#7a8999;font-size:10px;font-weight:700;letter-spacing:.16em}.xiaozhi-camera-bar__copy small{color:#596b7e;font-size:12px}
.xiaozhi-frame{display:block;width:100%;height:calc(100vh - 152px);border:0;background:#f4f7fb}
.xiaozhi-workspace--detection{min-height:480px}.xiaozhi-workspace--detection .xiaozhi-frame{height:min(560px,65vh);min-height:400px}.xiaozhi-workspace--detection .xiaozhi-loading{inset:24px 16px auto}
.xiaozhi-loading{position:absolute;inset:94px 24px auto;color:#6d8095;font-size:14px;text-align:center;padding:30px}
.xiaozhi-error{padding:28px}.xiaozhi-error-actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:18px}.xiaozhi-error-actions .el-button+.el-button{margin-left:0}
@media(max-width:640px){.xiaozhi-camera-bar{align-items:stretch;flex-direction:column;padding:10px 14px}.xiaozhi-camera-bar__copy small{display:none}}
</style>
