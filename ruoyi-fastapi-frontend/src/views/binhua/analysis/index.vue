<template>
  <div class="analysis-container">
    <el-card class="search-card">
      <el-form :inline="true" :model="queryParams" label-width="100px">
        <el-form-item label="人员ID">
          <el-input-number
            v-model="queryParams.personId"
            :min="0"
            placeholder="请输入人员ID"
            clearable
            style="width: 180px"
          />
        </el-form-item>

        <el-form-item label="人名">
          <el-input
            v-model="queryParams.personName"
            placeholder="输入人名（支持模糊）"
            clearable
            style="width: 180px"
          />
        </el-form-item>

        <el-form-item label="视频来源">
          <el-input
            v-model="queryParams.source"
            placeholder="输入视频来源（支持模糊）"
            clearable
            style="width: 180px"
          />
        </el-form-item>

        <el-form-item label="创建时间">
          <el-date-picker
            v-model="queryParams.startTime"
            type="date"
            placeholder="开始日期"
            value-format="YYYY-MM-DD"
            style="width: 160px"
          />
          <span style="margin: 0 8px; color: #909399;">至</span>
          <el-date-picker
            v-model="queryParams.endTime"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 160px"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 双图表布局 -->
    <div class="chart-group">
      <el-card class="chart-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>幸福等级分布（当前筛选条件）</span>
          </div>
        </template>
        <div ref="happinessChart" class="chart-container" />
      </el-card>

      <el-card class="chart-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>幸福指数趋势（按日期）</span>
          </div>
        </template>
        <div ref="trendChart" class="chart-container" />
      </el-card>
    </div>

    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span>分析记录列表</span>
          <div>
            <el-button type="primary" @click="handleAdd">新增记录</el-button>
            <el-button
              type="danger"
              :disabled="!multipleSelection.length"
              @click="handleBatchDelete"
            >
              批量删除
            </el-button>
            <el-button
              type="success"
              :loading="exportLoading"
              :disabled="loading || total === 0"
              @click="openExportDialog"
            >
              导出Excel
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="analysisList"
        @selection-change="handleSelectionChange"
        border
        style="width: 100%"
        highlight-current-row
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="source" label="视频来源" min-width="140" show-overflow-tooltip />
        <el-table-column prop="personName" label="人名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="personId" label="人员ID" width="100" align="center" />
        <el-table-column prop="happinessIndex" label="幸福指数" width="120" sortable align="center" />
        <el-table-column prop="happinessLevel" label="幸福等级" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getLevelTagType(row.happinessLevel)">
              {{ row.happinessLevel || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="safetyRisk" label="安全风险" min-width="160" show-overflow-tooltip />
        <el-table-column prop="createTime" label="创建时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDate(row.createTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">查看</el-button>
            <el-button type="warning" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <pagination
        v-show="total > 0"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getList"
        class="pagination-center"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      :title="dialogTitle"
      v-model="dialogVisible"
      width="620px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="analysisFormRef" :model="formData" :rules="rules" label-width="110px">
        <el-form-item label="视频来源" prop="source">
          <el-input v-model="formData.source" placeholder="请输入视频来源" />
        </el-form-item>
        <el-form-item label="人名" prop="personName">
          <el-input v-model="formData.personName" placeholder="请输入人名" />
        </el-form-item>
        <el-form-item label="人员ID" prop="personId">
          <el-input-number v-model="formData.personId" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="幸福指数" prop="happinessIndex">
          <el-input-number
            v-model="formData.happinessIndex"
            :precision="2"
            :step="0.01"
            :min="0"
            :max="100"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="幸福等级" prop="happinessLevel">
          <el-select v-model="formData.happinessLevel" placeholder="请选择幸福等级" style="width: 100%">
            <el-option label="高" value="高" />
            <el-option label="中" value="中" />
            <el-option label="低" value="低" />
          </el-select>
        </el-form-item>
        <el-form-item label="安全风险">
          <el-input
            v-model="formData.safetyRisk"
            type="textarea"
            :rows="3"
            placeholder="描述安全风险（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer 
      v-model="drawerVisible" 
      title="分析记录详情" 
      size="72%" 
      direction="rtl"
    >
      <div class="detail-wrapper">
        <!-- 基础信息 -->
        <el-descriptions :column="2" border size="small" class="mb-4">
          <template #header>
            <span class="section-title">基础信息</span>
          </template>
          <el-descriptions-item label="ID">{{ detailData.id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="视频来源">{{ detailData.source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="人名">{{ detailData.personName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="人员ID">{{ detailData.personId || '-' }}</el-descriptions-item>
          <el-descriptions-item label="幸福指数">
            <span style="color: #67C23A; font-weight: 500;">{{ detailData.happinessIndex || '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="幸福等级">
            <el-tag size="small" :type="getLevelTagType(detailData.happinessLevel)">
              {{ detailData.happinessLevel || '-' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="安全风险">
            <el-tag size="small" type="warning">{{ detailData.safetyRisk || '-' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(detailData.createTime) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 视频区域 -->
        <el-card shadow="hover" class="video-card mb-4">
          <template #header>
            <div class="video-header">
              <span class="section-title">分析视频（10秒录制）</span>
              <el-tag v-if="hasVideo" type="success" size="small">已录制</el-tag>
              <el-tag v-else type="info" size="small">暂无视频</el-tag>
            </div>
          </template>

          <div v-if="hasVideo" class="video-player-wrapper">
            <div v-if="!videoBlobUrl" class="loading-video">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>视频加载中...</span>
            </div>

            <video 
              v-if="videoBlobUrl"
              :src="videoBlobUrl"
              controls 
              controlsList="nodownload"
              class="analysis-video"
              @error="handleVideoError"
              @loadedmetadata="onVideoLoaded"
              @loadstart="onVideoLoadStart"
              preload="metadata"
              crossorigin="anonymous"
              playsinline
            >
              您的浏览器不支持视频播放
            </video>

            <div class="video-footer" v-if="videoBlobUrl">
              <small>
                当前地址: Blob URL |
                <a href="javascript:void(0)" @click="downloadCurrentVideo" class="download-link">直接下载</a>
              </small>
            </div>
          </div>

          <div v-else class="no-video">
            <el-empty description="该分析记录暂无视频文件" image-size="120" />
          </div>
        </el-card>

        <!-- E1-E14 指标 -->
        <el-card shadow="hover" class="mb-4">
          <template #header>
            <span class="section-title">E1-E14 心理指标数值</span>
          </template>
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="E1 攻击性">{{ detailData.e1 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E2 压力">{{ detailData.e2 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E3 焦虑">{{ detailData.e3 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E4 可疑">{{ detailData.e4 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E5 平衡">{{ detailData.e5 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E6 魅力">{{ detailData.e6 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E7 能量">{{ detailData.e7 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E8 自我调节">{{ detailData.e8 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E9 抑制">{{ detailData.e9 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E10 神经质">{{ detailData.e10 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E11 抑郁">{{ detailData.e11 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E12 幸福">{{ detailData.e12 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E13 外向性">{{ detailData.e13 || '-' }}</el-descriptions-item>
            <el-descriptions-item label="E14 稳定性">{{ detailData.e14 || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 计算方法说明 -->
        <el-card shadow="hover">
          <template #header>
            <span class="section-title">E1-E14 计算方法说明</span>
          </template>
          <div class="explanation">
            <div class="explanation-column">
              <div><strong>E1 攻击性：</strong>数值越高，人的攻击性、冲动倾向越强</div>
              <div><strong>E2 压力：</strong>数值越高，心理压力越大、情绪越紧绷</div>
              <div><strong>E3 焦虑：</strong>数值越高，焦虑感越强、情绪越不安</div>
              <div><strong>E4 可疑：</strong>数值越高，多疑、猜忌等负面情绪越明显</div>
              <div><strong>E5 平衡：</strong>数值越高，情绪状态越平稳、无明显极端倾向</div>
              <div><strong>E6 魅力：</strong>数值越高，亲和力/魅力越强、情绪越亲和</div>
              <div><strong>E7 能量：</strong>数值越高，精力越充沛、精神状态越好</div>
            </div>
            <div class="explanation-column">
              <div><strong>E8 自我调节：</strong>数值越高，情绪自我调节能力越强、状态越稳定</div>
              <div><strong>E9 抑制：</strong>数值越高，对外部刺激的反应越慢、抑制性越强</div>
              <div><strong>E10 神经质：</strong>数值越高，抑制性波动越大，神经质倾向越明显</div>
              <div><strong>E11 抑郁：</strong>数值越高，阴郁、低落的情绪越明显</div>
              <div><strong>E12 幸福：</strong>数值越高，愉悦感、幸福感越强</div>
              <div><strong>E13 外向性：</strong>数值越高，性格外向程度越高</div>
              <div><strong>E14 稳定性：</strong>数值越高，整体情绪和生理状态越稳定</div>
            </div>
          </div>
        </el-card>
      </div>
    </el-drawer>

    <!-- 导出对话框 -->
    <el-dialog
      title="导出Excel - 设置筛选条件"
      v-model="exportDialogVisible"
      width="720px"
      :close-on-click-modal="false"
      append-to-body
    >
      <el-form :model="queryParamsExport" label-width="100px" :inline="true">
        <el-form-item label="人员ID">
          <el-input-number
            v-model="queryParamsExport.personId"
            :min="0"
            placeholder="请输入人员ID"
            clearable
            style="width: 180px"
          />
        </el-form-item>

        <el-form-item label="人名">
          <el-input
            v-model="queryParamsExport.personName"
            placeholder="输入人名（支持模糊）"
            clearable
            style="width: 180px"
          />
        </el-form-item>

        <el-form-item label="视频来源">
          <el-input
            v-model="queryParamsExport.source"
            placeholder="输入视频来源（支持模糊）"
            clearable
            style="width: 180px"
          />
        </el-form-item>

        <el-form-item label="创建时间">
          <el-date-picker
            v-model="queryParamsExport.startTime"
            type="date"
            placeholder="开始日期"
            value-format="YYYY-MM-DD"
            style="width: 160px"
          />
          <span style="margin: 0 8px; color: #909399;">至</span>
          <el-date-picker
            v-model="queryParamsExport.endTime"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 160px"
          />
        </el-form-item>

        <el-form-item label="导出文件名">
          <el-input
            v-model="exportFileName"
            placeholder="请输入导出文件名（不含 .xlsx）"
            style="width: 320px"
          />
        </el-form-item>

        <el-form-item label=" ">
          <el-button type="primary" plain size="small" @click="resetExportParams">
            重置筛选条件
          </el-button>
        </el-form-item>
      </el-form>

      <template #footer>
        <div style="text-align: right; margin-top: 16px;">
          <el-button @click="exportDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="exportLoading"
            @click="confirmExport"
          >
            确认导出
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, getCurrentInstance, nextTick, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  listAnalysis,
  getAnalysis,
  addAnalysis,
  updateAnalysis,
  delAnalysis,
  batchDelAnalysis,
  getVideoBlobUrl,
  downloadVideo
} from '@/api/binhua/analysis'

// ==================== 数据定义 ====================
const queryParams = ref({
  personId: null,
  personName: '',
  source: '',
  startTime: '',
  endTime: '',
  pageNum: 1,
  pageSize: 10
})

const analysisList = ref([])
const total = ref(0)
const loading = ref(false)
const exportLoading = ref(false)

const multipleSelection = ref([])

const dialogVisible = ref(false)
const dialogTitle = ref('新增分析记录')
const isEdit = ref(false)
const formData = ref({
  id: null,
  source: '',
  personName: '',
  personId: null,
  happinessIndex: 0,
  happinessLevel: '',
  safetyRisk: ''
})
const analysisFormRef = ref(null)

const rules = {
  source: [{ required: true, message: '请输入视频来源', trigger: 'blur' }],
  personName: [{ required: true, message: '请输入人名', trigger: 'blur' }],
  personId: [{ required: true, message: '请输入人员ID', trigger: 'blur' }],
  happinessIndex: [{ required: true, message: '请输入幸福指数', trigger: 'blur' }],
  happinessLevel: [{ required: true, message: '请选择幸福等级', trigger: 'change' }]
}

const drawerVisible = ref(false)
const detailData = ref({})

// ==================== 视频相关 ====================
const videoBlobUrl = ref('')

const hasVideo = computed(() => {
  const has = !!(detailData.value?.id && (detailData.value.videoUrl || detailData.value.videoPath || detailData.value.video_path))
  console.log(`[视频日志] hasVideo 判断结果: ${has}，ID=${detailData.value?.id}`)
  return has
})

const loadVideo = async () => {
  videoBlobUrl.value = ''
  if (!detailData.value?.id) return

  try {
    console.log(`[视频日志] 开始加载视频 ID=${detailData.value.id}`)
    const blobUrl = await getVideoBlobUrl(detailData.value.id)
    videoBlobUrl.value = blobUrl
    console.log(`[视频日志] Blob URL 创建成功: ${blobUrl}`)
  } catch (err) {
    console.error('[视频加载失败]', err)
    videoBlobUrl.value = ''
    ElMessage.error('视频加载失败，请检查登录状态')
  }
}

const downloadCurrentVideo = () => {
  if (!detailData.value?.id) return
  downloadVideo(detailData.value.id, `分析视频_${detailData.value.id}.mp4`)
}

const onVideoLoadStart = () => console.log(`[视频日志] loadstart → 开始请求视频`)
const onVideoLoaded = () => console.log(`[视频日志] loadedmetadata → 元数据加载完成`)

const handleVideoError = (e) => {
  const video = e.target
  console.error('=== 【视频加载失败】详细诊断信息 ===')
  console.error('当前 src:', videoBlobUrl.value)
  if (video?.error) {
    console.error('MediaError.code:', video.error.code)
    console.error('MediaError.message:', video.error.message)
  }
  ElMessage.error(`视频加载失败（错误码: ${video?.error?.code || '未知'}）`)
}

// ==================== 工具函数 ====================
const getLevelTagType = (level) => {
  const typeMap = {
    '高': 'success',
    '中': 'warning',
    '低': 'danger',
    '未知': 'info'
  }
  return typeMap[level] || 'info'
}

const formatDate = (date) => {
  if (!date) return '-'
  try {
    let parsedDate = !isNaN(Number(date)) ? new Date(Number(date)) : new Date(date.replace('T', ' ').replace(/\..+/, ''))
    if (isNaN(parsedDate.getTime())) return '-'
    return parsedDate.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return '-'
  }
}

const getLevelCount = () => {
  const count = { 高: 0, 中: 0, 低: 0, 未知: 0 }
  analysisList.value.forEach(item => {
    const level = item.happinessLevel
    if (level in count) count[level]++
    else count.未知++
  })
  return count
}

const getTrendData = () => {
  const sortedList = [...analysisList.value].sort((a, b) => {
    const t1 = new Date(a.createTime || 0).getTime()
    const t2 = new Date(b.createTime || 0).getTime()
    return t1 - t2
  })
  const showList = sortedList.slice(0, 10)
  return {
    xAxis: showList.map((_, i) => `第${i+1}条`),
    yAxis: showList.map(item => (Number(item.happinessIndex) || 0) / 100)
  }
}

const getPieChartOption = () => {
  const levelCount = getLevelCount()
  const totalCount = analysisList.value.length || 1
  const colorMap = {
    '高': '#67C23A',
    '中': '#E6A23C',
    '低': '#F56C6C',
    '未知': '#909399'
  }
  const data = [
    { value: levelCount.高, name: `高 (${((levelCount.高 / totalCount) * 100).toFixed(1)}%)`, itemStyle: { color: colorMap['高'] } },
    { value: levelCount.中, name: `中 (${((levelCount.中 / totalCount) * 100).toFixed(1)}%)`, itemStyle: { color: colorMap['中'] } },
    { value: levelCount.低, name: `低 (${((levelCount.低 / totalCount) * 100).toFixed(1)}%)`, itemStyle: { color: colorMap['低'] } },
    { value: levelCount.未知, name: `未知 (${((levelCount.未知 / totalCount) * 100).toFixed(1)}%)`, itemStyle: { color: colorMap['未知'] } }
  ].filter(item => item.value > 0)

  return {
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', left: 'left', top: 'middle' },
    series: [{
      name: '幸福等级分布',
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['55%', '55%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
      labelLine: { show: false },
      data
    }]
  }
}

// ==================== 【修改重点】美化版幸福指数趋势图 ====================
const getLineChartOption = () => {
  const trendData = getTrendData()
  const hasData = trendData.xAxis.length > 0

  const mainSeries = {
    name: '幸福指数',
    type: 'line',
    data: hasData ? trendData.yAxis.map(v => v * 100) : [0],
    symbol: 'circle',
    symbolSize: 10,
    lineStyle: { width: 3, color: '#F56C6C' },
    itemStyle: {
      color: function(params) {
        const value = params.value
        if (value < 30) return '#F56C6C'    // 低
        if (value < 70) return '#FFD050'    // 中
        return '#67C23A'                    // 高
      },
      borderWidth: 2,
      borderColor: '#fff'
    },
    z: 10
  }

  // 背景分段区域
  const backgroundSeries = [
    // 低等级：0~30 浅红
    {
      type: 'line',
      data: [],
      markArea: {
        silent: true,
        itemStyle: { color: 'rgba(245, 102, 102, 0.15)' },
        data: [[ { xAxis: 0, yAxis: 0 }, { xAxis: 'max', yAxis: 30 } ]]
      },
      lineStyle: { opacity: 0 }
    },
    // 中等级：30~70 浅黄
    {
      type: 'line',
      data: [],
      markArea: {
        silent: true,
        itemStyle: { color: 'rgba(255, 208, 80, 0.25)' },
        data: [[ { xAxis: 0, yAxis: 30 }, { xAxis: 'max', yAxis: 70 } ]]
      },
      lineStyle: { opacity: 0 }
    },
    // 高等级：70~100 浅绿
    {
      type: 'line',
      data: [],
      markArea: {
        silent: true,
        itemStyle: { color: 'rgba(103, 194, 58, 0.15)' },
        data: [[ { xAxis: 0, yAxis: 70 }, { xAxis: 'max', yAxis: 100 } ]]
      },
      lineStyle: { opacity: 0 }
    }
  ]

  return {
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        const val = params[0].value
        let level = val < 30 ? '低' : val < 70 ? '中' : '高'
        return `${params[0].name}<br/>幸福指数：${val.toFixed(1)}分<br/>等级：${level}`
      },
      axisPointer: { type: 'shadow' }
    },
    grid: { left: '5%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: hasData ? trendData.xAxis : ['暂无数据'],
      axisLabel: { fontSize: 12 },
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      name: '幸福指数（分）',
      min: 0,
      max: 100,
      interval: 20,
      axisLabel: { formatter: '{value} 分' }
    },
    series: [...backgroundSeries, mainSeries]
  }
}

// ==================== 图表初始化 ====================
const happinessChart = ref(null)
const trendChart = ref(null)
let pieChartInstance = null
let lineChartInstance = null

const initCharts = async () => {
  await nextTick()
  try {
    if (happinessChart.value) {
      if (pieChartInstance) pieChartInstance.dispose()
      pieChartInstance = echarts.init(happinessChart.value, 'macarons')
      pieChartInstance.setOption(getPieChartOption())
    }
    if (trendChart.value) {
      if (lineChartInstance) lineChartInstance.dispose()
      lineChartInstance = echarts.init(trendChart.value, 'macarons')
      lineChartInstance.setOption(getLineChartOption())
    }
  } catch (err) {
    console.error('ECharts 初始化失败:', err)
  }
}

const resizeHandler = () => {
  pieChartInstance?.resize()
  lineChartInstance?.resize()
}

watch(analysisList, async () => {
  await nextTick()
  try {
    if (pieChartInstance) pieChartInstance.setOption(getPieChartOption(), true)
    if (lineChartInstance) lineChartInstance.setOption(getLineChartOption(), true)
  } catch (err) {
    console.error('ECharts setOption 失败:', err)
  }
}, { deep: true })

// ==================== 生命周期 ====================
onMounted(() => {
  initCharts()
  window.addEventListener('resize', resizeHandler)
  getList()
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeHandler)
  pieChartInstance?.dispose()
  lineChartInstance?.dispose()
})

// ==================== 数据请求方法 ====================
const getList = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: queryParams.value.pageNum,
      pageSize: queryParams.value.pageSize
    }

    if (queryParams.value.personId != null) params.personId = queryParams.value.personId
    if (queryParams.value.personName?.trim()) params.personName = queryParams.value.personName.trim()
    if (queryParams.value.source?.trim()) params.source = queryParams.value.source.trim()
    if (queryParams.value.startTime) params.startTime = `${queryParams.value.startTime} 00:00:00`
    if (queryParams.value.endTime) params.endTime = `${queryParams.value.endTime} 23:59:59`

    const res = await listAnalysis(params)
    const data = res.data || {}
    analysisList.value = data.records || data.rows || data.list || data.data || []
    total.value = data.total || 0
  } catch (err) {
    ElMessage.error(err.message || '获取列表失败')
  } finally {
    loading.value = false
  }
}

const handleQuery = () => {
  queryParams.value.pageNum = 1
  getList()
}

const resetQuery = () => {
  queryParams.value = {
    personId: null,
    personName: '',
    source: '',
    startTime: '',
    endTime: '',
    pageNum: 1,
    pageSize: 10
  }
  handleQuery()
}

const handleSelectionChange = (val) => {
  multipleSelection.value = val
}

const handleAdd = () => {
  Object.assign(formData.value, {
    id: null,
    source: '',
    personName: '',
    personId: null,
    happinessIndex: 0,
    happinessLevel: '',
    safetyRisk: ''
  })
  isEdit.value = false
  dialogTitle.value = '新增分析记录'
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  try {
    const res = await getAnalysis(row.id)
    Object.assign(formData.value, res.data || row)
    isEdit.value = true
    dialogTitle.value = '编辑分析记录'
    dialogVisible.value = true
  } catch {
    ElMessage.error('获取详情失败')
  }
}

const handleView = async (row) => {
  console.log('[视频日志] handleView 被调用，当前记录 ID=', row.id)
  detailData.value = { ...row }
  drawerVisible.value = true

  if (row.id) {
    await loadVideo()
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该记录吗？', '提示', { type: 'warning' })
    await delAnalysis(row.id)
    ElMessage.success('删除成功')
    getList()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleBatchDelete = async () => {
  const ids = multipleSelection.value.map(item => item.id).join(',')
  if (!ids) return
  try {
    await ElMessageBox.confirm('确定批量删除选中的记录吗？', '提示', { type: 'warning' })
    await batchDelAnalysis({ analysisIds: ids })
    ElMessage.success('批量删除成功')
    getList()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('批量删除失败')
  }
}

const submitForm = async () => {
  try {
    await analysisFormRef.value?.validate()
    if (isEdit.value && formData.value.id) {
      await updateAnalysis(formData.value.id, formData.value)
      ElMessage.success('修改成功')
    } else {
      await addAnalysis(formData.value)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    getList()
  } catch (err) {
    ElMessage.error(err.message || (isEdit.value ? '修改失败' : '新增失败'))
  }
}

// ==================== 导出相关 ====================
const exportDialogVisible = ref(false)
const exportFileName = ref('')
const queryParamsExport = ref({
  personId: null,
  personName: '',
  source: '',
  startTime: '',
  endTime: ''
})

const openExportDialog = () => {
  queryParamsExport.value = { ...queryParams.value }
  const dateStr = new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')
  exportFileName.value = `幸福分析记录_${dateStr}`
  exportDialogVisible.value = true
}

const resetExportParams = () => {
  queryParamsExport.value = {
    personId: null,
    personName: '',
    source: '',
    startTime: '',
    endTime: ''
  }
}

const proxy = getCurrentInstance()?.proxy

const confirmExport = () => {
  exportDialogVisible.value = false
  exportLoading.value = true

  const params = {
    pageNum: 1,
    pageSize: 999999,
  }

  if (queryParamsExport.value.personId != null) params.personId = queryParamsExport.value.personId
  if (queryParamsExport.value.personName?.trim()) params.personName = queryParamsExport.value.personName.trim()
  if (queryParamsExport.value.source?.trim()) params.source = queryParamsExport.value.source.trim()
  if (queryParamsExport.value.startTime) params.startTime = queryParamsExport.value.startTime + ' 00:00:00'
  if (queryParamsExport.value.endTime) params.endTime = queryParamsExport.value.endTime + ' 23:59:59'

  const filename = (exportFileName.value || '幸福分析记录') + '.xlsx'

  proxy.download('/analysis/export', params, filename)
    .then(() => ElMessage.success('导出成功'))
    .catch(err => {
      console.error('导出失败', err)
      ElMessage.error('导出失败')
    })
    .finally(() => {
      exportLoading.value = false
    })
}
</script>

<style scoped>
.analysis-container {
  padding: 20px;
}

.search-card {
  margin-bottom: 20px;
}

.chart-group {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.chart-card {
  flex: 1;
  border-radius: 8px;
  overflow: hidden;
}

.table-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}

.card-header > div {
  display: flex;
  gap: 8px;
}

.pagination-center {
  margin: 20px 0;
  text-align: center;
}

.chart-container {
  width: 100%;
  height: 340px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.video-card {
  margin-bottom: 20px;
}

.video-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.video-player-wrapper {
  position: relative;
}

.analysis-video {
  width: 100%;
  max-height: 320px;
  border-radius: 8px;
  background-color: #000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.video-footer {
  margin-top: 10px;
  text-align: center;
  color: #666;
  font-size: 13px;
}

.download-link {
  color: #409EFF;
  text-decoration: none;
}

.download-link:hover {
  text-decoration: underline;
}

.no-video {
  padding: 40px 0;
  text-align: center;
}

.explanation {
  display: flex;
  flex-wrap: wrap;
  gap: 30px;
  padding: 15px;
  background-color: #fafafa;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.7;
}

.explanation-column {
  flex: 1;
  min-width: 280px;
}

@media (max-width: 1200px) {
  .chart-group {
    flex-direction: column;
  }
  .analysis-video {
    max-height: 280px;
  }
}
</style>