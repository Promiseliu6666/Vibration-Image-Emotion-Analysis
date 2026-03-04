<template>
  <div class="app-container">
    <!-- 统计信息卡片 -->
    <el-row :gutter="20" class="mb4">
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><VideoCamera /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-title">总任务数</div>
              
              <div class="stat-value">{{ total }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><VideoPlay /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-title">已启用</div>
              <div class="stat-value">{{ runningJobCount }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><VideoPause /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-title">已停用</div>
              <div class="stat-value">{{ stoppedJobCount }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="任务名称" prop="jobName">
        <el-input v-model="queryParams.jobName" placeholder="请输入任务名称" clearable style="width: 240px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item label="任务状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="请选择任务状态" clearable style="width: 240px">
          <el-option v-for="dict in sys_normal_disable" :key="dict.value" :label="dict.label" :value="dict.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd">新增</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="jobList" @selection-change="handleSelectionChange">
      <el-table-column label="任务名称" align="center" prop="jobName" :show-overflow-tooltip="true" />
      <el-table-column label="关联视频数量" align="center" width="120">
        <template #default="scope">
          <el-tooltip placement="top" :content="getVideoContent(scope.row)" :disabled="!getVideoContent(scope.row)">
            <span>{{ getVideoCount(scope.row) }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <!-- <el-table-column label="调用目标" align="center" prop="invokeTarget" :show-overflow-tooltip="true" /> -->
      <el-table-column label="Cron执行表达式" align="center" prop="cronExpression" :show-overflow-tooltip="true" />
      <el-table-column label="状态" align="center" width="100">
        <template #default="scope">
          <el-tag :type="getJobStatusType(scope.row)">
            {{ getJobStatusText(scope.row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="200" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-tooltip content="配置" placement="top">
            <el-button link type="primary" icon="Edit" @click="handleJobConfig(scope.row)"></el-button>
          </el-tooltip>
          <el-tooltip content="立即执行" placement="top">
            <el-button link type="primary" icon="CaretRight" @click="handleJobRun(scope.row)"></el-button>
          </el-tooltip>
          <el-tooltip content="查看日志" placement="top">
            <el-button link type="primary" icon="Operation" @click="handleJobLog(scope.row)"></el-button>
          </el-tooltip>
          <el-tooltip content="删除" placement="top">
            <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"></el-button>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" v-model:page="queryParams.pageNum" v-model:limit="queryParams.pageSize" @pagination="getList" />

    <el-dialog :title="currentJob ? `配置定时任务 - ${currentJob.jobName}` : '新增定时任务'" v-model="jobConfigVisible" width="600px" append-to-body>
      <el-form ref="jobConfigRef" :model="jobConfigForm" :rules="jobConfigRules" label-width="120px">
      <el-row :gutter="20">
        <el-col :span="24">
          <el-form-item label="任务名称" prop="jobName">
            <el-input v-model="jobConfigForm.jobName" placeholder="请输入任务名称" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="运行时长" prop="durationMinutes">
              <div style="display: flex; align-items: center; width: 100%;">
                <el-input-number v-model="jobConfigForm.durationMinutes" :min="1" :max="10080" controls-position="right" placeholder="分钟" style="flex: 1;" />
                <span style="margin-left: 10px;">分钟</span>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Cron表达式" prop="cronExpression">
              <el-input v-model="jobConfigForm.cronExpression" placeholder="请输入cron执行表达式">
                <template #append>
                  <el-button type="primary" @click="handleShowCron">生成表达式</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="任务状态">
              <el-radio-group v-model="jobConfigForm.status">
                <el-radio-button value="0">启用</el-radio-button>
                <el-radio-button value="1">停用</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">关联视频</el-divider>
        <div v-if="selectedVideos.length > 0" class="mb8">
            <div style="margin-bottom: 5px; font-weight: bold;">已选视频 ({{ selectedVideos.length }}):</div>
            <el-tag
                v-for="video in selectedVideos"
                :key="video.vidId"
                closable
                class="mr-2 mb-2"
                @close="handleCloseTag(video)"
            >
                {{ video.vidName }}
            </el-tag>
        </div>
        <el-row :gutter="10" class="mb8">
          <el-col :span="12">
            <el-input v-model="videoQueryParams.vidName" placeholder="请输入视频名称" clearable @keyup.enter="handleVideoQuery" />
          </el-col>
          <el-col :span="6">
            <el-button type="primary" icon="Search" @click="handleVideoQuery">搜索</el-button>
          </el-col>
        </el-row>
        <el-table ref="videoTableRef" v-loading="videoLoading" :data="videoList" row-key="vidId" @select="handleVideoSelect" @select-all="handleVideoSelectAll" height="300px">
          <el-table-column type="selection" width="55" />
          <el-table-column label="视频名称" align="center" prop="vidName" />
          <el-table-column label="序列号" align="center" prop="vidSerial" />
        </el-table>
        <pagination v-show="videoTotal > 0" :total="videoTotal" v-model:page="videoQueryParams.pageNum" v-model:limit="videoQueryParams.pageSize" @pagination="getVideoList" layout="prev, pager, next" small />
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitJobConfig">确 定</el-button>
          <el-button @click="cancelJobConfig">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="Cron表达式生成器" v-model="openCron" append-to-body destroy-on-close>
      <crontab ref="crontabRef" @hide="openCron=false" @fill="crontabFill" :expression="cronExpression" />
    </el-dialog>
  </div>
</template>

<script setup name="BackendAI">
import { ref, reactive, toRefs, getCurrentInstance, onMounted, onUnmounted } from 'vue'
import { listJob, updateJob, runJob, addJob, delJob } from '@/api/monitor/job'
import { listVideo, getVideo } from '@/api/xuzhou/video'
import { VideoCamera, VideoPlay, VideoPause, Edit, CaretRight, Operation, Plus, Delete } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import Crontab from '@/components/Crontab'

const router = useRouter()
const { proxy } = getCurrentInstance()
const { sys_normal_disable } = proxy.useDict('sys_normal_disable')

// 统计信息
const runningJobCount = ref(0)
const stoppedJobCount = ref(0)

const jobList = ref([])
const loading = ref(true)
const showSearch = ref(true)
const total = ref(0)
const openCron = ref(false)
const cronExpression = ref('')

const currentJob = ref(null)
const jobConfigVisible = ref(false)
const jobConfigForm = ref({
  jobName: '',
  durationMinutes: 30,
  cronExpression: '',
  status: '0'
})
const jobConfigRules = {
  jobName: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  durationMinutes: [{ required: true, message: '请输入运行时长', trigger: 'change' }],
  cronExpression: [{ required: true, message: '请输入cron执行表达式', trigger: 'change' }]
}

// 视频选择相关
const videoTableRef = ref(null)
const videoList = ref([])
const videoTotal = ref(0)
const videoLoading = ref(false)
const selectedVideoIds = ref([])
const selectedVideos = ref([])
const videoQueryParams = reactive({
  pageNum: 1,
  pageSize: 5,
  vidName: undefined
})

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    jobName: undefined,
    status: undefined,
    invokeTarget: 'module_task.video_ai.run'
  }
})

const { queryParams } = toRefs(data)

function getJobStatusType(job) {
  if (!job) return 'info'
  return job.status === '0' ? 'success' : 'warning'
}

function getJobStatusText(job) {
  if (!job) return '未配置'
  return job.status === '0' ? '已启用' : '已停用'
}

function getList() {
  loading.value = true
  listJob(queryParams.value).then(response => {
    jobList.value = response.rows || []
    total.value = response.total
    
    // 简单的当前页统计，实际应该从后端获取或忽略
    runningJobCount.value = jobList.value.filter(job => job.status === '0').length
    stoppedJobCount.value = jobList.value.filter(job => job.status === '1').length
    
    loading.value = false
  }).catch(() => {
    loading.value = false
  })
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function resetQuery() {
  proxy.resetForm('queryRef')
  handleQuery()
}

function handleSelectionChange(selection) {
  // 列表选择变化处理
}

function handleJobRun(row) {
  proxy.$modal.confirm('确认要立即执行一次"' + row.jobName + '"的任务吗?').then(() => {
    return runJob(row.jobId, row.jobGroup)
  }).then(() => {
    proxy.$modal.msgSuccess('执行成功')
  }).catch(() => {})
}

function handleJobLog(row) {
  const jobId = row.jobId || 0
  router.push('/monitor/job-log/index/' + jobId)
}

function handleAdd() {
  currentJob.value = null
  jobConfigForm.value = {
    jobName: '',
    durationMinutes: 30,
    cronExpression: '',
    status: '0'
  }
  // 重置视频选择
  if (videoTableRef.value) {
    videoTableRef.value.clearSelection()
  }
  selectedVideoIds.value = []
  selectedVideos.value = []
  videoQueryParams.pageNum = 1
  videoQueryParams.vidName = undefined
  getVideoList()
  jobConfigVisible.value = true
}

function handleJobConfig(row) {
  currentJob.value = row
  jobConfigForm.value = {
    jobName: row.jobName,
    durationMinutes: extractKwarg(row, 'duration_minutes') || 30,
    cronExpression: row.cronExpression || '',
    status: row.status || '0'
  }
  // 初始化视频选择
  if (videoTableRef.value) {
    videoTableRef.value.clearSelection()
  }
  const kwargs = extractKwargs(row)
  // 兼容单个video_id和列表video_ids
  let ids = []
  if (kwargs.video_ids && Array.isArray(kwargs.video_ids)) {
    ids = kwargs.video_ids
  } else if (kwargs.video_id) {
    ids = [kwargs.video_id]
  }
  selectedVideoIds.value = ids
  selectedVideos.value = [] // 先清空，后加载
  
  // 加载已选视频详情
  if (ids.length > 0) {
    Promise.all(ids.map(id => getVideo(id).catch(() => null))).then(results => {
        results.forEach(res => {
            if (res && res.data) {
                const video = res.data
                // 兼容后端可能返回snake_case的情况
                if (!video.vidId && video.vid_id) video.vidId = video.vid_id
                if (!video.vidName && video.vid_name) video.vidName = video.vid_name
                if (!video.vidSerial && video.vid_serial) video.vidSerial = video.vid_serial
                selectedVideos.value.push(video)
            }
        })
    })
  }
  
  videoQueryParams.pageNum = 1
  videoQueryParams.vidName = undefined
  
  getVideoList().then(() => {
    // 数据加载完成后，根据selectedVideoIds设置选中
  })
  
  jobConfigVisible.value = true
}

function getVideoList() {
  videoLoading.value = true
  return listVideo(videoQueryParams).then(response => {
    videoList.value = response.rows || []
    videoTotal.value = response.total
    videoLoading.value = false
    
    // 回显选中状态
    nextTick(() => {
      if (videoTableRef.value) {
        videoList.value.forEach(row => {
          if (selectedVideoIds.value.includes(row.vidId)) {
            videoTableRef.value.toggleRowSelection(row, true)
          }
        })
      }
    })
  })
}

function handleVideoQuery() {
  videoQueryParams.pageNum = 1
  getVideoList()
}

function handleVideoSelect(selection, row) {
  const selected = selection.some(item => item.vidId === row.vidId)
  if (selected) {
    if (!selectedVideoIds.value.includes(row.vidId)) {
      selectedVideoIds.value.push(row.vidId)
      // Avoid duplicates in selectedVideos
      if (!selectedVideos.value.some(v => v.vidId === row.vidId)) {
          selectedVideos.value.push(row)
      }
    }
  } else {
    const index = selectedVideoIds.value.indexOf(row.vidId)
    if (index > -1) {
      selectedVideoIds.value.splice(index, 1)
      const vIndex = selectedVideos.value.findIndex(v => v.vidId === row.vidId)
      if (vIndex > -1) {
          selectedVideos.value.splice(vIndex, 1)
      }
    }
  }
}

function handleVideoSelectAll(selection) {
  const currentIds = videoList.value.map(item => item.vidId)
  if (selection.length > 0) {
    // 全选当前页
    videoList.value.forEach(row => {
      if (!selectedVideoIds.value.includes(row.vidId)) {
        selectedVideoIds.value.push(row.vidId)
        if (!selectedVideos.value.some(v => v.vidId === row.vidId)) {
            selectedVideos.value.push(row)
        }
      }
    })
  } else {
    // 取消全选当前页
    currentIds.forEach(id => {
      const index = selectedVideoIds.value.indexOf(id)
      if (index > -1) {
        selectedVideoIds.value.splice(index, 1)
        const vIndex = selectedVideos.value.findIndex(v => v.vidId === id)
        if (vIndex > -1) {
            selectedVideos.value.splice(vIndex, 1)
        }
      }
    })
  }
}

function handleCloseTag(video) {
  const index = selectedVideoIds.value.indexOf(video.vidId)
  if (index > -1) {
    selectedVideoIds.value.splice(index, 1)
    const vIndex = selectedVideos.value.findIndex(v => v.vidId === video.vidId)
    if (vIndex > -1) {
      selectedVideos.value.splice(vIndex, 1)
    }
    
    // 如果当前表格有这一行，取消勾选
    if (videoTableRef.value) {
      const row = videoList.value.find(v => v.vidId === video.vidId)
      if (row) {
        videoTableRef.value.toggleRowSelection(row, false)
      }
    }
  }
}

function handleDelete(row) {
  proxy.$modal.confirm('确认要删除"' + row.jobName + '"的任务吗?').then(() => {
    return delJob(row.jobId)
  }).then(() => {
    getList()
    proxy.$modal.msgSuccess("删除成功")
  }).catch(() => {})
}

function cancelJobConfig() {
  jobConfigVisible.value = false
  currentJob.value = null
}

function submitJobConfig() {
  proxy.$refs['jobConfigRef'].validate(valid => {
    if (!valid) return
    
    // 解析现有的kwargs并更新
    let kwargs = {}
    try {
      kwargs = currentJob.value && currentJob.value.jobKwargs ? JSON.parse(currentJob.value.jobKwargs) : {}
    } catch (e) {
      kwargs = {}
    }
    kwargs.duration_minutes = jobConfigForm.value.durationMinutes
    kwargs.video_ids = selectedVideoIds.value
    // 保存视频序列号列表
    kwargs.video_serials = selectedVideos.value
        .map(v => v.vidSerial || v.vid_serial)
        .filter(s => s)
    // 清理可能存在的旧参数
    delete kwargs.video_id

    const jobData = {
      jobName: jobConfigForm.value.jobName,
      jobGroup: 'DEFAULT',
      jobExecutor: 'default',
      invokeTarget: 'module_task.video_ai.run',
      cronExpression: jobConfigForm.value.cronExpression,
      misfirePolicy: '1',
      concurrent: '1',
      status: jobConfigForm.value.status,
      jobKwargs: JSON.stringify(kwargs)
    }
    
    if (currentJob.value && currentJob.value.jobId) {
      jobData.jobId = currentJob.value.jobId
      jobData.jobGroup = currentJob.value.jobGroup
      jobData.jobExecutor = currentJob.value.jobExecutor
      jobData.invokeTarget = currentJob.value.invokeTarget
      jobData.misfirePolicy = currentJob.value.misfirePolicy
      jobData.concurrent = currentJob.value.concurrent
      updateJob(jobData).then(() => {
        proxy.$modal.msgSuccess('修改成功')
        jobConfigVisible.value = false
        getList()
      })
    } else {
      addJob(jobData).then(() => {
        proxy.$modal.msgSuccess('新增成功')
        jobConfigVisible.value = false
        getList()
      })
    }
  })
}

function extractKwargs(row) {
  try {
    return row.jobKwargs ? JSON.parse(row.jobKwargs) : {}
  } catch (e) {
    return {}
  }
}

function extractKwarg(row, key) {
  try {
    const obj = row.jobKwargs ? JSON.parse(row.jobKwargs) : {}
    return obj[key]
  } catch (e) {
    return undefined
  }
}

function getVideoCount(row) {
  const kwargs = extractKwargs(row)
  if (kwargs.video_ids && Array.isArray(kwargs.video_ids)) {
    return kwargs.video_ids.length
  }
  if (kwargs.video_id) {
    return 1
  }
  return 0
}

function getVideoContent(row) {
  const kwargs = extractKwargs(row)
  if (kwargs.video_serials && Array.isArray(kwargs.video_serials) && kwargs.video_serials.length > 0) {
    return kwargs.video_serials.join(', ')
  }
  if (kwargs.video_ids && Array.isArray(kwargs.video_ids) && kwargs.video_ids.length > 0) {
    return kwargs.video_ids.join(', ')
  }
  if (kwargs.video_id) {
    return String(kwargs.video_id)
  }
  return ''
}

function handleShowCron() {
  cronExpression.value = jobConfigForm.value.cronExpression
  openCron.value = true
}

function crontabFill(value) {
  jobConfigForm.value.cronExpression = value
}

onMounted(() => {
  getList()
})

onUnmounted(() => {
})
</script>

<style scoped>
.stat-card {
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.stat-content {
  display: flex;
  align-items: center;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
}

.stat-icon .el-icon {
  font-size: 24px;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .stat-card {
    margin-bottom: 10px;
  }
}
</style>
