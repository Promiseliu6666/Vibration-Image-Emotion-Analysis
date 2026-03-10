<template>
  <div class="analysis-container">
    <el-card class="search-card">
      <el-form :inline="true" :model="queryParams" label-width="100px">
        <el-form-item label="人员ID">
          <el-input v-model.number="queryParams.personId" placeholder="输入人员ID" clearable />
        </el-form-item>
        <el-form-item label="视频来源">
          <el-input v-model="queryParams.source" placeholder="输入视频来源（模糊）" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span>分析记录列表</span>
          <div>
            <el-button type="primary" @click="handleAdd">新增记录</el-button>
            <el-button type="danger" :disabled="!multipleSelection.length" @click="handleBatchDelete">
              批量删除
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
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="source" label="视频来源" />
        <el-table-column prop="personName" label="人名" />
        <el-table-column prop="personId" label="人员ID" width="100" />
        <el-table-column prop="happinessIndex" label="幸福指数" width="120" sortable />
        <el-table-column prop="happinessLevel" label="幸福等级" width="120" />
        <el-table-column prop="safetyRisk" label="安全风险" />
        <el-table-column prop="createTime" label="创建时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDate(row.createTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
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

    <!-- 添加/编辑对话框 -->
    <el-dialog
      :title="dialogTitle"
      v-model="dialogVisible"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form ref="analysisFormRef" :model="formData" :rules="rules" label-width="120px">
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
          <el-input-number v-model="formData.happinessIndex" :precision="2" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="幸福等级">
          <el-input v-model="formData.happinessLevel" placeholder="如：高/中/低" />
        </el-form-item>
        <el-form-item label="安全风险">
          <el-input v-model="formData.safetyRisk" placeholder="描述安全风险" />
        </el-form-item>
        <!-- e1~e10 字段可根据需要展开，这里暂不全部展示，可折叠或分tab -->
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
          <el-descriptions-item label="视频来源">{{ detailData.source }}</el-descriptions-item>
          <el-descriptions-item label="人名">{{ detailData.personName }}</el-descriptions-item>
          <el-descriptions-item label="人员ID">{{ detailData.personId }}</el-descriptions-item>
          <el-descriptions-item label="幸福指数">{{ detailData.happinessIndex }}</el-descriptions-item>
          <el-descriptions-item label="幸福等级">{{ detailData.happinessLevel }}</el-descriptions-item>
          <el-descriptions-item label="安全风险" :span="2">{{ detailData.safetyRisk }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(detailData.createTime) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, toRefs } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Pagination from '@/components/Pagination/index.vue' // 假设有通用分页组件

import {
  listAnalysis,
  addAnalysis,
  updateAnalysis,
  delAnalysis,
  batchDelAnalysis,
  getAnalysis // 用于编辑时获取最新数据（可选）
} from '@/api/binhua/analysis.js' // 请根据你的项目路径调整（如 '@/api/analysis.js'）

// 类型定义（与后端VO对应，camelCase）
interface AnalysisItem {
  id?: number
  source: string
  personName: string
  personId?: number
  happinessIndex: number
  happinessLevel?: string
  safetyRisk?: string
  createTime?: string
  // e1~e10 等其他字段可后续补充
}

// 数据定义（与用户管理页面一致，使用 reactive + toRefs 确保 v-model 和分页绑定正确）
const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    personId: null as number | null,
    source: null as string | null,
  }
})

const { queryParams } = toRefs(data)

// 表格数据
const analysisList = ref<AnalysisItem[]>([])
const total = ref(0)
const loading = ref(false)
const multipleSelection = ref<AnalysisItem[]>([])

// 表单相关
const dialogVisible = ref(false)
const dialogTitle = ref('')
const isEdit = ref(false)
const formData = reactive<AnalysisItem>({
  source: '',
  personName: '',
  personId: undefined,
  happinessIndex: 0,
  happinessLevel: '',
  safetyRisk: '',
})

// 详情相关
const drawerVisible = ref(false)
const detailData = ref<AnalysisItem | null>(null)

// 表单校验规则
const rules = {
  source: [{ required: true, message: '请输入视频来源', trigger: 'blur' }],
  personName: [{ required: true, message: '请输入人名', trigger: 'blur' }],
}

