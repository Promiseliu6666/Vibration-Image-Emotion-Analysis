<template>
  <div class="box-test-container">
    <!-- 顶部：选择盒子 -->
    <el-card class="mb4">
      <el-row :gutter="20" align="middle">
        <el-col :span="4">
          <span class="label-text">选择盒子:</span>
        </el-col>
        <el-col :span="8">
          <el-select v-model="selectedBox" placeholder="选择盒子" clearable filterable style="width:100%" @change="onBoxChange">
            <el-option v-for="box in onlineBoxes" :key="box.serial" :label="`${box.box_name} (${box.serial})`" :value="box.serial">
              <span>{{ box.box_name }}</span>
              <el-tag size="small" style="margin-left:6px">{{ box.serial }}</el-tag>
              <el-tag size="small" type="success" style="margin-left:4px">在线</el-tag>
            </el-option>
          </el-select>
        </el-col>
        <el-col :span="2">
          <el-button type="primary" :loading="loadingBoxes" @click="fetchBoxes">刷新</el-button>
        </el-col>
        <el-col :span="10">
          <el-space>
            <el-tag v-if="selectedBox" type="warning">盒子 {{ selectedBox }}</el-tag>
            <el-tag v-if="selectedBox" :type="boxOnline ? 'success' : 'danger'">{{ boxOnline ? '● 在线' : '○ 离线' }}</el-tag>
            <el-tag type="info" effect="plain">共 {{ filteredCameras.length }} 路</el-tag>
            <el-tag :type="runningCount > 0 ? 'success' : 'info'" effect="plain">运行 {{ runningCount }} 路</el-tag>
          </el-space>
        </el-col>
      </el-row>
    </el-card>

    <!-- 摄像头列表 -->
    <el-table v-loading="loading" :data="filteredCameras" border stripe style="width:100%">
      <el-table-column label="ID" prop="vidId" width="60" align="center" />
      <el-table-column label="名称" prop="vidName" min-width="120" show-overflow-tooltip />
      <el-table-column label="类型" width="70" align="center">
        <template #default="{ row }">{{ row.vidType || '-' }}</template>
      </el-table-column>
      <el-table-column label="RTSP地址" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.vidUri">{{ row.vidUri }}</span>
          <span v-else style="color:#909399">未配置</span>
        </template>
      </el-table-column>
      <el-table-column label="配置状态" width="90" align="center">
        <template #default="{ row }">
          <el-tooltip :content="configIssue(row)" placement="top" :disabled="!configIssue(row)">
            <el-tag :type="configIssue(row) ? 'warning' : 'success'" size="small">
              {{ configIssue(row) ? '待修复' : '正常' }}
            </el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="算法" min-width="160">
        <template #default="{ row }">
          <div v-if="boxAlgorithms[row.vidId] && boxAlgorithms[row.vidId].length > 0" class="alg-tags">
            <el-tag
              v-for="alg in boxAlgorithms[row.vidId]"
              :key="alg.algorithmCode"
              :type="alg.status === 'running' ? 'success' : 'info'"
              size="small"
              style="margin-right:4px;margin-bottom:2px"
            >
              {{ alg.algorithmName || alg.algorithmCode }}
              <span class="alg-dot" :style="{color: alg.status === 'running' ? '#67c23a' : '#909399'}">{{ alg.status === 'running' ? '●' : '○' }}</span>
            </el-tag>
          </div>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="运行状态" width="100" align="center">
        <template #default="{ row }">
          <el-tooltip :content="row.deviceErrorMessage || ''" placement="top" :disabled="!row.deviceErrorMessage">
            <el-tag :type="statusTag(row.deviceStatus)" size="small">
              {{ statusLabel(row.deviceStatus) }}
            </el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="center" fixed="right">
        <template #default="{ row }">
          <el-button-group>
            <el-button
              v-if="row.deviceStatus !== 'running'"
              type="success" size="small" :icon="VideoPlay"
              :loading="actionLoading[row.vidId]"
              @click="doStart(row)"
            >启动</el-button>
            <el-button
              v-else
              type="danger" size="small" :icon="VideoPause"
              :loading="actionLoading[row.vidId]"
              @click="doStop(row)"
            >停止</el-button>
          </el-button-group>
          <el-button
            v-if="row.deviceStatus === 'running' && row.srsFlvUrl"
            type="primary" size="small" :icon="View"
            style="margin-left:6px"
            @click="openPreview(row)"
          >查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="selectedBox && !loading && filteredCameras.length === 0" description="该盒子暂无绑定摄像头" />

    <!-- 视频预览弹窗 -->
    <el-dialog v-model="previewVisible" :title="`实时画面 - ${previewCamera?.vidName || ''}`" width="70%" @close="closePreview">
      <div class="preview-container" v-if="previewCamera?.vidType === 'local'">
        <img v-if="snapshotSrc" :src="snapshotSrc" class="preview-player" style="object-fit:contain" />
        <div v-else style="color:#fff;text-align:center;padding:40px">
          <p>{{ snapshotError || '无法获取快照' }}</p>
        </div>
      </div>
      <div class="preview-container" v-else>
        <video ref="previewVideo" class="preview-player" controls muted autoplay />
        <div class="preview-placeholder" v-show="previewLoading">
          <el-icon size="40"><VideoCamera /></el-icon>
          <p>视频加载中...</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoCamera, VideoPlay, VideoPause, View } from '@element-plus/icons-vue'
