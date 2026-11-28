<template>
  <article ref="container" class="camera-preview" :class="{ 'is-selected': selected }" :style="{ '--camera-aspect-ratio': aspectRatio }" :aria-label="camera.name + '画面'">
    <div class="preview-frame" :style="frameStyle">
    <img v-if="streamUrl && state !== 'error'" :key="streamUrl" ref="image" :src="streamUrl"
      :alt="camera.name + '实时画面'" draggable="false" @load="connected" @error="failed" />
    <div v-if="state === 'live' || compact" class="preview-caption">
      <span class="preview-signal" :class="{ 'is-live': state === 'live' }"></span>
      <strong v-if="compact">{{ camera.name }}</strong><span v-if="state === 'live'" class="preview-state">{{ stateLabel }}</span>
      <small v-if="state === 'live' && nativeSize">{{ nativeSize.width }} × {{ nativeSize.height }}</small>
    </div>
    <div v-if="state !== 'live'" class="preview-placeholder" aria-live="polite">
      <el-icon :size="38"><VideoCamera /></el-icon>
      <strong>{{ placeholderTitle }}</strong>
      <p>{{ placeholderDetail }}</p>
      <button v-if="state === 'error' || state === 'waiting'" type="button" class="preview-retry" @click="retry">重新连接</button>
    </div>
    <div v-if="fallback && state === 'live'" class="preview-fallback" role="status">分析画面暂不可用，已显示原始画面。<button type="button" @click="retry">重新尝试</button></div>
    <button v-if="compact" type="button" class="preview-focus" @click="emit('focus', camera)">查看大画面 <el-icon><FullScreen /></el-icon></button>
    </div>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FullScreen, VideoCamera } from '@element-plus/icons-vue'
import { cameraPreviewUrl } from './preview'

const props = defineProps({ camera: { type: Object, required: true }, enabled: Boolean, compact: Boolean, selected: Boolean, revision: { type: Number, default: 0 }, feed: { type: String, default: 'raw' } })
const emit = defineEmits(['focus', 'state-change'])
const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'
const container = ref(null)
const containerSize = ref(null)
const nativeSize = ref(null)
const aspectRatio = computed(() => nativeSize.value ? nativeSize.value.width / nativeSize.value.height : 4 / 3)
const frameStyle = computed(() => {
  const available = containerSize.value
  if (!available) return { width: '100%', aspectRatio: aspectRatio.value }
  const width = Math.min(available.width, available.height * aspectRatio.value)
  return { width: width + 'px', height: width / aspectRatio.value + 'px' }
})
const image = ref(null)
const attempt = ref(0)
const fallback = ref(false)
const state = ref('connecting')
let connectionTimer
let sizeObserver
const effectiveFeed = computed(() => fallback.value || !['raw', 'analysis', 'fatigue'].includes(props.feed) ? 'raw' : props.feed)
const streamUrl = computed(() => props.enabled ? cameraPreviewUrl(props.camera, baseURL, `${props.revision}-${attempt.value}`, effectiveFeed.value) : '')
const stateLabel = computed(() => ({ live: '画面已连接', connecting: '正在连接', waiting: '等待画面', error: '连接中断', unavailable: '待配置', paused: '已暂停预览' })[state.value])
const placeholderTitle = computed(() => ({ connecting: '正在连接摄像头', waiting: '暂未收到画面', error: '暂时没有画面', unavailable: '请先配置摄像头', paused: '画面预览已暂停' })[state.value])
const placeholderDetail = computed(() => {
  if (state.value === 'unavailable') return '在设备配置中完成连接设置后，再打开此画面。'
  if (state.value === 'paused') return '返回此页面后继续接收画面。'
  if (state.value === 'connecting') return '画面连接后会自动显示。'
  return '检查设备连接和采集状态，或重新连接此画面。'
})
function setState(value) {
  state.value = value
  emit('state-change', { cameraId: props.camera.camera_id, state: value, feed: effectiveFeed.value,
    width: value === 'live' ? image.value?.naturalWidth : undefined,
    height: value === 'live' ? image.value?.naturalHeight : undefined })
}
watch(() => [props.camera.camera_id, props.feed, props.revision], () => { fallback.value = false })
watch(streamUrl, value => {
  clearTimeout(connectionTimer)
  if (!props.enabled) { setState('paused'); return }
  if (!value) { setState('unavailable'); return }
  setState('connecting')
  connectionTimer = setTimeout(() => setState('waiting'), 12000)
}, { immediate: true })
function connected(event) {
  if (event.currentTarget !== image.value) return
  const { naturalWidth: width, naturalHeight: height } = image.value
  if (width > 0 && height > 0) nativeSize.value = { width, height }
  clearTimeout(connectionTimer)
  setState('live')
}
function failed(event) {
  if (event.currentTarget !== image.value) return
  clearTimeout(connectionTimer)
  if (effectiveFeed.value !== 'raw') { fallback.value = true; return }
  setState('error')
}
function retry() { fallback.value = false; attempt.value += 1 }
watch(() => props.camera.camera_id, () => { nativeSize.value = null })
onMounted(() => {
  const measure = size => {
    if (size?.width > 0 && size?.height > 0) containerSize.value = { width: size.width, height: size.height }
  }
  measure(container.value?.getBoundingClientRect?.())
  if (typeof ResizeObserver !== 'undefined') {
    sizeObserver = new ResizeObserver(entries => {
      const entry = entries.find(entry => entry.target === container.value)
      measure(entry?.contentRect)
    })
    sizeObserver.observe(container.value)
  }
})
onBeforeUnmount(() => { sizeObserver?.disconnect(); clearTimeout(connectionTimer); emit('state-change', { cameraId: props.camera.camera_id, state: 'paused' }) })
</script>

