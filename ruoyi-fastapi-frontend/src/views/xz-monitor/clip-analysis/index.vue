<template>
  <div class="clip-page">
    <div class="page-header">
      <div>
        <h2>摄像头视频分析</h2>
        <p>打开摄像头后检测稳定人脸并自动录制，停止后直接分析并展示结果。</p>
      </div>
      <el-button icon="Refresh" :loading="recordLoading" @click="loadRecords">刷新记录</el-button>
    </div>

    <div class="workspace">
      <section class="camera-panel">
        <div class="section-title">后端摄像头预览</div>
        <div class="camera-shell">
          <img
            v-if="previewEnabled"
            ref="cameraImageRef"
            :key="previewKey"
            :src="previewUrl"
            alt="后端本地摄像头预览"
            class="camera-video"
            @load="onPreviewLoad"
            @error="onPreviewError"
          />
          <div v-else class="camera-placeholder">摄像头未打开</div>
          <div class="camera-overlay">
            <el-tag :type="cameraStatus === 'online' ? 'success' : cameraStatus === 'error' ? 'danger' : 'info'">
              {{ cameraStatusText }}
            </el-tag>
            <span>{{ statusText }}</span>
          </div>
        </div>
        <div class="camera-toolbar">
          <el-button icon="VideoCamera" :loading="cameraLoading" :disabled="!isLocalCamera" @click="openCameraPreview">打开摄像头</el-button>
          <el-button icon="VideoPause" :disabled="!previewEnabled" @click="closeCameraPreview">关闭摄像头</el-button>
        </div>
        <div v-if="form.selectedCameraId && !isLocalCamera" class="camera-hint">
          <el-alert title="非本地摄像头暂不支持预览录制" type="info" :closable="false" show-icon />
        </div>
      </section>

      <section class="control-panel">
        <div class="section-title">后台分析设置</div>
        <el-form ref="formRef" :model="form" :rules="rules" label-width="108px" class="capture-form">
          <div class="form-grid">
            <el-form-item label="选择摄像头" prop="selectedCameraId">
              <el-select v-model="form.selectedCameraId" placeholder="请选择摄像头" filterable style="width: 100%" @change="onCameraChange">
                <el-option v-for="cam in cameraList" :key="cam.vidId" :label="cam.vidName" :value="cam.vidId">
                  <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span>{{ cam.vidName }}</span>
                    <el-tag size="small" :type="cam.vidType === 'local' ? 'success' : 'info'" style="margin-left: 8px;">
                      {{ cam.vidType || '未知' }}
                    </el-tag>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="人脸库分组" prop="groupId">
              <el-input-number v-model="form.groupId" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="匹配阈值" prop="threshold">
              <el-input-number v-model="form.threshold" :min="0" :max="1" :step="0.05" :precision="2" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="抽帧数量" prop="sampleCount">
              <el-input-number v-model="form.sampleCount" :min="1" :max="30" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="未匹配保存">
              <el-switch v-model="form.saveUnmatched" active-text="保存" inactive-text="不保存" />
            </el-form-item>
          </div>

          <div class="action-row">
            <el-button type="primary" icon="VideoPlay" :loading="cameraLoading" :disabled="!isLocalCamera" @click="openCameraPreview">
              开始检测录制
            </el-button>
            <el-button icon="RefreshLeft" :disabled="previewEnabled" @click="resetForm">重置</el-button>
          </div>
        </el-form>

        <div class="task-panel">
          <div class="task-row">
            <span>录制会话</span>
            <strong>{{ recordingSessionId || '-' }}</strong>
          </div>
          <div class="task-row">
            <span>录制状态</span>
            <el-tag :type="taskTagType">{{ taskStatusText }}</el-tag>
          </div>
        </div>
      </section>
    </div>

    <section class="result-panel">
      <div class="section-title">分析结果</div>
      <div v-if="analyzing" class="state-box">
        <el-icon class="is-loading" size="38"><Loading /></el-icon>
        <div>{{ statusText }}</div>
      </div>
      <el-empty v-else-if="!result" description="暂无分析结果" />
      <div v-else class="result-content">
        <div class="result-summary">
          <div>
            <span class="label">识别人员</span>
            <strong>{{ result.personName || 'Unknown' }}</strong>
          </div>
          <div>
            <span class="label">幸福指数</span>
            <strong>{{ result.happinessIndex ?? '-' }}</strong>
          </div>
          <div>
            <span class="label">风险等级</span>
            <el-tag :type="riskTagType(result.safetyRisk)">{{ result.safetyRisk || '-' }}</el-tag>
          </div>
          <div>
            <span class="label">相似度</span>
            <strong>{{ formatSimilarity(result.similarity) }}</strong>
          </div>
        </div>

        <video v-if="videoBlobUrl" :src="videoBlobUrl" controls class="result-video" />

        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="分析ID">{{ result.analysisId }}</el-descriptions-item>
          <el-descriptions-item label="摄像头">{{ selectedCamera?.vidName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ result.source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="截取文件">{{ result.clipName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="视频文件" :span="2">{{ result.videoPath || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="metric-grid">
          <div v-for="item in metricItems" :key="item.key" class="metric-item">
            <span>{{ item.label }}</span>
            <strong>{{ result.parameters?.[item.key] ?? '-' }}</strong>
          </div>
        </div>
      </div>
    </section>

    <section class="record-section">
      <div class="section-title">最近截取分析记录</div>
      <el-table v-loading="recordLoading" :data="records" border>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="source" label="视频来源" min-width="160" show-overflow-tooltip />
        <el-table-column prop="personName" label="人员" width="140" show-overflow-tooltip />
        <el-table-column prop="happinessIndex" label="幸福指数" width="120" align="center" />
        <el-table-column prop="happinessLevel" label="幸福等级" width="110" align="center">
          <template #default="{ row }">
            <el-tag>{{ row.happinessLevel || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="safetyRisk" label="安全风险" width="130" align="center" />
        <el-table-column prop="createTime" label="创建时间" width="180">
          <template #default="{ row }">{{ parseTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="previewRecord(row)">预览</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { listAnalysis } from '@/api/binhua/analysis'
import {
  analyzeByPath,
  getAnalysisVideoBlobUrl,
  getLocalCameraRecordingStatus,
  listClipVideos,
  resetBackendLocalCamera,
  startLocalCameraRecording,
  stopLocalCameraRecording
} from '@/api/xuzhou/clipAnalysis'
import { getToken } from '@/utils/auth'
import { parseTime } from '@/utils/ruoyi'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'
const cameraImageRef = ref(null)
const cameraLoading = ref(false)
const cameraList = ref([])
const cameraStatus = ref('idle')
const cameraStatusText = ref('未打开')
const statusText = ref('打开后由后端读取本地摄像头，仅预览不分析')
const previewEnabled = ref(false)
const previewKey = ref(Date.now())
const formRef = ref(null)
const analyzing = ref(false)
const recordLoading = ref(false)
const records = ref([])
const result = ref(null)
const videoBlobUrl = ref('')
const recordingSessionId = ref('')
const taskStatus = ref('idle')
const taskStatusText = ref('未开始')
let recordingPollTimer = null
let previewRetryTimer = null
let previewRetryCount = 0
let closingCamera = false
let recordingPollBusy = false
let pendingCloseAfterOpen = false
let unloadStopSent = false

const form = reactive({
  selectedCameraId: null,
  groupId: 1,
  threshold: 0.4,
  sampleCount: 8,
  saveUnmatched: false
})

const rules = computed(() => ({
  selectedCameraId: [{ required: true, message: '请选择摄像头', trigger: 'change' }],
  groupId: [{ required: true, message: '请输入人脸库分组', trigger: 'change' }],
  threshold: [{ required: true, message: '请输入匹配阈值', trigger: 'change' }],
  sampleCount: [{ required: true, message: '请输入抽帧数量', trigger: 'change' }]
}))

const selectedCamera = computed(() => {
  return cameraList.value.find(c => c.vidId === form.selectedCameraId) || null
})

const currentCameraIndex = computed(() => {
  const cam = selectedCamera.value
  if (cam && cam.vidType === 'local') {
    const idx = parseInt(cam.vidUri, 10)
    return isNaN(idx) ? 1 : idx
  }
  return 1
})

const isLocalCamera = computed(() => {
  return selectedCamera.value?.vidType === 'local'
})

const previewUrl = computed(() => {
  const timestamp = previewKey.value
  return `${baseURL}/xuzhou/clip-analysis-stream/preview/local?camera_index=${currentCameraIndex.value}&t=${timestamp}`
})

const metricItems = [
  { key: 'e1', label: 'E1 攻击性' },
  { key: 'e2', label: 'E2 压力' },
  { key: 'e3', label: 'E3 焦虑' },
  { key: 'e4', label: 'E4 可疑' },
  { key: 'e5', label: 'E5 平衡' },
  { key: 'e6', label: 'E6 魅力' },
  { key: 'e7', label: 'E7 能量' },
  { key: 'e8', label: 'E8 自我调节' },
  { key: 'e9', label: 'E9 抑制' },
  { key: 'e10', label: 'E10 神经质' },
  { key: 'e11', label: 'E11 抑郁' },
  { key: 'e12', label: 'E12 幸福' },
  { key: 'e13', label: 'E13 外向性' },
  { key: 'e14', label: 'E14 稳定性' }
]

const taskTagType = computed(() => {
  if (taskStatus.value === 'finished') return 'success'
  if (taskStatus.value === 'failed') return 'danger'
  if (['analyzing', 'recording', 'waiting_stable', 'stopping'].includes(taskStatus.value)) return 'warning'
  return 'info'
})

async function openCameraPreview() {
  await formRef.value?.validate()
  if (!form.selectedCameraId) {
    ElMessage.warning('请选择摄像头')
    return
  }
  if (!isLocalCamera.value) {
    ElMessage.warning('所选摄像头非本地摄像头，无法预览录制')
    return
  }
  if (previewEnabled.value || cameraLoading.value) return
  pendingCloseAfterOpen = false
  unloadStopSent = false
  stopPreviewRetry()
  previewRetryCount = 0
  cameraLoading.value = true
  previewEnabled.value = true
  previewKey.value = Date.now()
  cameraStatus.value = 'connecting'
  cameraStatusText.value = '连接中'
  statusText.value = '正在连接摄像头并准备稳定人脸录制'
  taskStatus.value = 'waiting_stable'
  taskStatusText.value = '等待稳定人脸'
  result.value = null
  clearVideoBlob()

  try {
    const res = await startLocalCameraRecording(buildRecordingPayload())
    const data = res.data || {}
    recordingSessionId.value = data.sessionId || ''
    taskStatus.value = data.status || 'waiting_stable'
    taskStatusText.value = data.message || '等待稳定人脸'
    statusText.value = taskStatusText.value
    pollRecordingStatus()
    if (pendingCloseAfterOpen) {
      await closeCameraPreview()
    }
  } catch (error) {
    cameraStatus.value = cameraStatus.value === 'online' ? 'online' : 'connecting'
    cameraStatusText.value = cameraStatus.value === 'online' ? '在线' : '重连中'
    taskStatus.value = 'failed'
    taskStatusText.value = '录制启动失败'
    statusText.value = `${error.message || '摄像头录制启动失败'}，预览画面继续连接中`
    schedulePreviewRetry()
    ElMessage.error(error.message || '摄像头录制启动失败')
  } finally {
    cameraLoading.value = false
    pendingCloseAfterOpen = false
  }
}

async function closeCameraPreview(options = {}) {
  const silent = options.silent === true
  if (cameraLoading.value && !recordingSessionId.value) {
    pendingCloseAfterOpen = true
    previewEnabled.value = false
    cameraStatus.value = 'idle'
    cameraStatusText.value = '已关闭'
    statusText.value = '摄像头将在连接完成后自动关闭'
    return
  }
  if (closingCamera) return
  closingCamera = true
  stopPreviewRetry()
  stopRecordingPoll()
  previewEnabled.value = false
  cameraStatus.value = 'idle'
  cameraStatusText.value = '已关闭'
  taskStatus.value = 'stopping'
  taskStatusText.value = '正在停止录制'
  statusText.value = '正在保留视频并开始分析'
  if (cameraImageRef.value) cameraImageRef.value.src = ''
  let shouldResetCamera = true
  try {
    if (recordingSessionId.value) {
      const res = await stopLocalCameraRecording({
        sessionId: recordingSessionId.value,
        enqueueAnalysis: false
      })
      handleRecordingSnapshot(res.data || {})
      shouldResetCamera = !['waiting_stable', 'recording'].includes(res.data?.status)

      // Direct analysis: get clip path and analyze synchronously
      const clipPath = res.data?.clipPath || res.data?.segments?.[0]?.clipPath
      if (clipPath) {
        await runDirectAnalysis(clipPath)
      } else if (!silent) {
        ElMessage.info('未生成视频片段')
      }
    }
    if (shouldResetCamera) {
      await resetBackendLocalCamera({ camera_index: currentCameraIndex.value })
    }
  } catch (error) {
    console.warn('关闭后端摄像头失败', error)
    if (!silent) {
      ElMessage.warning(error.message || '摄像头已关闭，请稍后查看结果')
    }
  } finally {
    closingCamera = false
  }
}

async function runDirectAnalysis(clipPath) {
  analyzing.value = true
  taskStatus.value = 'analyzing'
  taskStatusText.value = '正在分析'
  statusText.value = '正在分析视频，请稍候...'
  try {
    const res = await analyzeByPath({
      videoPath: clipPath,
      source: selectedCamera.value?.vidName || `local-camera-${currentCameraIndex.value}`,
      groupId: form.groupId,
      threshold: form.threshold,
      sampleCount: form.sampleCount,
      saveUnmatched: form.saveUnmatched
    })
    const data = res.data || {}
    result.value = {
      analysisId: data.analysisId,
      videoPath: data.videoPath,
      source: data.source,
      personName: data.personName,
      personId: data.personId,
      similarity: data.similarity,
      happinessIndex: data.happinessIndex,
      happinessLevel: data.happinessLevel,
      safetyRisk: data.safetyRisk,
      parameters: data.parameters || {}
    }
    analyzing.value = false
    taskStatus.value = 'finished'
    taskStatusText.value = '分析完成'
    statusText.value = '分析完成'
    if (result.value?.analysisId) {
      loadResultVideo(result.value.analysisId)
    }
    loadRecords()
    ElMessage.success('录制视频分析完成')
  } catch (error) {
    analyzing.value = false
    taskStatus.value = 'failed'
    taskStatusText.value = '分析失败'
    statusText.value = error.message || '分析失败'
    ElMessage.error(error.message || '分析失败')
  }
}

async function restartPreview() {
  if (!previewEnabled.value) return
  await closeCameraPreview()
  openCameraPreview()
}

function onPreviewLoad() {
  stopPreviewRetry()
  previewRetryCount = 0
  cameraLoading.value = false
  cameraStatus.value = 'online'
  cameraStatusText.value = '在线'
  statusText.value = taskStatusText.value || '摄像头实时预览中'
}

function onPreviewError() {
  cameraLoading.value = false
  schedulePreviewRetry()
}

function schedulePreviewRetry() {
  if (!previewEnabled.value) return
  stopPreviewRetry()
  previewRetryCount += 1
  cameraStatus.value = previewRetryCount > 8 ? 'error' : 'connecting'
  cameraStatusText.value = previewRetryCount > 8 ? '不可用' : '重连中'
  statusText.value = previewRetryCount > 8
    ? '摄像头画面暂时不可用，请检查索引或设备占用'
    : '摄像头画面连接中，正在自动重试'
  if (previewRetryCount > 8) return
  previewRetryTimer = window.setTimeout(() => {
    if (!previewEnabled.value) return
    previewKey.value = Date.now()
  }, Math.min(800 + previewRetryCount * 400, 3000))
}

function stopPreviewRetry() {
  if (previewRetryTimer) {
    window.clearTimeout(previewRetryTimer)
    previewRetryTimer = null
  }
}

function buildRecordingPayload() {
  return {
    source: selectedCamera.value?.vidName || `local-camera-${currentCameraIndex.value}`,
    cameraIndex: currentCameraIndex.value,
    groupId: form.groupId,
    threshold: form.threshold,
    sampleCount: form.sampleCount,
    saveUnmatched: form.saveUnmatched
  }
}

function resetForm() {
  if (previewEnabled.value) return
  const firstLocal = cameraList.value.find(c => c.vidType === 'local')
  form.selectedCameraId = firstLocal?.vidId ?? null
  form.groupId = 1
  form.threshold = 0.4
  form.sampleCount = 8
  form.saveUnmatched = false
  result.value = null
  recordingSessionId.value = ''
  taskStatus.value = 'idle'
  taskStatusText.value = '未开始'
  clearVideoBlob()
  formRef.value?.clearValidate()
}

function handleRecordingSnapshot(data) {
  if (!data) return
  recordingSessionId.value = data.sessionId || recordingSessionId.value
  taskStatus.value = data.status || taskStatus.value
  taskStatusText.value = data.message || taskStatusText.value
  statusText.value = taskStatusText.value
}

async function pollRecordingStatus() {
  stopRecordingPoll()
  if (!recordingSessionId.value) return
  recordingPollTimer = window.setInterval(async () => {
    if (!recordingSessionId.value || recordingPollBusy) return
    recordingPollBusy = true
    try {
      const res = await getLocalCameraRecordingStatus(recordingSessionId.value)
      handleRecordingSnapshot(res.data || {})
    } catch (error) {
      stopRecordingPoll()
    } finally {
      recordingPollBusy = false
    }
  }, 1500)
}

function stopRecordingPoll() {
  if (recordingPollTimer) {
    window.clearInterval(recordingPollTimer)
    recordingPollTimer = null
  }
}

function handlePageHide() {
  if (!recordingSessionId.value || unloadStopSent) return
  unloadStopSent = true
  const token = getToken()
  fetch(`${baseURL}/xuzhou/clip-analysis/recording/local/stop`, {
    method: 'POST',
    credentials: 'include',
    keepalive: true,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify({
      sessionId: recordingSessionId.value,
      enqueueAnalysis: false
    })
  }).catch(() => {})
}

async function loadResultVideo(analysisId) {
  if (!analysisId) return
  try {
    videoBlobUrl.value = await getAnalysisVideoBlobUrl(analysisId)
  } catch (error) {
    ElMessage.warning(error.message || '视频预览加载失败')
  }
}

async function loadRecords() {
  recordLoading.value = true
  try {
    const res = await listAnalysis({ pageNum: 1, pageSize: 8 })
    const data = res.data || {}
    records.value = data.records || data.rows || data.list || []
  } catch (error) {
    ElMessage.error(error.message || '加载分析记录失败')
  } finally {
    recordLoading.value = false
  }
}

async function previewRecord(row) {
  result.value = {
    analysisId: row.id,
    videoPath: row.videoPath,
    source: row.source,
    personName: row.personName,
    personId: row.personId,
    happinessIndex: row.happinessIndex,
    happinessLevel: row.happinessLevel,
    safetyRisk: row.safetyRisk,
    parameters: Object.fromEntries(metricItems.map(item => [item.key, row[item.key]]))
  }
  clearVideoBlob()
  await loadResultVideo(row.id)
}

function formatSimilarity(value) {
  const number = Number(value || 0)
  return number ? `${(number * 100).toFixed(1)}%` : '-'
}

function riskTagType(value) {
  if (String(value || '').includes('高')) return 'danger'
  if (String(value || '').includes('中')) return 'warning'
  return 'success'
}

function clearVideoBlob() {
  if (videoBlobUrl.value) {
    URL.revokeObjectURL(videoBlobUrl.value)
    videoBlobUrl.value = ''
  }
}

async function fetchCameraList() {
  try {
    const res = await listClipVideos({ pageNum: 1, pageSize: 100 })
    const data = res.data || {}
    cameraList.value = data.records || data.rows || data.list || []
    // Auto-select first local camera
    if (!form.selectedCameraId && cameraList.value.length > 0) {
      const firstLocal = cameraList.value.find(c => c.vidType === 'local')
      if (firstLocal) {
        form.selectedCameraId = firstLocal.vidId
      }
    }
  } catch (error) {
    ElMessage.error(error.message || '加载摄像头列表失败')
  }
}

async function onCameraChange() {
  if (previewEnabled.value) {
    await closeCameraPreview()
  }
  if (isLocalCamera.value) {
    openCameraPreview()
  }
}

onMounted(() => {
  window.addEventListener('pagehide', handlePageHide)
  fetchCameraList().then(() => {
    if (isLocalCamera.value) {
      openCameraPreview()
    }
  })
  loadRecords()
})

onActivated(() => {
  fetchCameraList()
  if (!previewEnabled.value && !cameraLoading.value && !recordingSessionId.value && isLocalCamera.value) {
    openCameraPreview()
  }
})

onDeactivated(() => {
  closeCameraPreview({ silent: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('pagehide', handlePageHide)
  stopPreviewRetry()
  stopRecordingPoll()
  clearVideoBlob()
  closeCameraPreview({ silent: true })
})
</script>

<style scoped>
.clip-page {
  padding: 20px;
  background: #f5f7fb;
  min-height: calc(100vh - 84px);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: #1f2d3d;
}

.page-header p {
  margin: 0;
  color: #606266;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) minmax(360px, 460px);
  gap: 18px;
}

.camera-panel,
.control-panel,
.result-panel,
.record-section {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 18px;
}

.section-title {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.camera-shell {
  position: relative;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  border-radius: 8px;
  background: #111827;
}

.camera-video,
.camera-placeholder {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #111827;
}

.camera-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #cbd5e1;
}

.camera-overlay {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 13px;
}

.camera-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}

.camera-hint {
  margin-top: 10px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
}

.result-panel,
.record-section {
  margin-top: 18px;
}

.state-box {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #606266;
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.result-summary > div {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px;
  background: #fafafa;
}

.label {
  display: block;
  margin-bottom: 6px;
  color: #909399;
  font-size: 13px;
}

.result-summary strong {
  color: #1f2d3d;
  font-size: 18px;
}

.result-video {
  width: 100%;
  max-height: 360px;
  background: #111827;
  border-radius: 8px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f7f9fc;
  color: #606266;
}

.metric-item strong {
  color: #303133;
}

@media (max-width: 1200px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .result-summary,
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-header,
  .camera-toolbar {
    flex-direction: column;
  }

  .form-grid,
  .result-summary,
  .metric-grid {
    grid-template-columns: 1fr;
  }
}

.task-panel {
  display: grid;
  gap: 10px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #e4e7ed;
}

.task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #606266;
  font-size: 13px;
}

.task-row strong {
  min-width: 0;
  max-width: 260px;
  overflow: hidden;
  color: #303133;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}
</style>
