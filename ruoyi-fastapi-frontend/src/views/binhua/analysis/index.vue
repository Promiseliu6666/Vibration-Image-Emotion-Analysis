<template>
  <div class="analysis-container">
    <section class="detection-hub" aria-labelledby="detection-hub-title">
      <div class="detection-hub__heading">
        <div>
          <span class="detection-hub__eyebrow">智能状态感知</span>
          <h2 id="detection-hub-title">选择检测方式</h2>
        </div>
        <p>共用现有摄像头接入，从心理状态与疲劳行为两个角度辅助观察。</p>
      </div>

      <div class="detection-grid">
        <button
          type="button"
          class="detection-card detection-card--wellbeing"
          @click="router.push('/camera/live')"
        >
          <span class="detection-card__icon" aria-hidden="true">
            <el-icon :size="25"><Sunny /></el-icon>
          </span>
          <span class="detection-card__body">
            <span class="detection-card__meta">面部微振动 · 心理状态</span>
            <strong>幸福指数检测</strong>
            <span class="detection-card__description">
              查看当前幸福指数、安全风险与各项振动心理指标。
            </span>
          </span>
          <span class="detection-card__action">进入检测 <span>→</span></span>
          <span class="signal-trace" aria-hidden="true"></span>
        </button>

        <button
          type="button"
          class="detection-card detection-card--fatigue"
          @click="router.push('/fatigue')"
        >
          <span class="detection-card__icon" aria-hidden="true">
            <el-icon :size="25"><Timer /></el-icon>
          </span>
          <span class="detection-card__body">
            <span class="detection-card__meta">眼口行为 · 姿态时序</span>
            <strong>疲劳检测</strong>
            <span class="detection-card__description">
              观察闭眼、眨眼、哈欠和姿态变化，综合评估当前专注度。
            </span>
          </span>
          <span class="detection-card__action">进入检测 <span>→</span></span>
          <span class="signal-trace" aria-hidden="true"></span>
        </button>
      </div>
    </section>

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

        <!-- 人名：已改为下拉选择框 -->
        <el-form-item label="人名">
          <el-select
            v-model="queryParams.personName"
            placeholder="请选择人名"
            clearable
            filterable
            style="width: 180px"
            @change="handleQuery"
          >
            <el-option
              v-for="item in personNameOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="视频来源">
          <el-select
            v-model="queryParams.source"
            placeholder="选择或输入视频来源"
            clearable
            filterable
            allow-create
            default-first-option
            style="width: 180px"
          >
            <el-option
              v-for="option in cameraFilterOptions"
              :key="option.id"
              :label="option.label"
              :value="option.id"
            />
          </el-select>
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

    <!-- 第一行图表 -->
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

    <!-- 第二行图表：整体平均雷达图 + 风险柱状图 -->
    <div class="chart-group">
      <el-card class="chart-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>全体人员心理指标平均值（8维度）</span>
          </div>
        </template>
        <div ref="radarChart" class="chart-container" />
      </el-card>

      <el-card class="chart-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>指标健康度概览</span>
          </div>
        </template>
        <div ref="riskBarChart" class="chart-container" />
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

            <!-- 导出分析报告 按钮 -->
            <el-button
              type="primary"
              icon="el-icon-document"
              :disabled="!singleSelection"
              @click="handleExportReport"
            >
              导出分析报告
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
          <el-select
            v-model="formData.source"
            placeholder="选择或输入视频来源"
            filterable
            allow-create
            default-first-option
            style="width: 100%"
          >
            <el-option
              v-for="option in cameraFilterOptions"
              :key="option.id"
              :label="option.label"
              :value="option.id"
            />
          </el-select>
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

        <!-- 个人雷达图 -->
        <el-card shadow="hover" class="mb-4">
          <template #header>
            <span class="section-title">个人心理状态画像（8维度）</span>
          </template>
          <div ref="personRadarChart" class="chart-container" style="height: 360px"></div>
        </el-card>

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

        <!-- 导出里的人名也改为下拉 -->
        <el-form-item label="人名">
          <el-select
            v-model="queryParamsExport.personName"
            placeholder="请选择人名"
            clearable
            filterable
            style="width: 180px"
          >
            <el-option
              v-for="item in personNameOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="视频来源">
          <el-select
            v-model="queryParamsExport.source"
            placeholder="选择或输入视频来源"
            clearable
            filterable
            allow-create
            default-first-option
            style="width: 180px"
          >
            <el-option
              v-for="option in cameraFilterOptions"
              :key="option.id"
              :label="option.label"
              :value="option.id"
            />
          </el-select>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { Sunny, Timer } from '@element-plus/icons-vue'
