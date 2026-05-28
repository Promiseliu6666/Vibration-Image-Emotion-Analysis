<template>
  <div class="vibra-monitor">
    <!-- 标题与控制栏 -->
    <div class="header">
      <h2>振动图像心理生理实时监测系统</h2>
      <div class="controls">
        <div class="control-group">
          <label>摄像头：</label>
          <el-select v-model="selectedVidId" size="small" style="width: 240px" filterable @change="onCameraChange">
            <el-option label="本地摄像头（通用）" value="" />
            <el-option
              v-for="cam in cameraOptions"
              :key="cam.vidId"
              :label="`${cam.vidName} (${cam.vidType || 'rtsp'})`"
              :value="cam.vidId"
            >
              <span>{{ cam.vidName }}</span>
              <el-tag v-if="cam.vidBoxSerial" size="small" type="warning" style="margin-left:6px">盒子-{{ cam.vidBoxSerial }}</el-tag>
              <el-tag v-else size="small" type="success" style="margin-left:6px">本地</el-tag>
            </el-option>
          </el-select>
        </div>
        <div class="control-group">
          <el-tag v-if="selectedCamera && selectedCamera.vidAlgorithmName?.length" type="info" size="small" effect="plain">
            算法: {{ selectedCamera.vidAlgorithmName.join(', ') }}
          </el-tag>
          <el-tag v-else-if="!selectedVidId" type="success" size="small" effect="plain">默认全开</el-tag>
          <el-tag v-else type="warning" size="small" effect="plain">未配置算法</el-tag>
        </div>
        <div class="control-group">
          <el-button
            type="warning"
            size="small"
            @click="resetParams"
            :loading="resetLoading"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：视频流 -->
      <div class="video-section">
        <div class="video-wrapper">
          <img
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
              <div class="error-hint">💡 请在上方切换其他摄像头源重试</div>
            </div>
            <div v-if="videoStatus === 'error' && !showConnectionTip" class="reconnect-tip">
              视频流中断，浏览器正在自动重连...
            </div>
            <div v-if="videoStatus === 'online' && !isAnalyzing" class="waiting-tip">
              等待检测到稳定人脸...<br />
              请正对摄像头，保持头部静止几秒钟
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
          <div v-if="!isShowE1E10 && isAnalyzing && wellbeingResults.happiness_index > 0">
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
                <li><strong>幸福等级</strong>：≥80分"幸福达标"，≥60分"幸福待提升"，<60分"幸福预警"</li>
                <li><strong>安全风险</strong>：≥70分"低风险"，≥40分"中风险"，<40分"高风险"</li>
                <li><strong>检测规则</strong>：人脸稳定后持续分析10秒，结果自动保存</li>
              </ul>
            </div>
          </div>

          <!-- 无数据提示 -->
          <div v-if="!isShowE1E10 && (!isAnalyzing || wellbeingResults.happiness_index <= 0)">
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
                description="可能原因：视频源连接失败、未检测到人脸、头部未稳定。请检查摄像头并正对镜头保持静止。"
                :closable="false"
                show-icon
              />
            </div>
            <div v-if="isAnalyzing && wellbeingResults.happiness_index <= 0" class="no-analysis-tip">
              <el-alert
                title="分析中"
                type="info"
                description="正在采集数据计算幸福指数，请稍候（预计10秒）..."
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
import { ref, computed, onMounted, onBeforeUnmount, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, User } from '@element-plus/icons-vue'
import { listVideo } from '@/api/xuzhou/video'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'

// ==================== 状态管理 ====================
const selectedVidId = ref('')  // 空字符串 = 通用本地摄像头
const cameraOptions = ref([])
const selectedCamera = computed(() => cameraOptions.value.find(c => c.vidId === selectedVidId.value))
const videoStatus = ref('connecting')
const statusText = ref('连接中...')
const showConnectionTip = ref(false)
const connectionTipText = ref('')
const resetLoading = ref(false)
const reconnectAttempts = ref(0)
const MAX_RECONNECT_ATTEMPTS = 3
const shouldPolling = ref(true)
const isAnalyzing = ref(false)
const analysisCompleted = ref(false) // 新增：分析完成状态
let pollTimer = null

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
const videoStreamUrl = computed(() => {
  const timestamp = new Date().getTime()
  const params = selectedVidId.value
    ? `vid_id=${selectedVidId.value}&t=${timestamp}`
    : `source=local&t=${timestamp}`
  return `${baseURL}/video/feed/analysis?${params}`
})

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
const onVideoLoad = () => {
  videoStatus.value = 'online'
  statusText.value = '在线 · 等待人脸稳定...'
  reconnectAttempts.value = 0
  showConnectionTip.value = false
  shouldPolling.value = true
  startPolling()
}

const onVideoError = () => {
  videoStatus.value = 'error'
  reconnectAttempts.value++

  if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
    showConnectionTip.value = true
    shouldPolling.value = false
    stopPolling()
    clearResults()
    statusText.value = '摄像头不可用'
    connectionTipText.value = selectedVidId.value
      ? `❌ 摄像头 ${selectedCamera.value?.vidName || selectedVidId.value} 连接失败\n请检查设备电源、IP或视频流地址`
      : '❌ 本地摄像头无法打开\n请确认设备未被其他程序占用'
  }
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
  analysisCompleted.value = false // 重置分析完成状态
  isShowE1E10.value = false
}