import { listVideo } from '@/api/xuzhou/video'
import { listBoxes, startCamera, stopCamera, getDeviceStatus, getCameraSnapshot } from '@/api/xuzhou/camera'
import flvjs from 'flv.js'

const loading = ref(false)
const loadingBoxes = ref(false)
const selectedBox = ref('')
const onlineBoxes = ref([])
const allCameras = ref([])
const boxAlgorithms = ref({})  // vidId → algorithms[]
const actionLoading = reactive({})
const previewVisible = ref(false)
const previewCamera = ref(null)
const previewLoading = ref(true)
const previewVideo = ref(null)
const snapshotSrc = ref('')
const snapshotError = ref('')
let flvPlayer = null
let snapshotTimer = null
let snapshotObjectUrl = ''

// ── computed ──
const boxOnline = computed(() => onlineBoxes.value.some(b => b.serial === selectedBox.value))

const boxSnapshotUrl = computed(() => {
  if (!previewCamera.value) return ''
  return `/xuzhou/command/camera_snapshot/${previewCamera.value.vidId}`
})

const filteredCameras = computed(() => {
  if (!selectedBox.value) return []
  return allCameras.value.filter(c => (c.vidBoxSerial || '') === selectedBox.value)
})

const runningCount = computed(() => filteredCameras.value.filter(c => c.deviceStatus === 'running').length)

function configIssue(row) {
  const issues = []
  if (!row.vidUri) issues.push('未配置RTSP地址')
  if (!row.vidBoxSerial) issues.push('未绑定盒子')
  return issues.join('; ')
}

function statusTag(status) {
  return { running: 'success', stopped: 'info', error: 'danger', offline: 'warning' }[status] || 'info'
}

function statusLabel(status) {
  return { running: '运行中', stopped: '已停止', error: '错误', offline: '盒子离线' }[status] || '未知'
}

// ── fetch ──
async function fetchBoxes() {
  loadingBoxes.value = true
  try {
    const res = await listBoxes()
    if (res.code === 200 && res.data) {
      onlineBoxes.value = [...(res.data.online || []), ...(res.data.offline || [])]
      // 从在线盒子的 cameras 数据中提取算法信息
      const algMap = {}
      ;(res.data.online || []).forEach(box => {
        ;(box.cameras || []).forEach(cam => {
          algMap[cam.vidId] = cam.algorithms || []
        })
      })
      boxAlgorithms.value = algMap
    }
  } catch { /* ignore */ }
  finally { loadingBoxes.value = false }
}

async function fetchCameras() {
  loading.value = true
  try {
    const res = await listVideo({ pageNum: 1, pageSize: 9999 })
    if (res.code === 200) {
      const rows = res.rows || []
      rows.forEach(c => {
        c.srsFlvUrl = `http://192.168.0.246:8080/live/publish_${c.vidId}.flv`
        c.deviceErrorMessage = c.deviceErrorMessage || ''
      })
      allCameras.value = rows
    }
  } catch { /* ignore */ }
  finally { loading.value = false }
}

function onBoxChange() {
  // auto-refresh when box changes
}