import useCameraStore from '@/store/modules/camera'
import {
  listAnalysis,
  getAnalysis,
  addAnalysis,
  updateAnalysis,
  delAnalysis,
  batchDelAnalysis,
  getVideoBlobUrl,
  downloadVideo,
  exportPersonReport
} from '@/api/binhua/analysis'

const router = useRouter()
const cameraStore = useCameraStore()

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
const personNameOptions = ref([])
const cameraFilterOptions = computed(() => cameraStore.cameraOptions.map(option => ({
  id: option.id,
  label: `${option.label}${option.detail ? ` · ${option.detail}` : ''}`
})))
const singleSelection = ref(false)
const currentReportRow = ref(null)

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
  source: [{ required: true, message: '请选择或输入视频来源', trigger: 'change' }],
  personName: [{ required: true, message: '请输入人名', trigger: 'blur' }],
  personId: [{ required: true, message: '请输入人员ID', trigger: 'blur' }],
  happinessIndex: [{ required: true, message: '请输入幸福指数', trigger: 'blur' }],
  happinessLevel: [{ required: true, message: '请选择幸福等级', trigger: 'change' }]
}

const drawerVisible = ref(false)
const detailData = ref({})
const videoBlobUrl = ref('')

const happinessChart = ref(null)
const trendChart = ref(null)
const radarChart = ref(null)
const personRadarChart = ref(null)
const riskBarChart = ref(null)

let pieChartInstance = null
let lineChartInstance = null
let radarChartInstance = null
let personRadarInstance = null
let riskBarInstance = null

const hasVideo = computed(() => {
  const has = !!(detailData.value?.id && (detailData.value.videoUrl || detailData.value.videoPath || detailData.value.video_path))
  return has
})

const loadVideo = async () => {
  videoBlobUrl.value = ''
  if (!detailData.value?.id) return
  try {
    const blobUrl = await getVideoBlobUrl(detailData.value.id)
    videoBlobUrl.value = blobUrl
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

const onVideoLoadStart = () => {}
const onVideoLoaded = () => {}

const handleVideoError = (e) => {
  const video = e.target
  console.error('视频加载失败', video.error)
  ElMessage.error(`视频加载失败（错误码: ${video?.error?.code || '未知'}）`)
}

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

const getPersonNameOptions = () => {
  const names = [...new Set(
    analysisList.value
      .map(item => item.personName)
      .filter(name => name && name.trim())
  )]
  personNameOptions.value = names.map(name => ({
    label: name,
    value: name
  }))
}

const getAvgRadarOption = () => {
  const list = analysisList.value
  if (!list.length) {
    return {
      title: { text: '暂无数据', left: 'center', top: 'center' },
      radar: { indicator: [] },
      series: []
    }
  }

  let sumE12 = 0, sumE2 = 0, sumE3 = 0, sumE14 = 0
  let sumE1 = 0, sumE13 = 0, sumE8 = 0, sumE11 = 0
  let count = 0

  list.forEach(item => {
    sumE12 += Number(item.e12) || 0
    sumE2 += Number(item.e2) || 0
    sumE3 += Number(item.e3) || 0
    sumE14 += Number(item.e14) || 0
    sumE1 += Number(item.e1) || 0
    sumE13 += Number(item.e13) || 0
    sumE8 += Number(item.e8) || 0
    sumE11 += Number(item.e11) || 0
    count++
  })

  const data = [
    Math.round(sumE12 / count),
    Math.round(sumE2 / count),
    Math.round(sumE3 / count),
    Math.round(sumE14 / count),
    Math.round(sumE1 / count),
    Math.round(sumE13 / count),
    Math.round(sumE8 / count),
    Math.round(sumE11 / count)
  ]

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}分' },
    radar: {
      radius: '58%',
      axisName: { fontSize: 14, color: '#333' },
      indicator: [
        { name: '幸福度', max: 100 },
        { name: '压力值', max: 100 },
        { name: '焦虑值', max: 100 },
        { name: '稳定性', max: 100 },
        { name: '攻击性', max: 100 },
        { name: '外向性', max: 100 },
        { name: '自我调节', max: 100 },
        { name: '抑郁倾向', max: 100 }
      ],
      splitArea: {
        areaStyle: {
          color: ['rgba(103,194,58,0.1)','rgba(230,162,60,0.1)','rgba(245,108,108,0.1)']
        }
      }
    },
    series: [{
      type: 'radar',
      data: [{
        value: data,
        name: '全体平均值',
        areaStyle: { color: 'rgba(64, 158, 255, 0.2)' },
        lineStyle: { color: '#409EFF', width: 2 },
        itemStyle: { color: '#409EFF' }
      }],
      label: { show: false }
    }]
  }
}

