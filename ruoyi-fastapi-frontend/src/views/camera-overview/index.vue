<template>
  <div ref="overviewRoot" class="camera-overview" :style="{ '--overview-height': viewportHeight, '--workspace-gap': workspaceGap + 'px' }">
    <section class="monitor-toolbar" aria-label="监测画面与指标选择">
      <div class="toolbar-fields">
        <div class="toolbar-field camera-field">
          <span id="camera-field-label">摄像头</span>
          <el-select :model-value="cameraStore.selectedCamera || cameraStore.cameraId === 'xiaozhi' ? cameraStore.cameraId : undefined"
            filterable placeholder="选择摄像头" popper-class="monitor-camera-picker" :loading="loading && !cameraList.length"
            aria-label="选择摄像头" aria-labelledby="camera-field-label" @change="selectCamera">
            <el-option v-for="camera in cameraList" :key="camera.camera_id" :value="camera.camera_id" :label="camera.name">
              <div class="camera-option">
                <div class="camera-option-copy"><strong :title="camera.name">{{ camera.name }}</strong><small><template v-if="camera.name !== cameraSourceLabels[camera.source]">{{ cameraSourceLabels[camera.source] }} · </template>{{ camera.analysis?.scene }}</small></div>
                <span class="camera-option-state">{{ deviceStateLabel(camera) }}</span>
              </div>
            </el-option>
            <el-option v-if="!hasXiaozhiCameras" value="xiaozhi" label="小智摄像头">
              <div class="camera-option"><div class="camera-option-copy"><strong>小智摄像头</strong><small>连接 USB 设备后检测接入</small></div><span class="camera-option-state">待检测设备</span></div>
            </el-option>
          </el-select>
        </div>
        <div class="toolbar-field metric-field">
          <span id="metric-field-label">查看指标</span>
          <el-select :model-value="showResults ? selectedMetric : undefined"
            :disabled="!metricOptions.length" :placeholder="metricOptions.length ? '选择要查看的指标' : '暂无可查看指标'"
            aria-label="查看指标" aria-labelledby="metric-field-label" @change="changeMetric">
            <el-option v-for="metric in metricOptions" :key="metric.id" :value="metric.id" :label="metric.label" />
          </el-select>
        </div>
      </div>
      <div class="toolbar-actions">
        <div class="view-switch" role="group" aria-label="画面布局">
          <button type="button" :aria-pressed="viewMode === 'single'" @click="viewMode = 'single'"><el-icon><Monitor /></el-icon>单画面</button>
          <button type="button" :aria-pressed="viewMode === 'grid'" @click="viewMode = 'grid'"><el-icon><Grid /></el-icon>四画面</button>
        </div>
        <el-button text :disabled="!previewCameras.length" aria-label="重连画面" title="重连画面" @click="revision++"><el-icon><Refresh /></el-icon></el-button>
        <el-button text :disabled="!previewCameras.length" aria-label="全屏画面" title="全屏画面" @click="fullscreen"><el-icon><FullScreen /></el-icon></el-button>
        <el-button text :loading="loading" aria-label="刷新设备" title="刷新设备" @click="loadDevices()"><el-icon><Refresh /></el-icon></el-button>
        <el-button v-if="isXiaozhiSelected" @click="detectDevices = true">检测设备</el-button>
        <router-link to="/cameras" class="configuration-link"><el-icon><Setting /></el-icon>设备配置</router-link>
      </div>
    </section>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="overview-alert" />
    <el-alert v-else-if="cameraStore.deviceError" :title="cameraStore.deviceError" type="warning" show-icon :closable="false" class="overview-alert" />

    <el-dialog v-model="detectDevices" title="检测小智设备" width="min(720px, calc(100vw - 24px))" top="8vh" destroy-on-close :close-on-click-modal="false">
      <p class="detection-hint">已切换为小智摄像头，请先检测设备。检测成功后会自动连接监测画面。</p>
      <XiaozhiWorkspace v-if="detectDevices" detect-devices @detected="deviceDetected" @close="detectDevices = false" />
    </el-dialog>

    <div ref="workspace" class="overview-workspace" :class="{ 'has-results': showResults }" :style="workspaceStyle">
      <section ref="stage" class="overview-stage" aria-label="摄像头画面区">
        <div v-if="viewMode === 'grid' && pageCount > 1" ref="pagination" class="grid-pagination">
          <span>第 {{ page + 1 }} 组 · {{ previewCameras.length }} 路画面</span>
          <div><el-button text :disabled="page === 0" aria-label="上一组摄像头" @click="page--">上一组</el-button><el-button text :disabled="page + 1 >= pageCount" aria-label="下一组摄像头" @click="page++">下一组</el-button></div>
        </div>
        <div class="preview-surface" :class="{ 'is-grid': viewMode === 'grid' }">
          <CameraPreview v-for="camera in previewCameras" :key="camera.camera_id" :camera="camera"
            :enabled="pageActive && pageVisible" :compact="viewMode === 'grid'"
            :selected="viewMode === 'grid' && focusedCamera?.camera_id === camera.camera_id"
            :revision="revision" :feed="feedForCamera(camera)"
            @focus="focusCamera" @state-change="updateFrameState" />
          <div v-for="slot in (viewMode === 'grid' && previewCameras.length ? 4 - previewCameras.length : 0)" :key="'empty-' + slot" class="grid-placeholder" aria-hidden="true"><el-icon :size="28"><VideoCamera /></el-icon><span>暂无更多摄像头</span></div>
          <div v-if="!previewCameras.length" class="stage-empty">
            <el-icon :size="46"><VideoCamera /></el-icon><strong>{{ loading ? '正在读取摄像头' : '请选择摄像头查看画面' }}</strong>
            <span>设备接入与算法绑定请在设备配置中维护。</span>
            <el-button v-if="error" @click="loadDevices()">重新加载</el-button>
          </div>
        </div>
      </section>
      <aside v-show="showResults" class="analysis-aside" aria-label="当前摄像头分析结果">
        <header class="analysis-heading">
          <strong>识别结果</strong>
          <el-button text size="small" @click="showResults = false">收起</el-button>
        </header>
        <div class="analysis-body">
          <CameraResultsPanel v-if="canAnalyze" :vibration-available="vibrationAvailable" :active-metric="selectedMetric" />
          <el-empty v-else description="请选择已配置算法的摄像头" :image-size="70">
            <router-link to="/cameras" class="configuration-link">前往设备配置</router-link>
          </el-empty>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { FullScreen, Grid, Monitor, Refresh, Setting, VideoCamera } from '@element-plus/icons-vue'
