<template>
  <div class="vibra-monitor">
    <!-- 标题与控制栏 -->
    <div class="header">
      <h2>视频监测</h2>
      <div class="controls">
        <div class="control-group">
          <CameraSwitcher size="small" compact />
        </div>
        <div class="control-group">
          <el-button
            type="warning"
            size="small"
            @click="resetParams"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </div>

    <div v-if="cameraSource==='xiaozhi'" class="xiaozhi-source-bar">
      <span>小智设备</span>
      <el-checkbox v-model="parallelPreview">并行预览</el-checkbox>
      <span>{{ xiaozhiSourceError || '仅使用小智原始画面，不会切换为本机摄像头' }}</span>
      <router-link to="/xiaozhi/devices">管理小智设备</router-link>
    </div>

    <section
      v-if="emailStatus !== 'idle'"
      class="email-feedback"
      :class="`email-feedback--${emailStatus}`"
      role="status"
      aria-live="polite"
    >
      <div class="email-feedback__mark" aria-hidden="true">
        <el-icon><Message /></el-icon>
      </div>
      <div class="email-feedback__body">
        <div class="email-feedback__meta">
          <span class="email-feedback__eyebrow">自动预警 · 邮件通知</span>
          <span class="email-feedback__state">{{ emailStatusLabel }}</span>
        </div>
        <div class="email-feedback__heading">
          <h3>{{ emailFeedbackTitle }}</h3>
          <time v-if="emailTimestamp">{{ emailTimestamp }}</time>
        </div>
        <p>{{ emailMessage || '邮件发送状态正在更新，请稍候。' }}</p>
      </div>
    </section>

    <!-- 主内容区 -->
    <div class="main-content" :class="{ 'main-content--with-email': emailStatus !== 'idle' }">
      <!-- 左侧：视频流 -->
      <div v-if="viewActive" class="video-section">
        <div v-if="cameraSource==='xiaozhi'&&parallelPreview" class="parallel-cameras">
          <div v-for="device in xiaozhiDevices" :key="device.device_id" class="parallel-camera" :class="{selected:xiaozhiDevice===device.device_id}" @click="xiaozhiDevice=device.device_id">
            <header><strong>{{ device.name }}</strong><span>{{ device.online?'在线':'未出图' }}</span></header>
            <img v-if="device.online" :src="deviceStreamUrl(device.device_id)" :alt="device.name+'实时画面'" />
            <div v-else class="camera-offline">此设备暂无画面，请检查 USB 连接并启动采集</div>
            <footer>{{ xiaozhiDevice===device.device_id?'当前分析详情':'点击查看该设备分析详情' }}</footer>
          </div>
          <p v-if="!xiaozhiDevices.length">尚未连接小智设备</p>
        </div>
        <div v-else class="video-wrapper">
          <img
            v-if="videoStreamUrl"
            ref="videoImg"
            :src="videoStreamUrl"
            :key="videoStreamUrl"
            alt="实时视频流"
            class="video-stream"
            @load="onVideoLoad"
            @error="onVideoError"
          />
          <div class="status-overlay">
            <div class="status-corner" :class="videoStatus">
              <span class="status-text">{{ statusText }}</span>
              <!-- 分析完成标识 -->
              <span v-if="analysisCompleted" class="completed-tag">分析完成</span>
            </div>
            <div v-if="videoStatus === 'error' && showConnectionTip" class="error-tip">
              <div class="error-icon">⚠️</div>
              <div class="error-message">{{ connectionTipText }}</div>
              <div class="error-hint">💡 请检查当前摄像头连接，或在上方切换来源</div>
            </div>
            <div v-if="videoStatus === 'error' && !showConnectionTip" class="reconnect-tip">
              视频流中断，浏览器正在自动重连...
            </div>
            <div v-if="videoStatus === 'online' && !isAnalyzing && !analysisCompleted" class="waiting-tip">
              {{ analysisMessage }}<br />
              <span v-if="stabilityProgress>0">稳定确认 {{ Math.round(stabilityProgress*100) }}%</span>
              <span v-else>请让人脸清晰位于画面中</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：参数面板 -->
      <div class="params-section">
        <div class="params-panel">
          <!-- 人员信息卡片（强制显示） -->
          <div class="person-card">
            <div class="person-header">
              <el-icon><User /></el-icon>
              <h4>识别人员信息</h4>
              <!-- 分析完成标识 -->
              <el-tag v-if="analysisCompleted" type="success" size="small">分析完成</el-tag>
            </div>
            <div class="person-content">
              <div class="person-item">
                <span class="person-label">人员ID：</span>
                <span class="person-value">{{ personInfo.id || '未知ID' }}</span>
              </div>
              <div class="person-item">
                <span class="person-label">人员姓名：</span>
                <span class="person-value">{{ personInfo.name || '未识别' }}</span>
              </div>
              <div class="person-item">
                <span class="person-label">匹配相似度：</span>
                <span class="person-value">{{ (personInfo.similarity || 0) * 100 | numberFormat }}%</span>
              </div>
              <div class="person-item">
                <span class="person-label">识别时间：</span>
                <span class="person-value">{{ personInfo.recognizeTime || new Date().toLocaleString() }}</span>
              </div>
            </div>
          </div>

          <!-- 切换按钮 -->
          <div class="switch-btn-container">
            <el-button
              type="primary"
              size="small"
              @click="toggleParamView"
            >
              {{ isShowE1E10 ? '收起' : '详情' }}
            </el-button>
          </div>

          <!-- 幸福指数卡片 -->
          <div v-if="!isShowE1E10 && hasAnalysisResults">
            <div class="wellbeing-card">
              <div class="wellbeing-header">
                <h3>幸福指数综合评估</h3>
                <div class="wellbeing-status">
                  <el-tag :type="getHappinessTagType(wellbeingResults.happiness_level)" size="small">
                    {{ wellbeingResults.happiness_level }}
                  </el-tag>
                  <el-tag :type="getSafetyTagType(wellbeingResults.safety_risk_level)" size="small">
                    {{ wellbeingResults.safety_risk_level }}
                  </el-tag>
                </div>
              </div>
              <div class="wellbeing-content">
                <div class="index-display">
                  <div class="index-value">{{ wellbeingResults.happiness_index.toFixed(1) }}</div>
                  <div class="index-label">幸福指数</div>
                  <div class="index-progress">
                    <div
                      class="progress-fill"
                      :style="{ width: `${Math.min(wellbeingResults.happiness_index, 100)}%` }"
                      :class="getHappinessLevelClass(wellbeingResults.happiness_index)"
                    ></div>
                  </div>
                </div>
                <div class="level-indicators">
                  <div class="level-item">
                    <span class="level-label">幸福等级:</span>
                    <span class="level-value" :class="getHappinessLevelClass(wellbeingResults.happiness_index)">
                      {{ wellbeingResults.happiness_level }}
                    </span>
                  </div>
                  <div class="level-item">
                    <span class="level-label">安全风险:</span>
                    <span class="level-value" :class="getSafetyLevelClass(wellbeingResults.safety_risk_level)">
                      {{ wellbeingResults.safety_risk_level }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div class="wellbeing-tips">
              <p><strong>幸福指数说明：</strong></p>
              <ul>
                <li><strong>幸福指数</strong>：综合评估当前心理状态 (1-100分)</li>
                <li><strong>幸福等级</strong>：≥80分"幸福达标"，≥60分"幸福待提升"，&lt;60分"幸福预警"</li>
                <li><strong>安全风险</strong>：≥70分"低风险"，≥40分"中风险"，&lt;40分"高风险"</li>
                <li><strong>检测规则</strong>：人脸稳定后积累有效画面；匹配人员后才关联档案保存</li>
              </ul>
            </div>
          </div>

          <!-- 无数据提示 -->
          <div v-if="!isShowE1E10 && !hasAnalysisResults">
            <div class="panel-header">
              <h3>实时监测数据</h3>
              <el-tag :type="isAnalyzing ? 'success' : 'info'" size="small">
                {{ isAnalyzing ? '分析进行中' : '等待分析' }}
              </el-tag>
            </div>
            <div v-if="!isAnalyzing" class="no-analysis-tip">
              <el-alert
                title="当前无有效分析"
                type="warning"
                :description="analysisMessage"
                :closable="false"
                show-icon
              />
            </div>
            <div v-if="isAnalyzing && !hasAnalysisResults" class="no-analysis-tip">
              <el-alert
                title="分析中"
                type="info"
                :description="analysisMessage"
                :closable="false"
                show-icon
              />
            </div>
          </div>

          <!-- e1-e14参数视图 -->
          <div v-if="isShowE1E10">
            <div class="panel-header">
              <h3>基础生理参数 (e1-e14)</h3>
              <el-tag type="info" size="small">
                {{ analysisCompleted ? '分析完成（结果固定）' : '实时分析中' }}
              </el-tag>
            </div>
            <div class="param-list" v-if="isAnalyzing">
              <div v-for="param in paramConfig" :key="param.key" class="param-item">
                <div class="param-label">
                  <span class="key">{{ param.key }}</span>
                  <span class="name">{{ param.name }}</span>
                </div>
                <div class="progress-wrapper">
                  <div class="progress-bar">
                    <div
                      class="progress-fill"
                      :style="{ width: `${Math.min(results[param.key] || 0, 100)}%` }"
                      :class="getLevelClass(results[param.key] || 0)"
                    ></div>
                  </div>
                  <span class="value">{{ (results[param.key] || 0).toFixed(1) }}</span>
                </div>
              </div>
            </div>
            <div v-if="!isAnalyzing" class="no-analysis-tip">
              <el-alert
                title="无分析数据"
                type="warning"
                description="请先完成人脸检测和分析，再查看详细参数。"
                :closable="false"
                show-icon
              />
            </div>
            <div class="tips">
              <p><strong>参数含义：</strong></p>
              <div class="param-meaning-grid">
                <div class="param-meaning-item" v-for="(item, index) in paramMeaningList" :key="index">
                  <span class="key-tip">{{ item.key }}</span>
                  <span class="meaning-text">{{ item.meaning }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { getToken } from '@/utils/auth'
import CameraSwitcher from '@/components/CameraSwitcher/index.vue'
import useCameraStore from '@/store/modules/camera'
import { cameraQueryString, toCameraId } from '@/utils/camera'
import { Message, Refresh, User } from '@element-plus/icons-vue'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'

// ==================== 状态管理 ====================
const cameraStore = useCameraStore()
const viewActive = ref(true)
const cameraSource = computed(() => cameraStore.source)
const xiaozhiDevice = computed({
  get: () => cameraStore.xiaozhiDeviceId,
  set: id => cameraStore.selectCamera(toCameraId('xiaozhi', id))
})
const xiaozhiDevices = computed(() => cameraStore.xiaozhiDevices)
const xiaozhiSourceError = computed(() => cameraStore.deviceError ||
  (xiaozhiDevices.value.length ? '' : '尚未连接小智设备，请到设备管理接入'))
const parallelPreview = ref(false)
const streamRevision = ref(0)
const parallelRevisions = ref(new Map())
const deviceStreamUrl = id => {
  const query = cameraQueryString(toCameraId('xiaozhi', id))
  return `${baseURL}/video/feed/analysis?${query}&t=${parallelRevisions.value.get(id) || 0}`
}
const sourceQuery = computed(() => {
  if (cameraSource.value === 'xiaozhi' && !xiaozhiDevice.value) return ''
  return cameraQueryString(cameraStore.cameraId)
})
const authHeaders = () => ({ Authorization: `Bearer ${getToken() || ''}` })
const videoStatus = ref('connecting')
const statusText = ref('连接中...')
const showConnectionTip = ref(false)
const connectionTipText = ref('')
const reconnectAttempts = ref(0)
const MAX_RECONNECT_ATTEMPTS = 3
const isAnalyzing = ref(false)
const hasAnalysisResults=ref(false)
const analysisMessage=ref('等待清晰人脸画面')
const stabilityProgress=ref(0)
const analysisCompleted = ref(false) // 新增：分析完成状态
const emailStatus = ref('idle')
const emailMessage = ref('')
const emailUpdatedAt = ref(null)
const emailStatusLabel = computed(() => ({
  sending: '正在发送',
  sent: '发送成功',
  failed: '发送失败',
  skipped: '未触发'
}[emailStatus.value] || '状态更新'))
const emailFeedbackTitle = computed(() => ({
  sending: '预警邮件正在投递',
  sent: '预警邮件已发送',
  failed: '预警邮件未能发送',
  skipped: '本次分析未触发邮件'
}[emailStatus.value] || '邮件状态'))
const emailTimestamp = computed(() => emailUpdatedAt.value
  ? new Date(emailUpdatedAt.value * 1000).toLocaleString('zh-CN', { hour12: false })
  : '')
let pollTimer
let pendingResults
let reconnectTimer

const isShowE1E10 = ref(false)

// 人员信息（默认值）
const personInfo = ref({
  id: '',
  name: '',
  similarity: 0,
  recognizeTime: ''
})

const videoImg = ref(null)

// ==================== 参数数据 ====================
const results = ref({
  e1: 0, e2: 0, e3: 0, e4: 0, e5: 0,
  e6: 0, e7: 0, e8: 0, e9: 0, e10: 0,
  e11: 0, e12: 0, e13: 0, e14: 0
})

const wellbeingResults = ref({
  happiness_index: 0,
  happiness_level: '',
  safety_risk_level: ''
})

const paramConfig = [
  { key: 'e1', name: '攻击性' },
  { key: 'e2', name: '压力' },
  { key: 'e3', name: '焦虑' },
  { key: 'e4', name: '可疑' },
  { key: 'e5', name: '平衡' },
  { key: 'e6', name: '魅力' },
  { key: 'e7', name: '能量' },
  { key: 'e8', name: '自我调节' },
  { key: 'e9', name: '抑制' },
  { key: 'e10', name: '神经质' },
  { key: 'e11', name: '忧郁' },
  { key: 'e12', name: '幸福' },
  { key: 'e13', name: '外向性' },
  { key: 'e14', name: '稳定性' }
]

const paramMeaningList = ref([
  { key: 'e1', meaning: '攻击性-微振动强度与波动' },
  { key: 'e2', meaning: '压力-左右脸振动不对称' },
  { key: 'e3', meaning: '焦虑-高频振动能量占比' },
  { key: 'e4', meaning: '可疑-综合异常程度' },
  { key: 'e5', meaning: '平衡-振动稳定性（越高越好）' },
  { key: 'e6', meaning: '魅力-左右脸协调性' },
  { key: 'e7', meaning: '能量-整体振动能量水平' },
  { key: 'e8', meaning: '自我调节-参数波动稳定性' },
  { key: 'e9', meaning: '抑制-攻击性与平衡的协调' },
  { key: 'e10', meaning: '神经质-压力与焦虑平均' },
  { key: 'e11', meaning: '忧郁 — 与能量水平的负相关' },
  { key: 'e12', meaning: '幸福 — 信息效率与能量消耗比' },
  { key: 'e13', meaning: '外向性 — 信息效率与能量相关性' },
  { key: 'e14', meaning: '稳定性 — 频率直方图与正态分布相似度' }
])

// ==================== 过滤器 ====================
const numberFormat = (value) => {
  return value.toFixed(2)
}

// ==================== 视频流URL ====================
const videoStreamUrl = computed(() => sourceQuery.value
  ? `${baseURL}/video/feed/analysis?${sourceQuery.value}&t=${streamRevision.value}`
  : '')

// ==================== 幸福指数计算（与后端同步）====================
const calculateHappinessLevel = (index) => {
  if (index >= 80) return '幸福达标'
  if (index >= 60) return '幸福待提升'
  return '幸福预警'
}

const calculateSafetyRiskLevel = (index) => {
  if (index >= 70) return '低风险'
  if (index >= 40) return '中风险'
  return '高风险'
}

const getHappinessLevelClass = (value) => {
  if (value >= 80) return 'happiness-high'
  if (value >= 60) return 'happiness-medium'
  if (value >= 40) return 'happiness-low'
  return 'happiness-very-low'
}

const getSafetyLevelClass = (level) => {
  switch(level) {
    case '低风险': return 'safety-low'
    case '中风险': return 'safety-medium'
    case '高风险': return 'safety-high'
    default: return 'safety-unknown'
  }
}

const getHappinessTagType = (level) => {
  switch(level) {
    case '幸福达标': return 'success'
    case '幸福待提升': return 'warning'
    case '幸福预警': return 'danger'
    default: return 'info'
  }
}

const getSafetyTagType = (level) => {
  switch(level) {
    case '低风险': return 'success'
    case '中风险': return 'warning'
    case '高风险': return 'danger'
    default: return 'info'
  }
}

const toggleParamView = () => {
  isShowE1E10.value = !isShowE1E10.value
  ElMessage.success(`已切换至${isShowE1E10.value ? '详细参数' : '幸福指数'}视图`)
}

// ==================== 视频流事件 ====================
const onVideoLoad = event => {
  if (event.currentTarget !== videoImg.value || videoStatus.value === 'online') return
  clearTimeout(reconnectTimer)
  videoStatus.value = 'online'
  statusText.value = '在线 · 等待人脸稳定...'
  reconnectAttempts.value = 0
  showConnectionTip.value = false
  startPolling()
}

const onVideoError = event => {
  if (event.currentTarget !== videoImg.value || !viewActive.value) return
  clearTimeout(reconnectTimer)
  videoStatus.value = 'error'
  reconnectAttempts.value++
  if (reconnectAttempts.value < MAX_RECONNECT_ATTEMPTS) {
    reconnectTimer = setTimeout(() => { streamRevision.value++ }, 1000)
    return
  }
  showConnectionTip.value = true
  stopPolling()
  clearResults()
  statusText.value = '摄像头不可用'
  connectionTipText.value = cameraSource.value === 'xiaozhi'
    ? '小智摄像头未返回画面，请在设备管理中启动采集并检查设备连接'
    : cameraSource.value === 'rtsp'
      ? '海康 RTSP 摄像头连接失败，请检查设备电源、IP 和 RTSP 地址'
      : '本地摄像头无法打开，请检查设备连接与占用情况'
}

// ==================== 参数管理 ====================
const clearResults = () => {
  Object.keys(results.value).forEach(key => {
    results.value[key] = 0
  })

  wellbeingResults.value = {
    happiness_index: 0,
    happiness_level: '',
    safety_risk_level: ''
  }
  
  personInfo.value = { id: '', name: '', similarity: 0, recognizeTime: '' }
  isAnalyzing.value = false
  hasAnalysisResults.value=false
  analysisMessage.value='等待清晰人脸画面'
  stabilityProgress.value=0
  analysisCompleted.value = false // 重置分析完成状态
  emailStatus.value='idle'
  emailMessage.value=''
  emailUpdatedAt.value=null
  isShowE1E10.value = false
}

// 优化：fetchResults函数（适配新版后端接口）
const fetchResults = async (query, signal) => {
  try {
    const res = await fetch(`${baseURL}/video/results?${query}`, {
      headers: authHeaders(), signal, cache: 'no-store'
    })
    if (!res.ok) return
    const data = await res.json()
    if (signal.aborted || query !== sourceQuery.value) return

    // 更新分析状态
    isAnalyzing.value = data.analyzing || false
    analysisCompleted.value = data.completed || false
    hasAnalysisResults.value=!!data.has_results
    analysisMessage.value=data.message||'等待清晰人脸画面'
    stabilityProgress.value=data.stability_progress||0
    emailStatus.value=data.email_status||'idle'
    emailMessage.value=data.email_message||''
    emailUpdatedAt.value=data.email_updated_at||null
    
    // Reflect the backend phase, rather than showing identity lookup as face instability.
    if (videoStatus.value !== 'error') {
      statusText.value = analysisMessage.value
      if (data.analyzing || data.has_results) videoStatus.value = 'online'
    }

    // 更新参数
    if (data.results) {
      Object.keys(results.value).forEach(key => {
        // 分析完成后不再平滑更新，直接使用最终值
        if (analysisCompleted.value) {
          results.value[key] = data.results[key] || 0
        } else {
          results.value[key] = results.value[key] * 0.7 + (data.results[key] ?? 0) * 0.3
        }
      })
    }

    // 更新人员信息（适配新版接口）
    personInfo.value = {
      id: data.identified ? data.person_id || '' : '',
      name: data.identified ? data.matched_person || '' : '未匹配人员',
      similarity: data.similarity || 0,
      recognizeTime: data.identified
        ? (personInfo.value.id === data.person_id ? personInfo.value.recognizeTime : '') || new Date().toLocaleString()
        : ''
    }

    // 幸福指数计算（与后端同步）
    const happinessIndex = results.value.e12 || 0
    wellbeingResults.value.happiness_index = happinessIndex
    wellbeingResults.value.happiness_level = calculateHappinessLevel(happinessIndex)
    wellbeingResults.value.safety_risk_level = calculateSafetyRiskLevel(happinessIndex)

  } catch (err) {
    if (!signal.aborted) console.warn('无法读取实时监测结果')
  }
}

// ==================== 轮询管理 ====================
const stopPolling = () => {
  clearTimeout(pollTimer)
  pendingResults?.abort()
  pendingResults = undefined
}

const startPolling = () => {
  stopPolling()
  if (!sourceQuery.value || document.hidden || !viewActive.value || showConnectionTip.value) return
  const controller = new AbortController()
  const query = sourceQuery.value
  pendingResults = controller
  async function poll() {
    await fetchResults(query, controller.signal)
    if (!controller.signal.aborted) {
      pollTimer = setTimeout(poll, analysisCompleted.value ? 5000 : 800)
    }
  }
  poll()
}

const handleVisibilityChange = () => {
  if (document.hidden) stopPolling()
  else startPolling()
}

const resetVisibleState = () => {
  clearTimeout(reconnectTimer)
  clearResults()
  reconnectAttempts.value = 0
  showConnectionTip.value = false
  videoStatus.value = sourceQuery.value ? 'connecting' : 'waiting'
  statusText.value = sourceQuery.value ? '正在连接所选摄像头…' : '等待选择小智设备'
}

const resetParams = () => {
  if (cameraSource.value === 'xiaozhi') cameraStore.loadXiaozhiDevices(true, true).catch(() => {})
  resetVisibleState()
  if (cameraSource.value === 'xiaozhi' && parallelPreview.value) {
    const id = xiaozhiDevice.value
    if (id) parallelRevisions.value.set(id, (parallelRevisions.value.get(id) || 0) + 1)
  } else if (sourceQuery.value) {
    streamRevision.value++
  }
  startPolling()
}

watch([sourceQuery, parallelPreview], () => {
  resetVisibleState()
  startPolling()
})

// ==================== 进度条颜色 ====================
const getLevelClass = (value) => {
  if (value >= 70) return 'high'
  if (value >= 40) return 'medium'
  return 'low'
}

// ==================== 生命周期 ====================
onMounted(() => {
  resetVisibleState()
  startPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onActivated(() => {
  if (viewActive.value) return
  viewActive.value = true
  resetVisibleState()
  startPolling()
})

onDeactivated(() => {
  viewActive.value = false
  clearTimeout(reconnectTimer)
  stopPolling()
})

onBeforeUnmount(() => {
  viewActive.value = false
  clearTimeout(reconnectTimer)
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
/* 人员信息卡片 */
.person-card {
  background: linear-gradient(135deg, #f0f8ff 0%, #e8f4f8 100%);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
  border: 1px solid #dee2e6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.person-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #dee2e6;
}

.person-header h4 {
  margin: 0;
  color: #2c3e50;
  font-size: 1.1em;
  font-weight: 600;
}

.person-header .el-icon {
  color: #3b82f6;
  font-size: 1.2em;
}

.person-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.person-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.person-label {
  font-size: 0.85em;
  color: #6c757d;
  font-weight: 500;
}

.person-value {
  font-size: 0.95em;
  color: #2c3e50;
  font-weight: 600;
}

/* 分析完成标签 */
.completed-tag {
  background: rgba(46, 204, 113, 0.9);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  margin-top: 4px;
  display: inline-block;
}

.email-feedback {
  --mail-accent: #2563eb;
  --mail-border: #bfdbfe;
  --mail-surface: #eff6ff;
  --mail-ink: #1e3a8a;
  position: relative;
  isolation: isolate;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 18px;
  min-height: 122px;
  box-sizing: border-box;
  padding: 20px 24px;
  margin: 0 0 20px;
  overflow: hidden;
  color: var(--mail-ink);
  background:
    radial-gradient(circle at 92% -20%, color-mix(in srgb, var(--mail-accent) 15%, transparent) 0 34%, transparent 35%),
    linear-gradient(135deg, #ffffff 0%, var(--mail-surface) 100%);
  border: 1px solid var(--mail-border);
  border-left: 5px solid var(--mail-accent);
  border-radius: 16px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
}

.email-feedback--sent {
  --mail-accent: #07825b;
  --mail-border: #b7e4cf;
  --mail-surface: #ecfdf5;
  --mail-ink: #065f46;
}

.email-feedback--failed {
  --mail-accent: #d14343;
  --mail-border: #fecdd3;
  --mail-surface: #fff1f2;
  --mail-ink: #9f1239;
}

.email-feedback--skipped {
  --mail-accent: #c47b10;
  --mail-border: #fde5b0;
  --mail-surface: #fffbeb;
  --mail-ink: #92400e;
}

.email-feedback__mark {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  align-self: center;
  color: var(--mail-accent);
  font-size: 24px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--mail-border);
  border-radius: 16px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.email-feedback__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.email-feedback__meta,
.email-feedback__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.email-feedback__meta {
  margin-bottom: 7px;
}

.email-feedback__eyebrow {
  color: var(--mail-accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.email-feedback__state {
  flex-shrink: 0;
  padding: 4px 10px;
  color: var(--mail-accent);
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--mail-border);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.email-feedback--sending .email-feedback__state::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 7px;
  background: currentColor;
  border-radius: 50%;
  animation: email-feedback-pulse 1.4s ease-in-out infinite;
}

.email-feedback__heading h3 {
  margin: 0;
  color: var(--mail-ink);
  font-size: 1.08rem;
  font-weight: 750;
  letter-spacing: -0.01em;
}

.email-feedback__heading time {
  flex-shrink: 0;
  color: color-mix(in srgb, var(--mail-ink) 62%, #ffffff);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.email-feedback__body p {
  margin: 7px 0 0;
  color: color-mix(in srgb, var(--mail-ink) 82%, #ffffff);
  font-size: 13px;
  line-height: 1.6;
}

@keyframes email-feedback-pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.wellbeing-card {
  background: rgba(245, 247, 250, 0.78);
  backdrop-filter: blur(10px);          
  -webkit-backdrop-filter: blur(10px);  
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(200, 220, 255, 0.5);
  color: #1e293b;
}

.wellbeing-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.wellbeing-header h3 {
  color: #1e293b;
  font-size: 1.25em;
  font-weight: 700;
  letter-spacing: 0.5px;
  margin: 0;
}

.index-display {
  text-align: center;
  margin-bottom: 20px;
}

.index-value {
  font-size: 3.4em;
  font-weight: 800;
  color: #2563eb;
  text-shadow: 0 2px 8px rgba(37, 99, 235, 0.18);
  margin-bottom: 10px;
}

.index-label {
  font-size: 1.1em;
  color: #64748b;
  margin-bottom: 10px;
}

.index-progress {
  width: 100%;
  height: 14px;
  border-radius: 7px;
  overflow: hidden;
  background: rgba(226, 232, 240, 0.9);
  border: 1px solid rgba(203, 213, 225, 0.6);
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.06);
}

.index-progress .progress-fill {
  height: 100%;
  border-radius: 6px;
  box-shadow: 0 0 12px rgba(0,0,0,0.15);
  transition: width 1s ease-out;
}

/* 幸福指数颜色渐变 */
.index-progress .progress-fill.happiness-very-low {
  background: linear-gradient(90deg, #f87171, #ef4444);
}
.index-progress .progress-fill.happiness-low {
  background: linear-gradient(90deg, #fb923c, #f97316);
}
.index-progress .progress-fill.happiness-medium {
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
}
.index-progress .progress-fill.happiness-high {
  background: linear-gradient(90deg, #4ade80, #22c55e);
}

.level-indicators {
  display: flex;
  justify-content: space-around;
  gap: 20px;
}

.level-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.level-label {
  font-size: 0.9em;
  color: #7f8c8d;
}

.level-value {
  font-size: 1.1em;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 20px;
  min-width: 80px;
  text-align: center;
}

.level-value.happiness-high {
  background: rgba(46, 204, 113, 0.15);
  color: #27ae60;
}
.level-value.happiness-medium {
  background: rgba(52, 152, 219, 0.15);
  color: #2980b9;
}
.level-value.happiness-low {
  background: rgba(231, 126, 34, 0.15);
  color: #e67e22;
}
.level-value.happiness-very-low {
  background: rgba(231, 76, 60, 0.15);
  color: #c0392b;
}

.level-value.safety-low {
  background: rgba(46, 204, 113, 0.15);
  color: #27ae60;
}
.level-value.safety-medium {
  background: rgba(241, 196, 15, 0.15);
  color: #f39c12;
}
.level-value.safety-high {
  background: rgba(231, 76, 60, 0.15);
  color: #c0392b;
}
.level-value.safety-unknown {
  background: rgba(189, 195, 199, 0.15);
  color: #7f8c8d;
}

/* 幸福指数说明 */
.wellbeing-tips {
  margin-top: 0;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid #3498db;
}

.wellbeing-tips p {
  margin: 0 0 10px 0;
  font-weight: 600;
  color: #2c3e50;
}

.wellbeing-tips ul {
  padding-left: 20px;
  margin: 0;
}

.wellbeing-tips li {
  margin-bottom: 6px;
  color: #555;
  line-height: 1.5;
}

/* 切换按钮 */
.switch-btn-container {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

/* 参数含义排版 */
.param-meaning-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding-left: 0;
  margin: 10px 0;
  list-style: none;
}

.param-meaning-item {
  display: flex;
  align-items: flex-start;
  font-size: 13px;
  color: #7f8c8d;
  line-height: 1.6;
}

.key-tip {
  display: inline-block;
  width: 30px;
  font-weight: bold;
  color: #3498db;
  margin-right: 8px;
  flex-shrink: 0;
}

.meaning-text {
  flex: 1;
}

/* 基础布局 */
.vibra-monitor {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
  font-family: 'Microsoft YaHei', Arial, sans-serif;
  background: #f4f6f9;
  min-height: 100vh;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.header h2 {
  margin: 0;
  color: #2c3e50;
  font-size: 1.8em;
}

.controls {
  display: flex;
  gap: 20px;
  align-items: center;
  flex-wrap: wrap;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
}

.main-content {
  display: flex;
  gap: 30px;
  height: calc(100vh - 120px);
}

.main-content--with-email {
  height: calc(100vh - 250px);
  min-height: 520px;
}

.video-section {
  flex: 1.2;
  min-width: 0;
}

.video-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
}

.video-stream {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.status-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 12px;
}

.status-corner {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  z-index: 10;
  align-self: flex-end;
}

.status-text {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: bold;
  color: #fff;
}

.status-corner.online .status-text {
  background: rgba(46, 204, 113, 0.9);
}

.status-corner.error .status-text {
  background: rgba(231, 76, 60, 0.9);
}

.status-corner.connecting .status-text {
  background: rgba(52, 152, 219, 0.9);
}

.status-corner.waiting .status-text {
  background: rgba(52, 152, 219, 0.9);
}

.reconnect-tip, .waiting-tip, .error-tip {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 20px 40px;
  border-radius: 16px;
  font-size: 1.2em;
  text-align: center;
}

.error-icon {
  font-size: 2em;
  margin-bottom: 10px;
}

.error-hint {
  margin-top: 10px;
  font-size: 0.9em;
  color: #ccc;
}

.params-section {
  flex: 0.8;
  min-width: 400px;
  max-width: 500px;
}

.params-panel {
  width: 100%;
  height: 100%;
  background: #ffffff;
  border-radius: 16px;
  padding: 28px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-shrink: 0;
}

.panel-header h3 {
  margin: 0;
  color: #2c3e50;
  font-size: 1.4em;
}

.param-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
  margin-bottom: 20px;
}

.param-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.5);
}

.param-label {
  width: 110px;
  flex-shrink: 0;
}

.param-label .key {
  font-size: 1.1rem;
  font-weight: 700;
  color: #3b82f6;
  letter-spacing: 0.5px;
}

.param-label .name {
  font-size: 0.82rem;
  color: #64748b;
  margin-top: 2px;
  font-weight: 400;
}

.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.progress-bar {
  height: 18px;
  background: #e2e8f0;
  border-radius: 9px;
  overflow: hidden;
  flex: 1;
}

.progress-fill {
  height: 100%;
  border-radius: 8px;
  transition: width 0.5s ease;
}

.progress-fill.high {
  background: linear-gradient(90deg, #4ade80, #22c55e);
}

.progress-fill.medium {
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
}

.progress-fill.low {
  background: linear-gradient(90deg, #fb923c, #f97316);
}

.value {
  font-size: 0.9rem;
  font-weight: 600;
  color: #2c3e50;
  min-width: 50px;
  text-align: right;
}

.no-analysis-tip {
  margin-top: 20px;
}

.tips {
  margin-top: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid #3498db;
}

.tips p {
  margin: 0 0 10px 0;
  font-weight: 600;
  color: #2c3e50;
}

@media (max-width: 900px) {
  .main-content,
  .main-content--with-email {
    height: auto;
    min-height: 0;
    flex-direction: column;
  }

  .video-wrapper {
    min-height: 360px;
  }

  .params-section {
    width: 100%;
    min-width: 0;
    max-width: none;
  }
}

@media (max-width: 600px) {
  .email-feedback {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 18px;
  }

  .email-feedback__mark {
    width: 42px;
    height: 42px;
    align-self: start;
  }

  .email-feedback__meta,
  .email-feedback__heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .email-feedback--sending .email-feedback__state::before {
    animation: none;
  }
}
</style>
<style scoped>
.parallel-cameras{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start}.parallel-camera{border:2px solid #dce5f0;border-radius:8px;overflow:hidden;background:#14202c;cursor:pointer}.parallel-camera.selected{border-color:#409eff}.parallel-camera header{display:flex;justify-content:space-between;gap:10px;padding:12px;background:#fff;font-size:13px;color:#334d68}.parallel-camera header span{font-size:12px;color:#74899a}.parallel-camera img{display:block;width:100%;aspect-ratio:4/3;object-fit:contain}.camera-offline{aspect-ratio:4/3;display:grid;place-items:center;text-align:center;padding:20px;color:#b7c8d7;font-size:13px;line-height:1.8}.parallel-camera footer{padding:10px;background:#f2f7fc;color:#44718f;font-size:12px}@media(max-width:1000px){.parallel-cameras{grid-template-columns:1fr}}
</style>