const getPersonRadarOption = (row) => {
  const data = [
    Math.round(Number(row.e12) || 0),
    Math.round(Number(row.e2) || 0),
    Math.round(Number(row.e3) || 0),
    Math.round(Number(row.e14) || 0),
    Math.round(Number(row.e1) || 0),
    Math.round(Number(row.e13) || 0),
    Math.round(Number(row.e8) || 0),
    Math.round(Number(row.e11) || 0)
  ]
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}分' },
    radar: {
      radius: '58%',
      axisName: { fontSize: 14, color: '#333' },
      indicator: [
        { name: '幸福度', max: 100 },
        { name: '压力值', max: 100 },
        { name: '焦虑值', max: 100 },
        { name: '稳定性', max: 100 },
        { name: '攻击性', max: 100 },
        { name: '外向性', max: 100 },
        { name: '自我调节', max: 100 },
        { name: '抑郁倾向', max: 100 }
      ],
      splitArea: {
        areaStyle: {
          color: ['rgba(103,194,58,0.1)','rgba(230,162,60,0.1)','rgba(245,108,108,0.1)']
        }
      }
    },
    series: [{
      type: 'radar',
      data: [{
        value: data,
        name: row.personName || '当前人员',
        areaStyle: { color: 'rgba(255, 103, 80, 0.2)' },
        lineStyle: { color: '#F56C6C', width: 2 },
        itemStyle: { color: '#F56C6C' }
      }],
      label: { show: false }
    }]
  }
}