// 优化：fetchResults函数（适配新版后端接口）
const fetchResults = async () => {
  if (!shouldPolling.value) return

  try {
    const queryParam = selectedVidId.value
      ? `vid_id=${selectedVidId.value}`
      : 'source=local'
    const res = await fetch(`${baseURL}/video/results?${queryParam}`)
    const data = await res.json()

    console.log("后端返回数据：", data)

    // 更新分析状态
    isAnalyzing.value = data.analyzing || false
    analysisCompleted.value = data.completed || false
    
    // 更新视频状态文本
    if (isAnalyzing.value) {
      videoStatus.value = 'online'
      if (analysisCompleted.value) {
        statusText.value = '分析完成（结果已固定）'
      } else {
        statusText.value = '分析中（预计10秒）'
      }
    } else {
      statusText.value = data.message || '等待人脸稳定...'
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
      id: data.person_id || '',
      name: data.matched_person || '',
      similarity: data.similarity || 0,
      recognizeTime: personInfo.value.recognizeTime || new Date().toLocaleString()
    }

    // 幸福指数计算（与后端同步）
    const happinessIndex = results.value.e12 || 0
    wellbeingResults.value.happiness_index = happinessIndex
    wellbeingResults.value.happiness_level = calculateHappinessLevel(happinessIndex)
    wellbeingResults.value.safety_risk_level = calculateSafetyRiskLevel(happinessIndex)

  } catch (err) {
    console.error('轮询失败', err)
  }
}

// ==================== 轮询管理 ====================
const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  // 分析完成后降低轮询频率（每5秒一次）
  const interval = analysisCompleted.value ? 5000 : 800
  pollTimer = setInterval(fetchResults, interval)
  fetchResults() // 立即执行一次
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const handleVisibilityChange = () => {
  if (document.hidden) {
    stopPolling()
  } else if (shouldPolling.value && videoStatus.value === 'online') {
    startPolling()
  }
}

// ==================== 用户操作 ====================
const resetParams = async () => {
  resetLoading.value = true
  try {
    const queryParam = selectedVidId.value
      ? `vid_id=${selectedVidId.value}`
      : 'source=local'
    const res = await fetch(`${baseURL}/video/reset?${queryParam}`)
    if (res.ok) {
      const data = await res.json()
      clearResults()
      videoStatus.value = 'waiting'
      statusText.value = '已刷新，等待人脸检测...'
      ElMessage.success(data.message || '已刷新！摄像头将重新检测人脸')
      startPolling()
    } else {
      ElMessage.error('刷新失败')
    }
  } catch (err) {
    ElMessage.error('请求失败')
  } finally {
    resetLoading.value = false
  }
}

// ==================== 摄像头列表获取 ====================
async function fetchCameras() {
  try {
    const res = await listVideo({ pageNum: 1, pageSize: 9999 })
    console.log('[druid] 摄像头列表API返回:', res)
    if (res.code === 200) {
      const allCameras = res.rows || []
      console.log('[druid] 全部摄像头:', allCameras.length, '个')
      // 优先显示有算法的摄像头，也显示本地未绑定盒子的摄像头
      cameraOptions.value = allCameras.filter(cam => {
        const hasAlg = cam.vidAlgorithm?.length
        const isLocal = cam.vidType === 'local' && !cam.vidBoxSerial
        return hasAlg || isLocal
      })
      console.log('[druid] 过滤后摄像头:', cameraOptions.value.length, '个', cameraOptions.value.map(c => ({ id: c.vidId, name: c.vidName, alg: c.vidAlgorithm })))
      if (cameraOptions.value.length === 0) {
        ElMessage.warning('没有可用的摄像头，请先在摄像头管理中配置算法')
      }
    } else {
      console.error('[druid] 摄像头列表返回code异常:', res.code, res.msg)
    }
  } catch (e) {
    console.error('[druid] 获取摄像头列表失败:', e)
    ElMessage.error('获取摄像头列表失败，请检查网络或登录状态')
  }
}

function onCameraChange() {
  stopPolling()
  shouldPolling.value = false
  clearResults()
  isAnalyzing.value = false
  analysisCompleted.value = false
  videoStatus.value = 'connecting'

  setTimeout(() => {
    shouldPolling.value = true
    startPolling()
  }, 500)
}

// ==================== 进度条颜色 ====================
const getLevelClass = (value) => {
  if (value >= 70) return 'high'
  if (value >= 40) return 'medium'
  return 'low'
}

// ==================== 生命周期 ====================
onMounted(async () => {
  await fetchCameras()
  startPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  shouldPolling.value = false
  if (videoImg.value) videoImg.value.src = ''
  const queryParam = selectedVidId.value
    ? `vid_id=${selectedVidId.value}`
    : 'source=local'
  fetch(`${baseURL}/video/reset?${queryParam}`).catch(() => {})
})

onUnmounted(() => {
  if (videoImg.value) videoImg.value.src = ''
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

/* 幸福指数卡片 */
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
</style>