
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
            <div class="panel-header">
              <h3>实时心理生理参数</h3>
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
  
            <div class="param-list">
              <div v-for="param in paramConfig" :key="param.key" class="param-item">
                <div class="param-label">
                  <span class="key">{{ param.key }}</span>
                  <span class="name">{{ param.name }}</span>
                </div>
                <div class="progress-wrapper">
                  <!-- 进度条容器 -->
                  <div class="progress-bar">
                    <!-- 始终显示的浅灰占位条（0值时可见） -->
                    <div class="progress-fill placeholder"></div>
                    
                    <!-- 真实彩色进度条 -->
                    <div
                      class="progress-fill real-fill"
                      :style="{ width: `${Math.max(5, Math.min(results[param.key] || 0, 100))}%` }"
                      :class="getLevelClass(results[param.key] || 0)"
                    ></div>
                  </div>
                  
                  <!-- 数值显示（0时显示“待检测”） -->
                  <span class="value">
                    {{ isAnalyzing 
                    ? (results[param.key] || 0).toFixed(1) 
                    : '待检测' 
                      }}
                  </span>
                </div>
              </div>
            </div>
  
            <div class="tips">
              <p><strong>参数含义：</strong></p>
              <ul>
                <li><span class="key-tip">e1</span> 攻击性 — 微振动强度与波动</li>
                <li><span class="key-tip">e2</span> 压力 — 左右脸振动不对称</li>
                <li><span class="key-tip">e3</span> 焦虑 — 高频振动能量占比</li>
                <li><span class="key-tip">e4</span> 可疑 — 综合异常程度</li>
                <li><span class="key-tip">e5</span> 平衡 — 振动稳定性（越高越好）</li>
                <li><span class="key-tip">e6</span> 魅力 — 左右协调性</li>
                <li><span class="key-tip">e7</span> 能量 — 整体振动能量水平</li>
                <li><span class="key-tip">e8</span> 自我调节 — 参数波动稳定性</li>
                <li><span class="key-tip">e9</span> 抑制 — 攻击性与平衡的协调</li>
                <li><span class="key-tip">e10</span> 神经质 — 压力与焦虑平均</li>
                <li><span class="key-tip">e11</span> 忧郁 — 与能量水平的负相关</li>
                <li><span class="key-tip">e12</span> 幸福 — 信息效率与能量消耗比</li>
                <li><span class="key-tip">e13</span> 外向性 — 信息效率与能量相关性</li>
                <li><span class="key-tip">e14</span> 稳定性 — 频率直方图与正态分布相似度</li>
              </ul>
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
  const videoStatus = ref('connecting')
  const statusText = ref('连接中...')
  const showConnectionTip = ref(false)
  const connectionTipText = ref('')
  const resetLoading = ref(false)
  const reconnectAttempts = ref(0)
  const MAX_RECONNECT_ATTEMPTS = 3
  const shouldPolling = ref(true)
  const isAnalyzing = ref(false)
  let pollTimer = null
  
  const videoImg = ref(null)
  
  // ==================== 参数数据 ====================
  const results = ref({
    e1: 0, e2: 0, e3: 0, e4: 0, e5: 0,
    e6: 0, e7: 0, e8: 0, e9: 0, e10: 0,
    e11: 0, e12: 0, e13: 0, e14: 0
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
  
  // ==================== 视频流URL ====================
  const videoStreamUrl = computed(() => {
    const timestamp = new Date().getTime()
    return `${baseURL}/video/feed/analysis?source=${cameraSource.value}&t=${timestamp}`
  })
  
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
    isAnalyzing.value = false
  }
  
  const fetchResults = async () => {
    if (!shouldPolling.value) return
  
    try {
      const res = await fetch(`${baseURL}/video/results?source=${cameraSource.value}`)
      const data = await res.json()
      console.log('results:', data.results)
      
      if (data.analyzing) {
        isAnalyzing.value = true
        videoStatus.value = 'online'
  
        Object.keys(results.value).forEach(key => {
          results.value[key] = data.results?.[key] ?? 0
        })
      } else {
        isAnalyzing.value = false
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

/* 主内容区 - 左右并排布局 */
.main-content {
  display: flex;
  gap: 30px;
  height: calc(100vh - 120px);
}

/* 左侧视频区域 */
.video-section {
  flex: 1.2;
  min-width: 0; /* 防止flex元素溢出 */
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

.status-corner {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  z-index: 10;
}

.status-text {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: bold;
  color: #fff;
}

.status-corner.online .status-text { background: rgba(46, 204, 113, 0.9); }
.status-corner.error .status-text { background: rgba(231, 76, 60, 0.9); }
.status-corner.connecting .status-text { background: rgba(52, 152, 219, 0.9); }

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

/* 右侧参数区域 */
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
  margin-bottom: 20px;
  gap: 16px;
  min-height: 40px;
}

.param-label {
  width: 100px;
  flex-shrink: 0;
}

.param-label .key {
  font-weight: bold;
  color: #3498db;
  font-size: 16px;
  display: block;
}

.param-label .name {
  color: #666;
  font-size: 13px;
  display: block;
  margin-top: 2px;
}

  .progress-wrapper {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .progress-bar {
    position: relative;           /* 关键：让两个条层叠 */
    flex: 1;
    height: 26px;
    background: #d5dbdb;
    border-radius: 13px;
    overflow: hidden;
    min-width: 0;
    border: 2px solid #bdc3c7;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
  }
  
  /* 浅灰占位条（0值时可见） */
  .progress-fill.placeholder {
    position: absolute;
    left: 0;
    top: 0;
    width: 100% !important;
    height: 100%;
    background: #e5e7eb;
    border-radius: 13px;
    z-index: 1;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.08);
  }
  
  /* 真实彩色进度条 */
  .progress-fill.real-fill {
    position: absolute;
    left: 0;
    top: 0;
    z-index: 2;
    height: 100%;
    border-radius: 13px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    min-width: 5px;
    box-shadow: 0 0 8px rgba(0,0,0,0.35);
  }
  
  /* 颜色样式（应用到 real-fill） */
  .real-fill.low { 
    background: linear-gradient(90deg, #27ae60, #2ecc71);
    background-image: linear-gradient(45deg, rgba(255,255,255,0.15) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.15) 50%, rgba(255,255,255,0.15) 75%, transparent 75%, transparent);
    background-size: 20px 20px;
  }
  
  .real-fill.medium { 
    background: linear-gradient(90deg, #e67e22, #f39c12); 
  }
  
  .real-fill.high { 
    background: linear-gradient(90deg, #e74c3c, #c0392b); 
  }
  
  .value {
    width: 60px;
    text-align: right;
    font-weight: bold;
    font-size: 16px;
    color: #2c3e50;
    flex-shrink: 0;
  }
  
  /* 其余原有样式（响应式、滚动条、tips 等）全部保留 */
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

  /* 响应式 */
  @media (max-width: 1200px) { .main-content { flex-direction: column; height: auto; } .params-section { min-width: 100%; max-width: 100%; } }
  @media (max-width: 768px) {
    .header { flex-direction: column; align-items: flex-start; gap: 16px; }
    .param-item { flex-direction: column; align-items: flex-start; gap: 8px; }
    .progress-wrapper { width: 100%; }
    .param-label { width: 100%; }
  }
  </style>