// ── actions ──
async function doStart(row) {
  actionLoading[row.vidId] = true
  try {
    await startCamera(row.vidId)
    ElMessage.success(`已向摄像头 ${row.vidName} 发送启动指令`)
    await new Promise(r => setTimeout(r, 2000))
    await refreshOne(row.vidId)
  } catch {
    ElMessage.error('启动失败')
  }
  finally { actionLoading[row.vidId] = false }
}

async function doStop(row) {
  actionLoading[row.vidId] = true
  try {
    await stopCamera(row.vidId)
    ElMessage.success(`已向摄像头 ${row.vidName} 发送停止指令`)
    await new Promise(r => setTimeout(r, 2000))
    await refreshOne(row.vidId)
  } catch {
    ElMessage.error('停止失败')
  }
  finally { actionLoading[row.vidId] = false }
}

async function refreshOne(vidId) {
  try {
    const res = await getDeviceStatus(vidId)
    if (res.code === 200 && res.data) {
      const cam = allCameras.value.find(c => c.vidId === vidId)
      if (cam) {
        cam.deviceStatus = res.data.status || 'unknown'
        cam.deviceErrorMessage = res.data.error_message || ''
      }
    }
  } catch { /* ignore */ }
}

// ── preview ──
function openPreview(row) {
  previewCamera.value = row
  previewVisible.value = true
  if (row.vidType === 'local') {
    loadSnapshot(row.vidId)
    snapshotTimer = setInterval(() => {
      loadSnapshot(row.vidId)
    }, 2000)
    return
  }
  previewLoading.value = true
  nextTick(() => initPlayer(row))
}

async function readBlobError(data) {
  try {
    const text = await data.text()
    const parsed = JSON.parse(text)
    return parsed.msg || parsed.detail || '快照接口未返回图片'
  } catch {
    return '快照接口未返回图片'
  }
}

async function loadSnapshot(vidId) {
  try {
    const data = await getCameraSnapshot(vidId)
    if (!data || !data.type?.startsWith('image/')) {
      throw new Error(await readBlobError(data))
    }
    const nextUrl = URL.createObjectURL(data)
    if (snapshotObjectUrl) {
      URL.revokeObjectURL(snapshotObjectUrl)
    }
    snapshotObjectUrl = nextUrl
    snapshotSrc.value = nextUrl
    snapshotError.value = ''
  } catch (error) {
    snapshotSrc.value = ''
    snapshotError.value = error?.message || '获取摄像头快照失败'
  }
}

function initPlayer(row) {
  if (!flvjs.isSupported()) { previewLoading.value = false; return }
  destroyPlayer()
  const el = previewVideo.value
  if (!el) return
  const url = row.srsFlvUrl || `http://192.168.0.246:8080/live/publish_${row.vidId}.flv`
  const player = flvjs.createPlayer({ type: 'flv', url }, { isLive: true })
  player.attachMediaElement(el)
  player.load()
  player.on(flvjs.Events.METADATA_ARRIVED, () => { previewLoading.value = false })
  player.on(flvjs.Events.ERROR, () => { previewLoading.value = false })
  player.play().catch(() => {})
  flvPlayer = player
}

function destroyPlayer() {
  if (flvPlayer) { try { flvPlayer.destroy() } catch { /* */ } flvPlayer = null }
}

function closePreview() {
  previewVisible.value = false
  destroyPlayer()
  previewLoading.value = true
  if (snapshotTimer) { clearInterval(snapshotTimer); snapshotTimer = null }
  if (snapshotObjectUrl) { URL.revokeObjectURL(snapshotObjectUrl); snapshotObjectUrl = '' }
  snapshotSrc.value = ''
  snapshotError.value = ''
}

// ── init ──
onMounted(async () => {
  await Promise.all([fetchBoxes(), fetchCameras()])
})
</script>

<style scoped>
.box-test-container { padding: 20px; }
.mb4 { margin-bottom: 16px; }
.label-text { font-size: 15px; font-weight: 500; }
.alg-dot { font-size: 10px; margin-left: 2px; }
.alg-tags { display: flex; flex-wrap: wrap; align-items: center; }
.preview-container {
  position: relative; width: 100%; height: 50vh;
  background: #000; border-radius: 8px; display: flex; justify-content: center; align-items: center; overflow: hidden;
}
.preview-player { width: 100%; height: 100%; object-fit: contain; z-index: 1; }
.preview-placeholder {
  position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: center;
  align-items: center; background: rgba(0,0,0,0.7); color: #fff; z-index: 2;
}
</style>
