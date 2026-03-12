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

    <!-- 幸福等级分布饼图 -->
    <el-card class="chart-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>幸福等级分布（当前筛选条件）</span>
        </div>
      </template>
      <div ref="happinessChart" class="chart-container" />
    </el-card>

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
        <el-table-column prop="happinessLevel" label="幸福等级" width="120" align="center" />
        <el-table-column prop="safetyRisk" label="安全风险" min-width="160" show-overflow-tooltip />
        <el-table-column prop="createTime" label="创建时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDate(row.createTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right" align="center">
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
            :max="1"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="幸福等级">
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
    <el-drawer v-model="drawerVisible" title="分析记录详情" size="50%" direction="rtl">
      <div v-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ detailData.id }}</el-descriptions-item>
          <el-descriptions-item label="视频来源">{{ detailData.source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="人名">{{ detailData.personName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="人员ID">{{ detailData.personId || '-' }}</el-descriptions-item>
          <el-descriptions-item label="幸福指数">{{ detailData.happinessIndex || '-' }}</el-descriptions-item>
          <el-descriptions-item label="幸福等级">{{ detailData.happinessLevel || '-' }}</el-descriptions-item>
          <el-descriptions-item label="安全风险">{{ detailData.safetyRisk || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(detailData.createTime) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-drawer>

    <!-- 导出对话框（可重新选择筛选条件） -->
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
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  listAnalysis,
  getAnalysis,
  addAnalysis,
  updateAnalysis,
  delAnalysis,
  batchDelAnalysis,
  exportAnalysis
} from '@/api/binhua/analysis' // 请根据实际路径调整

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
  happinessIndex: [{ required: true, message: '请输入幸福指数', trigger: 'blur' }]
}

const drawerVisible = ref(false)
const detailData = ref(null)

const happinessChart = ref(null)
let chartInstance = null

// 导出对话框相关
const exportDialogVisible = ref(false)
const exportFileName = ref('')
const queryParamsExport = ref({
  personId: null,
  personName: '',
  source: '',
  startTime: '',
  endTime: ''
})

const getLevelCount = () => {
  const count = { 高: 0, 中: 0, 低: 0, 未知: 0 }
  analysisList.value.forEach(item => {
    const level = item.happinessLevel
    if (level in count) count[level]++
    else count.未知++
  })
  return count
}

const getChartOption = () => {
  const levelCount = getLevelCount()
  const totalCount = analysisList.value.length || 1
  const data = [
    { value: levelCount.高, name: `高 (${((levelCount.高 / totalCount) * 100).toFixed(1)}%)` },
    { value: levelCount.中, name: `中 (${((levelCount.中 / totalCount) * 100).toFixed(1)}%)` },
    { value: levelCount.低, name: `低 (${((levelCount.低 / totalCount) * 100).toFixed(1)}%)` },
    { value: levelCount.未知, name: `未知 (${((levelCount.未知 / totalCount) * 100).toFixed(1)}%)` }
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

const initChart = () => {
  if (!happinessChart.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(happinessChart.value, 'macarons')
  chartInstance.setOption(getChartOption())
}

const resizeHandler = () => {
  chartInstance?.resize()
}

watch(analysisList, () => {
  if (chartInstance) chartInstance.setOption(getChartOption())
}, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', resizeHandler)
  getList()
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeHandler)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

const getList = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: queryParams.value.pageNum,
      pageSize: queryParams.value.pageSize
    }

    if (queryParams.value.personId != null) params.personId = queryParams.value.personId
    if (queryParams.value.personName.trim()) params.personName = queryParams.value.personName.trim()
    if (queryParams.value.source.trim()) params.source = queryParams.value.source.trim()
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

const handleView = (row) => {
  detailData.value = { ...row }
  drawerVisible.value = true
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

const formatDate = (date) => {
  if (!date) return '-'
  try {
    let parsedDate
    if (!isNaN(Number(date))) {
      parsedDate = new Date(Number(date))
    } else {
      parsedDate = new Date(date.replace('T', ' '))
    }
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

// 导出相关
const openExportDialog = () => {
  // 预填当前查询条件
  queryParamsExport.value = {
    personId: queryParams.value.personId,
    personName: queryParams.value.personName,
    source: queryParams.value.source,
    startTime: queryParams.value.startTime,
    endTime: queryParams.value.endTime
  }

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

// 假设你有 proxy（setup 中常见写法）
const proxy = getCurrentInstance()?.proxy

const confirmExport = () => {
  exportDialogVisible.value = false
  exportLoading.value = true

  const params = {
    pageNum: 1,
    pageSize: 999999,
  }

  if (queryParamsExport.value.personId != null) {
    params.personId = queryParamsExport.value.personId
  }
  if (queryParamsExport.value.personName?.trim()) {
    params.personName = queryParamsExport.value.personName.trim()
  }
  if (queryParamsExport.value.source?.trim()) {
    params.source = queryParamsExport.value.source.trim()
  }
  if (queryParamsExport.value.startTime) {
    params.startTime = queryParamsExport.value.startTime + ' 00:00:00'
  }
  if (queryParamsExport.value.endTime) {
    params.endTime = queryParamsExport.value.endTime + ' 23:59:59'
  }

  const filename = (exportFileName.value || '幸福分析记录') + '.xlsx'

  // ──────────────── 关键调用 ────────────────
  proxy.download('/analysis/export', params, filename)
    .then(() => {
      ElMessage.success('导出成功')
    })
    .catch(err => {
      console.error('导出失败', err)
      ElMessage.error('导出失败，请查看控制台或后端日志')
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
.chart-card {
  margin-bottom: 20px;
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
</style>