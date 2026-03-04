<template>
  <div class="vibra-monitor">
    <!-- 标题与控制栏 -->
    <div class="header">
      <h2>振动图像心理生理实时监测系统</h2>
      <div class="controls">
        <!-- 摄像头源选择 -->
        <div class="control-group">
          <label>摄像头：</label>
          <el-select v-model="cameraSource" size="small" style="width: 160px">
            <el-option label="本地摄像头" value="local" />
            <el-option label="海康RTSP摄像头" value="rtsp" />
          </el-select>
        </div>

        <!-- 刷新按钮 -->
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

    <!-- 主内容区 - 左右并排布局 -->
    <div class="main-content">
      <!-- 左侧：视频流 -->
      <div class="video-section">
        <div class="video-wrapper">
          <img
            :src="videoStreamUrl"
            alt="实时视频流"
            class="video-stream"
            @load="onVideoLoad"
            @error="onVideoError"
          />

          <!-- 状态标签 -->
          <div class="status-corner" :class="videoStatus">
            <span class="status-text">{{ statusText }}</span>
          </div>

          <!-- 重连提示 -->
          <div v-if="videoStatus === 'error'" class="reconnect-tip">
            视频流中断，正在自动重连...
          </div>
        </div>
      </div>

      <!-- 右侧：参数面板 - 始终显示 -->
      <div class="params-section">
        <div class="params-panel">
          <div class="panel-header">
            <h3>实时心理生理参数</h3>
            <el-tag type="info" size="small">自动更新中</el-tag>
          </div>

          <div class="param-list">
            <div v-for="param in paramConfig" :key="param.key" class="param-item">
              <div class="param-label">
                <span class="key">{{ param.key }}</span>
                <span class="name">{{ param.name }}</span>
              </div>
              <div class="progress-wrapper">
                <div class="progress-bar">
                  <div
                    class="progress-fill"
                    :style="{ width: `${Math.min(results[param.key], 100)}%` }"
                    :class="getLevelClass(results[param.key])"
                  ></div>
                </div>
                <span class="value">{{ results[param.key].toFixed(1) }}</span>
              </div>
            </div>
          </div>

          <!-- 参数解释 -->
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
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'

const cameraSource = ref('local')
const videoStatus = ref('connecting')
const statusText = ref('连接中...')
const resetLoading = ref(false)
let pollTimer = null

const results = ref({
  e1: 0, e2: 0, e3: 0, e4: 0, e5: 0,
  e6: 0, e7: 0, e8: 0, e9: 0, e10: 0
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
]

const videoStreamUrl = computed(() => {
  // 添加时间戳防止缓存
  const timestamp = new Date().getTime()
  return `${baseURL}/video/feed/analysis?source=${cameraSource.value}&t=${timestamp}`
})

const onVideoLoad = () => {
  videoStatus.value = 'online'
  statusText.value = '在线 · 分析自动进行中'
}

const onVideoError = () => {
  videoStatus.value = 'error'
  statusText.value = '连接断开'
  setTimeout(() => {
    if (videoStatus.value === 'error') {
      videoStatus.value = 'connecting'
      statusText.value = '重新连接中...'
    }
  }, 3000)
}

const fetchResults = async () => {
  try {
    const res = await fetch(`${baseURL}/video/results`)
    if (res.ok) {
      const data = await res.json()
      Object.keys(results.value).forEach(key => {
        if (data[key] !== undefined) {
          // 平滑过渡
          results.value[key] = results.value[key] * 0.7 + data[key] * 0.3
        }
      })
    }
  } catch (err) {
    console.error('获取参数失败', err)
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(fetchResults, 800)
  fetchResults()
}

const stopPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

const resetParams = async () => {
  resetLoading.value = true
  try {
    const res = await fetch(
      `${baseURL}/video/reset?source=${cameraSource.value}`
    )
    if (res.ok) {
      // 本地数据重置
      Object.keys(results.value).forEach(key => {
        results.value[key] = 0
      })
      
      // 刷新视频流（强制重新加载）
      const videoElement = document.querySelector('.video-stream')
      if (videoElement) {
        videoElement.src = videoStreamUrl.value
        videoStatus.value = 'connecting'
        statusText.value = '重置中...'
      }
      
      ElMessage.success('已刷新！摄像头将重新检测人脸')
      console.log('[刷新] 分析状态已重置，框和参数已清空')
    } else {
      ElMessage.error('刷新失败')
    }
  } catch (err) {
    ElMessage.error('请求失败')
    console.error('刷新失败', err)
  } finally {
    resetLoading.value = false
  }
}

watch(cameraSource, () => {
  videoStatus.value = 'connecting'
  statusText.value = '切换摄像头...'
  // 切换摄像头时重置参数
  Object.keys(results.value).forEach(key => {
    results.value[key] = 0
  })
})

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})

const getLevelClass = (value) => {
  if (value >= 70) return 'high'
  if (value >= 40) return 'medium'
  return 'low'
}
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
  flex: 1;
  height: 26px;
  background: #ecf0f1;
  border-radius: 13px;
  overflow: hidden;
  min-width: 0;
}

.progress-fill {
  height: 100%;
  border-radius: 13px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.progress-fill.low { background: linear-gradient(90deg, #27ae60, #2ecc71); }
.progress-fill.medium { background: linear-gradient(90deg, #e67e22, #f39c12); }
.progress-fill.high { background: linear-gradient(90deg, #e74c3c, #c0392b); }

.value {
  width: 60px;
  text-align: right;
  font-weight: bold;
  font-size: 16px;
  color: #2c3e50;
  flex-shrink: 0;
}

/* 参数解释区域 */
.tips {
  flex-shrink: 0;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px dashed #ddd;
  font-size: 13px;
  color: #7f8c8d;
  line-height: 1.7;
}

.tips ul {
  padding-left: 0;
  margin: 10px 0;
  list-style: none;
}

.tips li {
  margin-bottom: 8px;
  display: flex;
  align-items: flex-start;
}

.key-tip {
  display: inline-block;
  width: 30px;
  font-weight: bold;
  color: #3498db;
  margin-right: 8px;
  flex-shrink: 0;
}

/* 滚动条样式 */
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

/* 响应式设计 */
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
    max-height: 500px;
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
}
</style>