<style scoped>
.camera-preview { display:flex;align-items:center;justify-content:center;width:100%;height:100%;min-width:0;min-height:0; }
.preview-frame { position:relative;flex:none;max-width:100%;max-height:100%;overflow:hidden;background:#152536;isolation:isolate;color:#f3f6fa; }
.camera-preview.is-selected .preview-frame { outline:2px solid #7badeb;outline-offset:-2px; }
.preview-frame > img { display:block;width:100%;height:100%;object-fit:contain;object-position:center; }
.preview-caption { position:absolute;top:0;left:0;right:0;z-index:2;display:flex;align-items:center;gap:9px;padding:15px 18px;background:linear-gradient(#102030c9,transparent);font-size:12px;pointer-events:none; }
.preview-caption strong { font-size:14px;font-weight:600;overflow:hidden;white-space:nowrap;text-overflow:ellipsis; }
.preview-state { white-space:nowrap;color:#d1dce8; }.preview-caption small { margin-left:auto;font-size:11px;color:#d1dce8;white-space:nowrap; }
.preview-signal { width:7px;height:7px;flex-shrink:0;background:#92a1b0;border-radius:50%; }
.preview-signal.is-live { background:#6cdbb2;box-shadow:0 0 0 3px #6cdbb220; }
.preview-placeholder { position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;padding:60px 24px;text-align:center;background:#152536; }
.preview-placeholder > .el-icon { color:#7d91a6; }.preview-placeholder strong { font-size:17px;font-weight:500; }
.preview-placeholder p { color:#b1c0d0;line-height:1.7;font-size:13px;margin:0;max-width:340px; }
.preview-retry { border:1px solid #71869c;border-radius:5px;color:#f3f6fa;background:#263b50;padding:8px 16px;cursor:pointer; }
.preview-focus { position:absolute;right:12px;bottom:12px;display:flex;align-items:center;gap:6px;padding:5px 8px;border:1px solid #ffffff55;border-radius:4px;color:white;background:#15253699;cursor:pointer;font:inherit;font-size:12px; }
.preview-fallback { position:absolute;left:12px;right:12px;bottom:52px;padding:8px 10px;border:1px solid #ffffff30;border-radius:5px;color:#e4edf7;background:#152536d9;font-size:12px;line-height:1.6; }
.preview-fallback button { color:#b6d7ff;background:none;border:0;text-decoration:underline;cursor:pointer;font:inherit; }
button:focus-visible { outline:2px solid #9bc7ff;outline-offset:3px; }
@media(max-width:600px) { .preview-caption { padding:12px; }.preview-placeholder { gap:8px;padding:46px 16px; }.preview-placeholder strong { font-size:15px; }.preview-placeholder p { font-size:12px; } }
@media(max-width:1150px) { .camera-preview { height:auto;aspect-ratio:var(--camera-aspect-ratio,4/3); } }
</style>