const getRiskBarOption = () => {
  const list = analysisList.value;

  const personMap = {};
  list.forEach(item => {
    const pid = item.personId;
    if (!pid) return;
    if (!personMap[pid]) {
      personMap[pid] = {
        name: item.personName,
        total: 0,
        count: 0
      };
    }
    const val = Number(item.happinessIndex) || 0;
    personMap[pid].total += val;
    personMap[pid].count += 1;
  });

  const personList = Object.values(personMap).map(p => ({
    name: p.name,
    avg: Math.round(p.total / p.count)
  }));

  const levelCount = { 高: 0, 中: 0, 低: 0, 未知: 0 };
  personList.forEach(p => {
    const avg = p.avg;
    if (avg >= 80) levelCount.高++;
    else if (avg >= 60) levelCount.中++;
    else if (avg > 0) levelCount.低++;
    else levelCount.未知++;
  });

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: '{b}等级：{c} 人'
    },
    grid: { left: '10%', right: '5%', bottom: '10%', top: '10%' },
    xAxis: {
      type: 'category',
      data: ['高', '中', '低'],
      axisLabel: { fontSize: 13 }
    },
    yAxis: { type: 'value', name: '人数' },
    series: [{
      type: 'bar',
      data: [
        { value: levelCount.高, itemStyle: { color: '#67C23A' } },
        { value: levelCount.中, itemStyle: { color: '#E6A23C' } },
        { value: levelCount.低, itemStyle: { color: '#F56C6C' } }
      ],
      barWidth: '40%',
      label: { show: true, position: 'top', formatter: '{c}' }
    }]
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
        if (value < 60) return '#F56C6C'
        if (value < 80) return '#E6A23C'
        return '#67C23A'
      },
      borderWidth: 2,
      borderColor: '#fff'
    },
    z: 10
  }

  const backgroundSeries = [
    {
        type: 'line',
        data: [],
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(245, 102, 102, 0.15)' },
          data: [[{ xAxis: 0, yAxis: 0 }, { xAxis: 'max', yAxis: 60 }]]
        },
        lineStyle: { opacity: 0 }
      },
    {
        type: 'line',
        data: [],
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(255, 208, 80, 0.25)' },
          data: [[{ xAxis: 0, yAxis: 60 }, { xAxis: 'max', yAxis: 80 }]]
        },
        lineStyle: { opacity: 0 }
      },
    {
        type: 'line',
        data: [],
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(103, 194, 58, 0.15)' },
          data: [[{ xAxis: 0, yAxis: 80 }, { xAxis: 'max', yAxis: 100 }]]
        },
        lineStyle: { opacity: 0 }
      }
  ]

  return {
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        const val = params[0].value
        let level = val < 60 ? '低' : val < 80 ? '中' : '高'
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
    if (radarChart.value) {
      if (radarChartInstance) radarChartInstance.dispose()
      radarChartInstance = echarts.init(radarChart.value, 'macarons')
      radarChartInstance.setOption(getAvgRadarOption())
    }
    if (riskBarChart.value) {
      if (riskBarInstance) riskBarInstance.dispose()
      riskBarInstance = echarts.init(riskBarChart.value, 'macarons')
      riskBarInstance.setOption(getRiskBarOption())
    }
  } catch (err) {
    console.error('图表初始化失败:', err)
  }
}

const resizeHandler = () => {
  pieChartInstance?.resize()
  lineChartInstance?.resize()
  radarChartInstance?.resize()
  personRadarInstance?.resize()
  riskBarInstance?.resize()
}

watch(analysisList, async () => {
  await nextTick()
  try {
    if (pieChartInstance) pieChartInstance.setOption(getPieChartOption(), true)
    if (lineChartInstance) lineChartInstance.setOption(getLineChartOption(), true)
    if (radarChartInstance) radarChartInstance.setOption(getAvgRadarOption(), true)
    if (riskBarInstance) riskBarInstance.setOption(getRiskBarOption(), true)
  } catch (err) {
    console.error('图表更新失败:', err)
  }
}, { deep: true })

onMounted(async () => {
  initCharts()
  window.addEventListener('resize', resizeHandler)
  loadAllPersonNames()
  getList()
  try {
    await cameraStore.loadXiaozhiDevices()
  } catch {
    // Historical filtering still accepts manually entered source values.
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeHandler)
  pieChartInstance?.dispose()
  lineChartInstance?.dispose()
  radarChartInstance?.dispose()
  personRadarInstance?.dispose()
  riskBarInstance?.dispose()
})

const handleView = async (row) => {
  detailData.value = { ...row }
  drawerVisible.value = true
  if (row.id) await loadVideo()

  await nextTick()
  if (personRadarChart.value) {
    if (personRadarInstance) personRadarInstance.dispose()
    personRadarInstance = echarts.init(personRadarChart.value, 'macarons')
    personRadarInstance.setOption(getPersonRadarOption(row))
  }
}

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
    getPersonNameOptions()
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
  if (val.length === 1) {
    singleSelection.value = true
    currentReportRow.value = val[0]
  } else {
    singleSelection.value = false
    currentReportRow.value = null
  }
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