// 获取列表
const getList = async () => {
  console.log('──── getList 被调用 ────')
  console.log('当前页码 pageNum:', queryParams.value.pageNum)
  console.log('当前条数 pageSize:', queryParams.value.pageSize)
  console.log('查询条件 personId:', queryParams.value.personId, 'source:', queryParams.value.source)
  loading.value = true
  try {
    const res = await listAnalysis({
      pageNum: queryParams.value.pageNum,
      pageSize: queryParams.value.pageSize,
      personId: queryParams.value.personId,
      source: queryParams.value.source,
    })

    // === 调试日志（上线前可删除）===
    console.log('【完整响应】', res)
    console.log('【res.data】', res.data)

    // === 通用解析：自动尝试常见字段 ===
    let records = []
    let totalNum = 0

    if (res.data) {
      // 优先尝试 records → rows → list → data（嵌套） → 直接数组
      records = 
        res.data.records ?? 
        res.data.rows ?? 
        res.data.list ?? 
        res.data.data?.records ?? 
        res.data.data?.rows ?? 
        res.data.data?.list ?? 
        res.data.data ?? 
        res.data ?? 
        []

      totalNum = 
        res.data.total ?? 
        res.data.data?.total ?? 
        0
    } else if (Array.isArray(res)) {
      // 极少数情况直接返回数组
      records = res
      totalNum = res.length
    }

    analysisList.value = records
    total.value = totalNum

    // 如果还是空，可以在这里提示
    if (records.length === 0) {
      console.warn('列表数据为空，请检查后端返回结构是否在以上兼容范围内')
    }

  } catch (error: any) {
    ElMessage.error(error.msg || '获取列表失败')
  } finally {
    loading.value = false
  }
}

// 查询
const handleQuery = () => {
  queryParams.value.pageNum = 1
  getList()
}

// 重置
const resetQuery = () => {
  queryParams.value.personId = null
  queryParams.value.source = null
  handleQuery()
}

// 多选
const handleSelectionChange = (val: AnalysisItem[]) => {
  multipleSelection.value = val
}

// 新增
const handleAdd = () => {
  Object.assign(formData, {
    source: '',
    personName: '',
    personId: undefined,
    happinessIndex: 0,
    happinessLevel: '',
    safetyRisk: '',
  })
  isEdit.value = false
  dialogTitle.value = '新增分析记录'
  dialogVisible.value = true
}

// 编辑（先获取最新数据回显，确保与其他用户修改同步）
const handleEdit = async (row: AnalysisItem) => {
  try {
    const res = await getAnalysis(row.id!)
    Object.assign(formData, res.data) // 假设返回 { code: 200, data: {...} }
    isEdit.value = true
    dialogTitle.value = '编辑分析记录'
    dialogVisible.value = true
  } catch (error: any) {
    ElMessage.error(error.msg || '获取详情失败')
  }
}

// 查看详情（直接用行数据）
const handleView = (row: AnalysisItem) => {
  detailData.value = { ...row }
  drawerVisible.value = true
}

// 删除
const handleDelete = async (row: AnalysisItem) => {
  await ElMessageBox.confirm('确认删除该记录？', '警告', { type: 'warning' })
  try {
    await delAnalysis(row.id!)
    ElMessage.success('删除成功')
    getList()
  } catch (error: any) {
    ElMessage.error(error.msg || '删除失败')
  }
}

// 批量删除
const handleBatchDelete = async () => {
  const ids = multipleSelection.value.map(item => item.id).join(',')
  if (!ids) return
  await ElMessageBox.confirm('确认批量删除选中记录？', '警告', { type: 'warning' })
  try {
    await batchDelAnalysis({ analysisIds: ids })
    ElMessage.success('批量删除成功')
    getList()
  } catch (error: any) {
    ElMessage.error(error.msg || '批量删除失败')
  }
}

// 提交表单
const submitForm = async () => {
  try {
    if (isEdit.value && formData.id) {
      await updateAnalysis(formData.id, formData)
      ElMessage.success('修改成功')
    } else {
      await addAnalysis(formData)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    getList()
  } catch (error: any) {
    ElMessage.error(error.msg || (isEdit.value ? '修改失败' : '新增失败'))
  }
}

// 时间格式化
const formatDate = (date: string) => {
  return date ? new Date(date).toLocaleString() : '-'
}

onMounted(() => {
  getList()
})
</script>

<style scoped>
.analysis-container {
  padding: 20px;
}
.search-card {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.table-card {
  margin-bottom: 20px;
}

/* 匹配用户管理页面的分页样式 */
.pagination-center {
  margin: 24px 0;
  text-align: center;
}
</style>