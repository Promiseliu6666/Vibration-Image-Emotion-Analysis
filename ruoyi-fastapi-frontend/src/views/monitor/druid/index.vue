<template>
  <div class="vibra-monitor">
    <!-- 标题与控制栏 -->
    <div class="header">
      <h2>振动图像心理生理实时监测系统</h2>
      <div class="controls">
        <div class="control-group">
          <label>摄像头：</label>
          <el-select v-model="cameraSource" size="small" style="width: 160px">
            <el-option label="本地摄像头" value="local" />
            <el-option label="海康RTSP摄像头" value="rtsp" />
          </el-select>
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
            :key="cameraSource"
            alt="实时视频流"
            class="video-stream"
            @load="onVideoLoad"
            @error="onVideoError"
          />
          <div class="status-overlay">
            <div class="status-corner" :class="videoStatus">
              <span class="status-text">{{ statusText }}</span>
            </div>
            <!-- 错误提示遮罩，当摄像头完全不可用时显示 -->
            <div v-if="videoStatus === 'error' && showConnectionTip" class="error-tip">
              <div class="error-icon">⚠️</div>
              <div class="error-message">{{ connectionTipText }}</div>
              <div class="error-hint">💡 请在上方切换其他摄像头源重试</div>
            </div>
            <!-- 连接失败自动重连提示 -->
            <div v-if="videoStatus === 'error' && !showConnectionTip" class="reconnect-tip">
              视频流中断，浏览器正在自动重连...
            </div>
            <!-- 等待人脸提示 -->
            <div v-if="videoStatus === 'online' && !isAnalyzing" class="waiting-tip">
              等待检测到稳定人脸...<br />
              请正对摄像头，保持头部静止几秒钟
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：参数面板（支持切换） -->
      <div class="params-section">
        <div class="params-panel">
          <!-- 🔥 切换按钮：默认显示"详情"，切换后显示"收起" -->
          <div class="switch-btn-container">
            <el-button
              type="primary"
              size="small"
              @click="toggleParamView"
            >
              {{ isShowE1E10 ? '收起' : '详情' }}
            </el-button>
          </div>

          <!-- 🔥 视图1：默认显示 - 幸福卡片+幸福参数 -->
          <div v-if="!isShowE1E10 && isAnalyzing && wellbeingResults.happiness_index > 0">
            <!-- 幸福指数卡片 -->
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

            <!-- 幸福指数说明（紧贴卡片） -->
            <div class="wellbeing-tips">
              <p><strong>幸福指数说明：</strong></p>
              <ul>
                <li><strong>幸福指数</strong>：综合评估当前心理状态 (1-100分)</li>
                <li><strong>幸福等级</strong>：根据指数划分的心理状态等级</li>
                <li><strong>安全风险</strong>：评估潜在的安全风险程度</li>
                <li><strong>检测规则</strong>：检测10秒后数值固定，不再变化</li>
              </ul>
            </div>
          </div>

          <!-- 视图1无数据时显示 -->
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
                description="正在采集数据计算幸福指数，请稍候..."
                :closable="false"
                show-icon
              />
            </div>
          </div>

          <!-- 🔥 视图2：切换后显示 - e1-e14及参数含义 -->
          <div v-if="isShowE1E10">
            <div class="panel-header">
              <h3>基础生理参数 (e1-e14)</h3>
              <el-tag type="info" size="small">
                详细参数视图
              </el-tag>
            </div>
            <!-- e1-e14 参数显示区域 -->
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

            <!-- 参数含义（两列排版，节省空间） -->
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
import { ref, computed, watch, onMounted, onBeforeUnmount, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'

// ==================== 状态管理 ====================
const cameraSource = ref('local')
const videoStatus = ref('connecting')  // connecting, online, waiting, error
const statusText = ref('连接中...')
const showConnectionTip = ref(false)
const connectionTipText = ref('')
const resetLoading = ref(false)
const reconnectAttempts = ref(0)
const MAX_RECONNECT_ATTEMPTS = 3
const shouldPolling = ref(true)
const isAnalyzing = ref(false)
let pollTimer = null

// 🔥 新增：切换状态（默认false：显示幸福卡片；true：显示e1-e14）
const isShowE1E10 = ref(false)

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

// 新增：参数含义列表（两列排版用）
const paramMeaningList = ref([
  { key: 'e1', meaning: '攻击性-微振动强度与波动' },
  { key: 'e2', meaning: '压力-左右脸振动不对称' },
  { key: 'e3', meaning: '焦虑-高频振动能量占比' },
  { key: 'e4', meaning: '可疑-综合异常程度' },
  { key: 'e5', meaning: '平衡-振动稳定性（越高越好）' },
  { key: 'e6', meaning: '魅力-左右协调性' },
  { key: 'e7', meaning: '能量-整体振动能量水平' },
  { key: 'e8', meaning: '自我调节-参数波动稳定性' },
  { key: 'e9', meaning: '抑制-攻击性与平衡的协调' },
  { key: 'e10', meaning: '神经质-压力与焦虑平均' },
  { key: 'e11', meaning: '忧郁 — 与能量水平的负相关' },
  { key: 'e12', meaning: '幸福 — 信息效率与能量消耗比' },
  { key: 'e13', meaning: '外向性 — 信息效率与能量相关性' },
  { key: 'e14', meaning: '稳定性 — 频率直方图与正态分布相似度' }
])

// ==================== 视频流URL ====================
const videoStreamUrl = computed(() => {
  const timestamp = new Date().getTime()
  return `${baseURL}/video/feed/analysis?source=${cameraSource.value}&t=${timestamp}`
})

// ==================== 幸福指数计算函数 ====================
/**
 * 根据幸福指数计算幸福等级
 */
const calculateHappinessLevel = (index) => {
  if (index >= 80) return '幸福达标'
  if (index >= 60) return '幸福待提升'
  return '幸福预警'
}

/**
 * 根据幸福指数计算安全风险等级
 */
const calculateSafetyRiskLevel = (index) => {
  if (index >= 70) return '低风险'
  if (index >= 40) return '中风险'
  return '高风险'
}

/**
 * 获取幸福指数进度条颜色类
 */
const getHappinessLevelClass = (value) => {
  if (value >= 80) return 'happiness-high'
  if (value >= 60) return 'happiness-medium'
  if (value >= 40) return 'happiness-low'
  return 'happiness-very-low'
}

/**
 * 获取安全风险等级颜色类
 */
const getSafetyLevelClass = (level) => {
  switch(level) {
    case '低风险':
      return 'safety-low'
    case '中风险':
      return 'safety-medium'
    case '高风险':
      return 'safety-high'
    default:
      return 'safety-unknown'
  }
}

/**
 * 获取幸福等级标签类型
 */
const getHappinessTagType = (level) => {
  switch(level) {
    case '幸福达标':
      return 'success'
    case '幸福待提升':
      return 'warning'
    case '幸福预警':
      return 'danger'
    default:
      return 'info'
  }
}

/**
 * 获取安全风险标签类型
 */
const getSafetyTagType = (level) => {
  switch(level) {
    case '低风险':
      return 'success'
    case '中风险':
      return 'warning'
    case '高风险':
      return 'danger'
    default:
      return 'info'
  }
}

/**
 * 🔥 新增：切换视图函数
 */
const toggleParamView = () => {
  isShowE1E10.value = !isShowE1E10.value
  ElMessage.success(`已切换至${isShowE1E10.value ? '详细参数' : '幸福指数'}视图`)
}

// ==================== 视频流事件处理 ====================
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
    connectionTipText.value = cameraSource.value === 'rtsp'
      ? '❌ 海康RTSP摄像头连接失败 (500)\n请检查设备电源、IP或RTSP地址'
      : '❌ 本地摄像头无法打开 (500)\n请确认设备未被其他程序占用'
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

  isAnalyzing.value = false
  // 重置视图为默认（幸福卡片）
  isShowE1E10.value = false
}