// ==================== 导出分析报告 PDF ====================
const handleExportReport = async () => {
  if (!currentReportRow.value) {
    ElMessage.warning('请选择一条记录')
    return
  }

  const row = currentReportRow.value
  exportLoading.value = true

  try {
    let tempChart = echarts.init(document.createElement('div'))
    tempChart.setOption(getPersonRadarOption(row))
    
    const radarBase64 = tempChart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff'
    })
    tempChart.dispose()

    const res = await exportPersonReport({
      analysisId: row.id,
      radarImage: radarBase64
    })

    const blob = new Blob([res], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${row.personName || '人员'}_心理分析报告.pdf`
    a.click()
    URL.revokeObjectURL(url)

    ElMessage.success('PDF 报告导出成功')
  } catch (err) {
    console.error(err)
    ElMessage.error('报告导出失败，请检查后端接口')
  } finally {
    exportLoading.value = false
  }
}

// ====================== 加载所有人名到下拉框 ======================
const loadAllPersonNames = async () => {
  try {
    const params = { pageNum: 1, pageSize: 5000 }
    const res = await listAnalysis(params)
    const data = res.data || {}
    const fullList = data.records || data.rows || data.list || []
    
    const extractedNames = fullList
      .map(item => (item.personName || '').trim())
      .filter(name => name.length > 0)
    
    const uniqueNames = [...new Set(extractedNames)].sort((a, b) => a.localeCompare(b, 'zh-CN'))
    personNameOptions.value = uniqueNames.map(name => ({ label: name, value: name }))
  } catch (err) {
    console.error('加载人名失败', err)
  }
}
</script>

<style scoped>
.analysis-container {
  padding: 20px;
}
.detection-hub {
  margin-bottom: 20px;
  padding: 22px;
  overflow: hidden;
  background:
    radial-gradient(circle at 92% 8%, rgba(59, 130, 246, 0.08), transparent 28%),
    #f8fafc;
  border: 1px solid #e4e9f0;
  border-radius: 12px;
}
.detection-hub__heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}
.detection-hub__eyebrow {
  display: block;
  margin-bottom: 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
}
.detection-hub__heading h2 {
  margin: 0;
  color: #1f2937;
  font-size: 22px;
  line-height: 1.3;
}
.detection-hub__heading p {
  max-width: 480px;
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
  text-align: right;
}
.detection-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.detection-card {
  --accent: #2f7d65;
  --accent-soft: #e8f5ef;
  position: relative;
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  min-height: 136px;
  padding: 20px 20px 24px;
  overflow: hidden;
  color: #1f2937;
  text-align: left;
  cursor: pointer;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.05);
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}
.detection-card--fatigue {
  --accent: #b66b17;
  --accent-soft: #fff4e5;
}
.detection-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent) 42%, #e2e8f0);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.09);
}
.detection-card:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--accent) 30%, transparent);
  outline-offset: 2px;
}
.detection-card__icon {
  display: grid;
  width: 52px;
  height: 52px;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 12px;
  place-items: center;
}
.detection-card__body {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.detection-card__meta {
  margin-bottom: 5px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
}
.detection-card__body strong {
  color: #111827;
  font-size: 18px;
  line-height: 1.4;
}
.detection-card__description {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}
.detection-card__action {
  align-self: end;
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.detection-card__action span {
  display: inline-block;
  margin-left: 3px;
  transition: transform 180ms ease;
}
.detection-card:hover .detection-card__action span {
  transform: translateX(3px);
}
.signal-trace {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 5px;
  opacity: 0.55;
  background:
    linear-gradient(166deg, transparent 0 22%, var(--accent) 22% 27%, transparent 27% 42%, var(--accent) 42% 48%, transparent 48% 64%, var(--accent) 64% 68%, transparent 68%);
  background-size: 76px 8px;
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
.empty-placeholder {
  width: 100%;
  height: 340px;
}
@media (max-width: 1200px) {
  .chart-group {
    flex-direction: column;
  }
  .analysis-video {
    max-height: 280px;
  }
}
@media (max-width: 860px) {
  .detection-hub__heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .detection-hub__heading p {
    text-align: left;
  }
  .detection-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 520px) {
  .analysis-container {
    padding: 12px;
  }
  .detection-hub {
    padding: 16px;
  }
  .detection-card {
    grid-template-columns: 44px minmax(0, 1fr);
    gap: 12px;
    padding: 16px 16px 22px;
  }
  .detection-card__icon {
    width: 44px;
    height: 44px;
  }
  .detection-card__action {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .detection-card,
  .detection-card__action span {
    transition: none;
  }
}
</style>
