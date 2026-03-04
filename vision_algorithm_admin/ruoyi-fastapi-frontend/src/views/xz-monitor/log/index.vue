<template>
  <div class="log-container">
    <div class="app-header">
      <h2>监控预警日志</h2>
    </div>
    <div class="app-container">
    <div class="alarm-list">
      <!-- 预警列表 -->
      <div class="alarm-list-content">
        <div 
          v-for="(alarm, index) in alarmList" 
          :key="alarm.id" 
          class="alarm-item"
          :class="{ 'active': selectedAlarm?.id === alarm.id }"
          @click="selectAlarm(alarm)"
        >
          <!-- 预警图片 -->
          <div class="alarm-image">
            <img 
              :src="'data:image/jpeg;base64,' + alarm.images[0]" 
              :alt="getAlgorithmName(alarm.eventType)"
              @error="handleImageError"
            />
          </div>
          
          <!-- 预警信息 -->
          <div class="alarm-info">
            <div class="event-type">
              <el-tag 
                type="warning"
                size="small"
                effect="dark"
              >
                {{ getAlgorithmName(alarm.eventType) }}
              </el-tag>
            </div>
            <div class="alarm-time">
              <el-icon><Clock /></el-icon>
              {{ formatTime(alarm.warningTime) }}
            </div>
            <div class="alarm-location" v-if="alarm.location">
              <el-icon><Location /></el-icon>
              {{ alarm.location }}
            </div>
            <div class="alarm-description">
              检测到{{ getAlgorithmName(alarm.eventType) }}
            </div>
          </div>
          
          <!-- 状态指示器 -->
          <div class="status-indicator" :class="alarm.status">
            <div class="status-dot"></div>
          </div>
        </div>
      </div>
      
      <!-- 分页组件 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          size="small"
          :page-sizes="[5, 10, 20, 50]"
          :total="totalAlarms"
          layout="prev, pager, next, sizes"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>
    
    <!-- 右侧详情面板 -->
    <div class="alarm-detail">
      <div v-if="selectedAlarm" class="detail-content">
        <div class="detail-left-panel">
          <div class="alarm-detail-image-container">
            <img 
              :src="'data:image/jpeg;base64,' + selectedAlarm.image" 
              :alt="getAlgorithmName(selectedAlarm.eventType)"
              @error="handleImageError"
              class="alarm-detail-image"
            />
          </div>
        </div>
        
        <!-- 右侧预警详细信息区域 -->
        <div class="detail-right-panel">
          <h3 class="detail-title">预警详细信息</h3>
          <el-descriptions :column="1" border size="large">
            <el-descriptions-item label="预警类型">
              <el-tag type="warning">
                {{ getAlgorithmName(selectedAlarm.eventType) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="发生时间">
              {{ formatTime(selectedAlarm.warningTime) }}
            </el-descriptions-item>
            <el-descriptions-item label="预警位置">
              {{ selectedAlarm.location }}
            </el-descriptions-item>
            <el-descriptions-item label="详细描述">
              检测到{{ getAlgorithmName(selectedAlarm.eventType) }}
            </el-descriptions-item>
            <el-descriptions-item label="追踪目标">
              {{ selectedAlarm.rawContent.track_id }}
            </el-descriptions-item>
            <el-descriptions-item label="消息推送">
              <div class="push-info-list">
                <div v-for="(item, index) in selectedAlarm.pushContent" :key="index" class="push-info-item">
                  <div class="push-header">
                    <el-tag size="small" :type="item.status === 'success' ? 'success' : 'danger'" effect="plain">
                      {{ item.status === 'success' ? '推送成功' : '推送失败' }}
                    </el-tag>
                    <span class="push-time">{{ formatTime(item.time) }}</span>
                  </div>
                  <div class="push-detail">
                    <span class="push-url" :title="item.url">URL: {{ item.url }}</span>
                    <span class="push-code" v-if="item.http_code">Code: {{ item.http_code }}</span>
                    <el-button link type="primary" size="small" @click="showResponse(item.response)">详情</el-button>
                  </div>
                </div>
              </div>
            </el-descriptions-item>
            
          </el-descriptions>
        </div>
      </div>
      <div v-else class="no-selection">
        <el-empty description="请选择预警项目查看详情" />
      </div>
    </div>
    </div>
    
    <!-- 响应详情弹窗 -->
    <el-dialog
      v-model="responseDialogVisible"
      title="推送响应详情"
      width="50%"
      append-to-body
    >
      <div class="response-content">
        <pre>{{ currentResponse }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, Location } from '@element-plus/icons-vue'
import { getAlarmList } from '@/api/xuzhou/alarm'
import { listAlgorithm } from '@/api/xuzhou/algorithm'
import defaultImage from '@/assets/images/profile.png'

// 响应式数据
const alarmList = ref([])
const selectedAlarm = ref(null)
const currentPage = ref(1)
const pageSize = ref(5)
const totalAlarms = ref(0)
const loading = ref(false)
const algorithmDict = ref({})
const responseDialogVisible = ref(false)
const currentResponse = ref('')

// 加载算法字典
const loadAlgorithmDict = async () => {
  try {
    const res = await listAlgorithm({ pageNum: 1, pageSize: 999 })
    if (res.rows) {
      const dict = {}
      res.rows.forEach(item => {
        const key = item.algSerial || item.alg_serial || item.serial || item.algCode || item.code
        const name = item.algName || item.alg_name || item.name
        if (key && name) {
          dict[key] = name
        }
      })
      algorithmDict.value = dict
    }
  } catch (error) {
    console.error('获取算法列表失败', error)
  }
}

const getAlgorithmName = (code) => {
  return algorithmDict.value[code] || code
}

// 解析推送信息
const getPushInfo = (alarm) => {
  if (!alarm?.rawContent?.push_request) return []
  let pushData = alarm.rawContent.push_request
  if (typeof pushData === 'string') {
    try {
      pushData = JSON.parse(pushData)
    } catch (e) {
      console.warn('解析推送信息失败', e)
      return []
    }
  }
  return Array.isArray(pushData) ? pushData : [pushData]
}

const hasPushInfo = (alarm) => {
  return alarm?.rawContent?.push_request && getPushInfo(alarm).length > 0
}

const showResponse = (response) => {
  currentResponse.value = response
  responseDialogVisible.value = true
}

// 加载预警数据
const loadAlarmData = async () => {
  loading.value = true
  try {
    const res = await getAlarmList({
      page_num: currentPage.value,
      page_size: pageSize.value
    })
    
    if (res.code === 200) {
      alarmList.value = res.rows.map(item => {
        let images = []
        try {
            // 兼容后端返回的下划线格式或驼峰格式
            const imgStr = item.alarm_image || item.alarmImage
            
            // 处理单个图片字符串的辅助函数
            const processImage = (img) => {
                if (img && !img.startsWith('http') && !img.startsWith('/') && !img.startsWith('data:image')) {
                    // 移除可能存在的换行符和空格
                    const cleanImg = img.replace(/[\r\n\s]+/g, '')
                    return `data:image/jpeg;base64,${cleanImg}`
                }
                return img
            }

            if (imgStr) {
                try {
                    // 尝试解析JSON数组
                    const parsed = JSON.parse(imgStr)
                    if (Array.isArray(parsed)) {
                        images = parsed.map(img => processImage(img))
                    } else if (typeof parsed === 'string') {
                        // 如果解析出来是字符串，也当做图片处理
                        images = [processImage(parsed)]
                    }
                } catch (jsonError) {
                    // 如果不是JSON格式，假设它就是原始字符串（可能是旧数据或纯base64）
                    console.warn('图片数据非JSON格式，尝试直接处理', jsonError)
                    images = [processImage(imgStr)]
                }
            }
        } catch (e) {
            console.error('解析图片流程异常', e)
        }
        
        let content = {}
        try {
            const contentStr = item.alarm_content || item.alarmContent
            if (contentStr) {
                content = JSON.parse(contentStr)
            }
        } catch (e) {
             console.error('解析内容失败', e)
        }

        let pushResult = {}
        try {
            const pushStr = item.push_result
            if (pushStr) {
                pushResult = JSON.parse(pushStr)
            }
        } catch (e) {
             console.error('解析内容失败', e)
        }

        const alarmCode = item.alarm_code || item.alarmCode
        const vidName = item.vid_name || item.vidName
        const alarmTime = item.alarm_time || item.alarmTime
        const alarmId = item.alarm_id || item.alarmId

        return {
          id: alarmId,
          eventType: alarmCode, 
          warningTime: alarmTime,
          location: vidName || '未知位置',
          description: `检测到${alarmCode}`, 
          image: images.length > 0 ? images[0] : '',
          images: images,
          status: 'unresolved', 
          rawContent: content,
          pushContent: pushResult
        }
      })
      totalAlarms.value = res.total
      
      // 默认选中第一个
      if (alarmList.value.length > 0 && !selectedAlarm.value) {
        selectedAlarm.value = alarmList.value[0]
      }
    }
  } catch (error) {
    console.error('获取预警列表失败', error)
    ElMessage.error('获取预警列表失败')
  } finally {
    loading.value = false
  }
}

// 获取事件类型对应的标签类型
const getEventTypeTagType = (eventType) => {
  const name = getAlgorithmName(eventType)
  const typeMap = {
    '火灾预警': 'danger',
    '入侵检测': 'warning',
    '设备故障': 'info',
    '温度异常': 'warning',
    '烟雾检测': 'danger',
    '人员离岗': 'warning',
    '未戴安全帽': 'danger',
    '抽烟检测': 'warning',
    '打电话检测': 'warning'
  }
  return typeMap[name] || 'info'
}

// 处理图片加载错误
const handleImageError = (event) => {
  event.target.src = defaultImage
}

// 格式化时间
const formatTime = (time) => {
  return new Date(time).toLocaleString('zh-CN')
}

// 选择预警项目
const selectAlarm = (alarm) => {
  selectedAlarm.value = alarm
}

// 分页处理
const handleSizeChange = (val) => {
  pageSize.value = val
  loadAlarmData()
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  loadAlarmData()
}

// 组件挂载时加载数据
onMounted(() => {
  loadAlgorithmDict()
  loadAlarmData()
})
</script>

<style scoped>
.app-header {
  padding: 20px;
  padding-bottom: 0;
  height: 60px;
  width: 100%;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.app-header h2 {
  margin: 0;
  color: #303133;
  font-size: 20px;
  font-weight: 600;
}

.app-container {
  padding: 0;
  display: flex;
  height: calc(100vh - 150px);
  background-color: #f5f7fa;
}

.alarm-list {
  height: 100%;
  width: 30%;
  background-color: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.alarm-list-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.alarm-item {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  margin-bottom: 12px;
  background-color: #fafafa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
}

.alarm-item:hover {
  background-color: #f0f2f5;
  border-color: #409eff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
}

.alarm-item.active {
  background-color: #ecf5ff;
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
}

.alarm-image {
  width: 60px;
  height: 60px;
  margin-right: 12px;
  border-radius: 6px;
  overflow: hidden;
  background-color: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.alarm-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.alarm-info {
  flex: 1;
  min-width: 0;
}

.event-type {
  margin-bottom: 8px;
}

.alarm-time {
  display: flex;
  align-items: center;
  color: #606266;
  font-size: 13px;
  margin-bottom: 4px;
}

.alarm-location {
  display: flex;
  align-items: center;
  color: #909399;
  font-size: 12px;
  margin-bottom: 4px;
}

.alarm-description {
  color: #606266;
  font-size: 13px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.status-indicator {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #f56c6c;
}

.status-indicator.resolved {
  background-color: #67c23a;
}

.status-dot {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.pagination-container {
  padding: 16px;
  border-top: 1px solid #e4e7ed;
  background-color: #fff;
}

.alarm-detail {
  height: 100%;
  width: 70%;
  overflow-y: auto;
  background-color: #fff;
}

.detail-content {
  display: flex;
  height: 100%;
  gap: 20px;
  padding: 20px;
}

.detail-left-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-right-panel {
    width: 30%;
    background-color: #fff;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    padding: 0 10px;
    overflow-y: auto;
  }

  .detail-title {
    margin: 0 0 16px 0;
    color: #303133;
    font-size: 16px;
    font-weight: 600;
    padding-left: 8px;
    border-left: 4px solid #409eff;
  }

.alarm-detail-image-container {
  width: 100%;
  height: 100%;
  background-color: #fafafa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow: hidden;
}

.alarm-detail-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.event-timeline-placeholder {
    text-align: center;
    color: #909399;
  }

.no-selection {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

:deep(.el-icon) {
  margin-right: 4px;
}

:deep(.el-descriptions) {
  background-color: transparent;
}

:deep(.el-descriptions__label) {
  background-color: #f5f7fa !important;
  font-weight: 600;
  color: #303133;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .alarm-list {
    width: 35%;
  }
  .alarm-detail {
    width: 65%;
  }
  .detail-content {
    flex-direction: column;
  }
  .detail-left-panel,
  .detail-right-panel {
    flex: none;
  }
  .detail-right-panel {
    min-height: 200px;
  }
}

@media (max-width: 768px) {
  .app-container {
    flex-direction: column;
  }
  .alarm-list {
    width: 100%;
    height: 50%;
    border-right: none;
    border-bottom: 1px solid #e4e7ed;
  }
  .alarm-detail {
    width: 100%;
    height: 50%;
  }
  .detail-content {
    flex-direction: column;
    padding: 16px;
  }
  .alarm-detail-image-container {
    height: 300px;
  }
}

.push-info-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.push-info-item {
  background-color: #fafafa;
  border-radius: 4px;
  padding: 8px;
  border: 1px solid #ebeef5;
}

.push-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.push-time {
  font-size: 12px;
  color: #909399;
}

.push-detail {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  font-size: 12px;
}

.push-url {
  color: #606266;
  word-break: break-all;
}

.push-code {
  color: #909399;
}

.response-content {
  max-height: 500px;
  overflow-y: auto;
  background-color: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
}

.response-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: monospace;
}
</style>