const fetchResults = async () => {
  if (!shouldPolling.value) return

  try {
    const res = await fetch(`${baseURL}/video/results?source=${cameraSource.value}`)
    const data = await res.json()

    if (data.analyzing) {
      isAnalyzing.value = true
      videoStatus.value = 'online'

      // 更新所有参数（平滑过渡）
      Object.keys(results.value).forEach(key => {
        results.value[key] = results.value[key] * 0.7 + (data.results?.[key] ?? 0) * 0.3
      })

      // 🔥 幸福指数来自 e12，并进行平滑更新
      const currentE12 = data.results?.e12 ?? 0
      wellbeingResults.value.happiness_index = 
        wellbeingResults.value.happiness_index * 0.7 + currentE12 * 0.3

      // 根据幸福指数动态计算等级
      wellbeingResults.value.happiness_level = calculateHappinessLevel(wellbeingResults.value.happiness_index)
      wellbeingResults.value.safety_risk_level = calculateSafetyRiskLevel(wellbeingResults.value.happiness_index)

    } else {
      isAnalyzing.value = false
      if (!data.analyzing) {
        wellbeingResults.value = {
          happiness_index: 0,
          happiness_level: '',
          safety_risk_level: ''
        }
      }
    }
  } catch (err) {
    console.error('轮询失败', err)
  }
}