import useCameraStore from '@/store/modules/camera'
import { useMonitorViewport } from '@/composables/useMonitorViewport'
import { cameraAnalysis, cameraConnectionState, cameraSourceLabels } from '@/utils/cameraManagement'
import CameraPreview from './CameraPreview.vue'
import CameraResultsPanel from './CameraResultsPanel.vue'
import XiaozhiWorkspace from '@/views/xiaozhi/index.vue'

const cameraStore = useCameraStore()
const overviewRoot = ref(null)
const viewportHeight = useMonitorViewport(overviewRoot, true, 0)
const stage = ref(null)
const workspace = ref(null)
const pagination = ref(null)
const workspaceGap = 8
const workspaceSize = reactive({ width: 0, height: 0, paginationHeight: 0 })
let layoutObserver
const loading = ref(false)
const error = ref('')
const detectDevices = ref(false)
const viewMode = ref('single')
const showResults = ref(true)
const selectedMetric = ref('')
const metricNames = { vibration: '心理状态', fatigue: '疲劳状态' }
const metricSelections = new Map()
const page = ref(0)
const revision = ref(0)
const frameStates = reactive({})
const feedStates = reactive({})
const frameSizes = reactive({})
const pageActive = ref(true)
const pageVisible = ref(!document.hidden)
let refreshTimer
let disposed = false
const cameraList = computed(() => cameraStore.cameraCatalog)
const hasXiaozhiCameras = computed(() => cameraList.value.some(camera => camera.source === 'xiaozhi'))
const isXiaozhiSelected = computed(() => cameraStore.cameraId === 'xiaozhi' || cameraStore.cameraId.startsWith('xiaozhi:'))
const metricOptions = computed(() => cameraStore.selectedCamera
  ? cameraAnalysis(cameraStore.selectedCamera).algorithm_ids.filter(id => metricNames[id]).map(id => ({ id, label: metricNames[id] })) : [])
const pageCount = computed(() => Math.ceil(cameraList.value.length / 4))
const previewCameras = computed(() => viewMode.value === 'single'
  ? (cameraStore.selectedCamera ? [cameraStore.selectedCamera] : [])
  : cameraList.value.slice(page.value * 4, page.value * 4 + 4))
const focusedCamera = computed(() => viewMode.value === 'single' ? cameraStore.selectedCamera
  : previewCameras.value.find(camera => camera.camera_id === cameraStore.cameraId) || previewCameras.value[0])