// ==================== 轮询管理 ====================
const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(fetchResults, 800)
  fetchResults()
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
    const res = await fetch(`${baseURL}/video/reset?source=${cameraSource.value}`)
    if (res.ok) {
      clearResults()
      videoStatus.value = 'waiting'
      statusText.value = '已刷新，等待人脸检测...'
      ElMessage.success('已刷新！摄像头将重新检测人脸')
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

// ==================== 摄像头切换 ====================
watch(cameraSource, async (newVal, oldVal) => {
  if (oldVal && oldVal !== newVal) {
    stopPolling()
    shouldPolling.value = false
    clearResults()
    isAnalyzing.value = false
    videoStatus.value = 'connecting'

    try {
      await fetch(`${baseURL}/video/reset?source=${oldVal}`)
    } catch (e) {
      console.warn('重置旧摄像头源失败', e)
    }

    await new Promise(resolve => setTimeout(resolve, 500))
  }

  shouldPolling.value = true
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
  startPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  shouldPolling.value = false
  if (videoImg.value) videoImg.value.src = ''
  fetch(`${baseURL}/video/reset?source=${cameraSource.value}`).catch(() => {})
})

onUnmounted(() => {
  if (videoImg.value) videoImg.value.src = ''
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
/* === 幸福指数卡片样式 === */
.wellbeing-card {
  background: rgba(245, 247, 250, 0.78);
  backdrop-filter: blur(10px);          /* 毛玻璃效果，现代感强 */
  -webkit-backdrop-filter: blur(10px);  /* Safari 支持 */
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(200, 220, 255, 0.5);
  color: #1e293b;                       /* 深灰偏蓝，更高级 */
}

.wellbeing-header h3 {
  color: #1e293b;
  font-size: 1.25em;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.index-value {
  font-size: 3.4em;
  font-weight: 800;
  color: #2563eb;                       /* 更沉稳的蓝 */
  text-shadow: 0 2px 8px rgba(37, 99, 235, 0.18);
}

.index-progress .progress-bar {
  height: 14px;                         /* 更细更优雅 */
  background: rgba(226, 232, 240, 0.9);
  border: 1px solid rgba(203, 213, 225, 0.6);
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.06);
}

.index-progress .progress-fill {
  box-shadow: 0 0 12px rgba(0,0,0,0.15);
  transition: width 1s ease-out;
}

/* 幸福指数颜色 - 更柔和渐变 */
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

/* === 幸福指数说明 === */
.wellbeing-tips {
  margin-top: 0;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 4px solid #3498db;
}

.wellbeing-tips ul {
  padding-left: 20px;
  margin: 10px 0;
}

.wellbeing-tips li {
  margin-bottom: 6px;
  color: #555;
  line-height: 1.5;
}

/* === 🔥 切换按钮样式 === */
.switch-btn-container {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

/* === 🔥 参数含义两列排版（节省空间）=== */
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

/* === 原有样式 === */
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

.reconnect-tip {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 20px 40px;
  border-radius: 16px;
  font-size: 1.2em;
}

.waiting-tip {
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
  line-height: 1.6;
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
  display: grid;
  grid-template-columns: 110px 1fr 70px;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.5);
}

.param-label {
  width: auto;
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
  gap: 12px;
}

.progress-bar {
  height: 18px;
  background: #e2e8f0;
  border-radius: 999px;               /* 极致圆角 */
  overflow: hidden;
  border: none;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.08);
  position: relative;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.9s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 2px 10px rgba(0,0,0,0.15);
  min-width: 6%;
  background-size: 200% 200%;
  animation: gradientFlow 8s ease infinite;
}

/* 颜色语义更柔和 + 流动感渐变 */
.progress-fill.low {
  background: linear-gradient(90deg, #86efac, #4ade80, #22c55e);
  background-size: 200% 200%;
}
.progress-fill.medium {
  background: linear-gradient(90deg, #fdba74, #fb923c, #f97316);
  background-size: 200% 200%;
}
.progress-fill.high {
  background: linear-gradient(90deg, #fca5a5, #f87171, #ef4444);
  background-size: 200% 200%;
}

.value {
  font-size: 1.18rem;
  font-weight: 700;
  color: #1e293b;
  text-shadow: 0 1px 3px rgba(0,0,0,0.1);
  min-width: 60px;
  text-align: right;
}

/* 微动画 - 渐变流动（可选，增加高级感） */
@keyframes gradientFlow {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
.no-analysis-tip {
  margin-bottom: 20px;
  padding: 0 10px;
}

.tips {
  flex-shrink: 0;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px dashed #ddd;
  font-size: 13px;
  color: #7f8c8d;
  line-height: 1.7;
}

.tips p {
  margin: 0;
}

.tips ul {
  padding-left: 20px;
  margin: 10px 0;
}

.tips li {
  margin-bottom: 6px;
  line-height: 1.6;
}

.params-panel::-webkit-scrollbar {
  width: 8px;
}

.params-panel::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.params-panel::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.params-panel::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 响应式适配 */
@media (max-width: 1200px) {
  .main-content {
    flex-direction: column;
    height: auto;
  }
  .params-section {
    min-width: 100%;
    max-width: 100%;
  }
  .params-panel {
    height: auto;
    max-height: 600px;
  }
  .level-indicators {
    flex-direction: column;
    gap: 12px;
  }
  .param-meaning-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  .controls {
    width: 100%;
    justify-content: space-between;
  }
  .param-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .progress-wrapper {
    width: 100%;
  }
  .param-label {
    width: 100%;
  }
  .wellbeing-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .wellbeing-status {
    align-self: flex-start;
  }
}
</style>