const canAnalyze = computed(() => pageActive.value && Boolean(cameraStore.selectedCamera)
  && cameraStore.selectedCamera.configured !== false && metricOptions.value.length > 0)
const vibrationAvailable = computed(() => feedStates[cameraStore.cameraId] !== 'raw')
const workspaceStyle = computed(() => {
  if (!workspaceSize.width || !workspaceSize.height) return {}
  const ratios = previewCameras.value.map(camera => {
    const size = frameSizes[camera.camera_id]
    return size ? size.width / size.height : 4 / 3
  })
  const ratio = Math.max(...ratios, 0) || 4 / 3
  const height = Math.max(0, workspaceSize.height - workspaceSize.paginationHeight)
  const preferred = viewMode.value === 'grid' ? Math.max(0, height - 10) * ratio + 10 : height * ratio
  const width = Math.min(preferred, Math.max(0, workspaceSize.width - workspaceGap - 300))
  return { '--monitor-video-width': width + 'px' }
})

watch([workspace, pagination], ([root, pager]) => {
  layoutObserver?.disconnect()
  if (!root || typeof ResizeObserver === 'undefined') return
  if (!pager) workspaceSize.paginationHeight = 0
  layoutObserver = new ResizeObserver(entries => {
    for (const entry of entries) {
      if (entry.target === root) {
        workspaceSize.width = entry.contentRect.width
        workspaceSize.height = entry.contentRect.height
      } else {
        const borderSize = entry.borderBoxSize?.[0]?.blockSize
        const height = borderSize ?? entry.target.getBoundingClientRect?.().height
          ?? entry.contentRect.height
        if (entry.target === pager) workspaceSize.paginationHeight = height + 8
      }
    }
  })
  for (const target of [root, pager].filter(Boolean)) layoutObserver.observe(target)
}, { flush: 'post' })

watch([() => cameraStore.cameraId, () => metricOptions.value.map(metric => metric.id).join(',')], () => {
  const ids = metricOptions.value.map(metric => metric.id)
  const previous = metricSelections.get(cameraStore.cameraId)
  selectedMetric.value = ids.includes(previous) ? previous : ids[0] || ''
  if (selectedMetric.value) metricSelections.set(cameraStore.cameraId, selectedMetric.value)
}, { immediate: true })
watch(previewCameras, cameras => {
  if (viewMode.value === 'grid' && cameras.length && !cameras.some(camera => camera.camera_id === cameraStore.cameraId)) cameraStore.selectCamera(cameras[0].camera_id)
})
watch(pageCount, count => { page.value = Math.min(page.value, Math.max(0, count - 1)) })
watch(viewMode, mode => {
  if (mode === 'grid') revealSelectedCamera()
  else {
    if (cameraStore.cameraId === 'xiaozhi') return
    const group = cameraList.value.slice(page.value * 4, page.value * 4 + 4)
    const camera = group.find(camera => camera.camera_id === cameraStore.cameraId) || group[0]
    if (camera) cameraStore.selectCamera(camera.camera_id)
  }
})
function changeMetric(id) {
  if (!metricOptions.value.some(metric => metric.id === id)) return
  selectedMetric.value = id
  metricSelections.set(cameraStore.cameraId, id)
  showResults.value = true
}
function revealSelectedCamera() {
  const index = cameraList.value.findIndex(camera => camera.camera_id === cameraStore.cameraId)
  page.value = index >= 0 ? Math.floor(index / 4) : 0
}
function selectCamera(cameraId) {
  if (cameraId !== 'xiaozhi' && !cameraList.value.some(camera => camera.camera_id === cameraId)) return
  const changed = cameraId !== cameraStore.cameraId
  cameraStore.selectCamera(cameraId)
  if (cameraId === 'xiaozhi') viewMode.value = 'single'
  if (changed && isXiaozhiSelected.value) detectDevices.value = true
  if (viewMode.value === 'grid') revealSelectedCamera()
}
async function deviceDetected(deviceId) {
  try {
    await cameraStore.loadXiaozhiDevices(true, true)
    if (disposed || !detectDevices.value) return
    const cameraId = `xiaozhi:${deviceId}`
    if (!cameraList.value.some(camera => camera.camera_id === cameraId)) {
      ElMessage.warning(cameraStore.deviceError || '检测已完成，设备列表尚未更新，请稍后刷新设备。')
      return
    }
    cameraStore.selectCamera(cameraId)
    if (viewMode.value === 'grid') revealSelectedCamera()
    revision.value++
    error.value = ''
    detectDevices.value = false
    ElMessage.success('设备检测成功，正在连接监测画面')
  } catch { if (!disposed) ElMessage.warning('检测已完成，设备列表读取失败，请刷新设备重试。') }
}
function focusCamera(camera) { selectCamera(camera.camera_id); viewMode.value = 'single' }
function updateFrameState({ cameraId, state, feed, width, height }) {
  frameStates[cameraId] = state
  if (feed) feedStates[cameraId] = feed
  if (width > 0 && height > 0) frameSizes[cameraId] = { width, height }
}
function feedForCamera(camera) {
  if (camera.camera_id !== cameraStore.cameraId) return 'raw'
  const analysis = cameraAnalysis(camera)
  if (analysis.algorithm_ids.includes('vibration')) return 'analysis'
  if (analysis.algorithm_ids.includes('fatigue') && analysis.show_overlay) return 'fatigue'
  return 'raw'
}
function deviceStateLabel(camera) {
  if (frameStates[camera.camera_id] === 'live') return '已收到画面'
  if (frameStates[camera.camera_id] === 'connecting') return '正在连接'
  if (frameStates[camera.camera_id] === 'waiting' || frameStates[camera.camera_id] === 'error') return '等待设备画面'
  return cameraConnectionState(camera).label
}
async function fullscreen() {
  try { if (stage.value?.requestFullscreen) await stage.value.requestFullscreen(); else ElMessage.info('当前浏览器不支持全屏显示') }
  catch { ElMessage.info('无法进入全屏，请在浏览器中重试') }
}
async function loadDevices(quiet = false) {
  if (loading.value) return
  loading.value = true
  if (!quiet) error.value = ''
  try {
    await cameraStore.loadXiaozhiDevices(true, true)
    if (disposed) return
    error.value = ''
    if (!cameraStore.selectedCamera && cameraStore.cameraId !== 'xiaozhi' && cameraList.value.length) {
      const camera = cameraList.value.find(camera => camera.configured !== false && camera.online === true)
        || cameraList.value.find(camera => camera.configured !== false) || cameraList.value[0]
      cameraStore.selectCamera(camera.camera_id)
    }
  } catch { if (!disposed) error.value = '设备列表读取失败，已有画面仍可继续查看，请刷新设备重试。' }
  finally { loading.value = false }
}
function visibilityChanged() { pageVisible.value = !document.hidden }
onMounted(() => {
  loadDevices()
  document.addEventListener('visibilitychange', visibilityChanged)
  refreshTimer = window.setInterval(() => { if (pageVisible.value && pageActive.value) loadDevices(true) }, 30000)
})
onActivated(() => { pageActive.value = true })
onDeactivated(() => { pageActive.value = false })
onBeforeUnmount(() => { disposed = true; layoutObserver?.disconnect(); window.clearInterval(refreshTimer); document.removeEventListener('visibilitychange', visibilityChanged) })
</script>

<style scoped>
.camera-overview { height:var(--overview-height,calc(100dvh - 84px));min-height:0;padding:0;box-sizing:border-box;display:flex;flex-direction:column;overflow:hidden;color:var(--el-text-color-primary); }
.configuration-link { display:inline-flex;align-items:center;gap:7px;color:var(--el-text-color-secondary);font-size:13px;line-height:1.8; }
.configuration-link:hover { color:var(--el-color-primary); }
.monitor-toolbar { display:flex;align-items:center;gap:18px;flex-wrap:wrap;padding:10px 12px;margin-bottom:8px;border-bottom:1px solid var(--el-border-color-light);background:var(--el-bg-color);flex-shrink:0; }
.toolbar-fields,.toolbar-actions,.toolbar-field { display:flex;align-items:center;gap:10px;min-width:0; }
.toolbar-fields { gap:22px; }.toolbar-field > span { white-space:nowrap;color:var(--el-text-color-regular);font-size:13px; }
.camera-field .el-select { width:250px; }.metric-field .el-select { width:190px; }
.toolbar-actions { margin-left:auto;gap:10px;flex-wrap:wrap; }
.toolbar-actions :deep(.el-button + .el-button) { margin-left:0; }.toolbar-actions :deep(.el-button) { padding:8px; }
.camera-option { display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:14px;width:100%;line-height:20px; }
.camera-option-copy { min-width:0; }
.camera-option strong { display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px;line-height:20px;font-weight:500; }
.camera-option small { display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px;color:var(--el-text-color-secondary);font-size:12px;line-height:18px; }
.camera-option-state { min-width:88px;box-sizing:border-box;text-align:center;white-space:nowrap;padding:3px 8px;border-radius:4px;background:var(--el-fill-color-light);color:var(--el-text-color-regular);font-size:12px;line-height:18px; }
.view-switch { display:flex;padding:3px;border:1px solid var(--el-border-color-light);border-radius:6px;background:var(--el-fill-color-light); }
.view-switch button { display:flex;align-items:center;gap:7px;padding:6px 10px;border:0;border-radius:4px;background:transparent;color:var(--el-text-color-regular);font-size:13px;cursor:pointer; }
.view-switch button[aria-pressed=true] { color:var(--el-color-primary);background:var(--el-bg-color);box-shadow:0 1px 4px #253b5310; }
.overview-alert { margin-bottom:12px;flex-shrink:0; }
.detection-hint { margin:0 0 14px;color:var(--el-text-color-regular);font-size:14px;line-height:1.6; }
.overview-workspace { display:grid;grid-template-columns:minmax(0,1fr);gap:var(--workspace-gap);flex:1;min-height:0; }
.overview-workspace.has-results { grid-template-columns:minmax(0,var(--monitor-video-width,60%)) minmax(300px,1fr); }
.overview-stage { display:flex;flex-direction:column;min-width:0;min-height:0; }
.grid-pagination { display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;font-size:12px;color:var(--el-text-color-secondary); }
.grid-pagination > div { display:flex;gap:8px; }.grid-pagination :deep(.el-button + .el-button) { margin-left:0; }
.preview-surface { display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,1fr);gap:10px;flex:1;min-height:0; }
.preview-surface.is-grid { grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:repeat(2,minmax(0,1fr)); }
.grid-placeholder { display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;border:1px dashed var(--el-border-color);border-radius:8px;background:var(--el-fill-color-light);color:var(--el-text-color-secondary);font-size:12px; }
.stage-empty { display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;border:1px solid var(--el-border-color-light);border-radius:8px;background:var(--el-fill-color-light);color:var(--el-text-color-secondary); }
.stage-empty strong { font-size:17px;font-weight:500; }.stage-empty > span { font-size:13px; }
.analysis-aside { display:flex;flex-direction:column;min-height:0;min-width:0;width:100%;height:100%; }
.analysis-heading { display:flex;justify-content:space-between;align-items:center;gap:10px;min-height:36px;padding:0 12px;background:var(--el-bg-color); }
.analysis-heading strong { font-size:14px; }
.analysis-body { flex:1;min-height:0;overflow:hidden; }
button:focus-visible,.configuration-link:focus-visible { outline:2px solid var(--el-color-primary);outline-offset:3px; }
.overview-stage:fullscreen { padding:0;background:var(--el-bg-color);height:100dvh;box-sizing:border-box; }
.overview-stage:fullscreen .preview-surface { flex:1;height:auto;min-height:0; }
@media(max-width:1300px) { .monitor-toolbar { gap:12px; }.toolbar-fields { gap:14px; } }
@media(max-width:1150px) { .overview-workspace,.overview-workspace.has-results { display:flex;flex-direction:column; }.overview-stage { flex:1; }.preview-surface { flex:1;height:100%;min-height:0; }.camera-overview :deep(.camera-preview) { height:100%;aspect-ratio:auto; }.grid-placeholder { min-height:0; }.stage-empty { min-height:0; }.analysis-aside { height:auto;flex:1.5; }.toolbar-fields { flex-basis:100%; }.toolbar-field { flex:1; }.toolbar-field .el-select { width:100%; }.toolbar-actions { margin-left:auto; } }
@media(max-width:600px) { .monitor-toolbar { padding:8px 10px; }.toolbar-fields { flex-direction:column;align-items:stretch;gap:8px;width:100%; }.toolbar-field > span { width:64px; }.toolbar-field .el-select { flex:1;min-width:0; }.toolbar-actions { width:100%;justify-content:flex-end;gap:6px; }.view-switch button { padding:6px 8px; }.preview-surface.is-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }.grid-placeholder { display:none; }.stage-empty { padding:12px;text-align:center; } }
.overview-stage:fullscreen .preview-surface { grid-template-rows:minmax(0,1fr); }
.overview-stage:fullscreen .preview-surface.is-grid { grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:repeat(2,minmax(0,1fr));align-items:stretch; }
.overview-stage:fullscreen :deep(.camera-preview) { height:100%;aspect-ratio:auto; }
</style>
<style>
/* The select popup is teleported outside the page; scope its row sizing by popup name. */
.monitor-camera-picker { min-width:min(360px,calc(100vw - 24px)) !important;max-width:calc(100vw - 24px); }
.monitor-camera-picker .el-select-dropdown__item { height:auto;min-height:60px;padding:10px 12px;line-height:normal; }
</style>
