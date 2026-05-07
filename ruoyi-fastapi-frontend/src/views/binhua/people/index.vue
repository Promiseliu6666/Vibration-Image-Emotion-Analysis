<template>
  <div class="app-container">
    <!-- 搜索区域 -->
    <el-card shadow="never" class="search-wrapper">
      <el-form :inline="true" :model="queryParams">
        <el-form-item label="人员姓名">
          <el-input v-model="queryParams.name" placeholder="请输入姓名" clearable />
        </el-form-item>
        <el-form-item label="分组ID">
          <el-input-number v-model="queryParams.groupId" :min="1" placeholder="分组ID" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
          <el-button icon="Refresh" @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 列表区域 -->
    <el-card shadow="never" class="table-wrapper">
      <template #header>
        <div class="flex justify-between items-center">
          <el-button type="primary" icon="Plus" @click="handleAdd">新增人员</el-button>
          <el-button type="warning" icon="Upload" @click="handleBatchImport">批量导入</el-button>
          <el-button type="success" icon="Camera" @click="handleFaceCompare">人脸比对</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="peopleList">
        <el-table-column label="ID" prop="id" width="80" align="center" />
        <el-table-column label="分组ID" prop="groupId" width="100" align="center" />
        <el-table-column label="人脸照片" width="120" align="center">
          <template #default="scope">
            <el-image
              style="width: 80px; height: 80px; border-radius: 8px;"
              :src="scope.row.pics"
              :preview-src-list="[scope.row.pics]"
              fit="cover"
              preview-teleported
            />
          </template>
        </el-table-column>
        <el-table-column label="姓名" prop="name" align="center" />
        <el-table-column label="创建时间" prop="createdTime" width="180" align="center" />
        <el-table-column label="操作" width="180" align="center">
          <template #default="scope">
            <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)">修改</el-button>
            <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <pagination
        v-if="total > 0"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getList"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="open" :title="title" width="520px" append-to-body>
      <el-form ref="peopleFormRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="分组ID" prop="groupId">
          <el-input-number v-model="form.groupId" :min="1" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="人脸照片" prop="pics">
          <el-upload
            class="avatar-uploader"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleAvatarChange"
            accept="image/jpeg,image/png"
            :limit="1"
          >
            <img v-if="form.pics" :src="form.pics" class="avatar" />
            <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
          </el-upload>
          <div class="el-upload__tip">支持 JPG/PNG，正面清晰人脸照最佳</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog v-model="batchOpen" title="批量导入人员（Excel + ZIP）" width="700px" append-to-body>
      <el-alert
        title="使用说明"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        请准备两个文件：<br>
        1. Excel 文件（必须包含列：姓名、分组ID、照片文件名）<br>
        2. 照片 ZIP 压缩包（把所有照片放在同一文件夹后压缩上传）
      </el-alert>

      <el-form label-width="140px">
        <el-form-item label="Excel 文件" required>
          <el-upload
            class="upload-demo"
            :auto-upload="false"
            :on-change="handleExcelChange"
            :limit="1"
            accept=".xlsx,.xls"
          >
            <el-button type="primary">选择 Excel 文件</el-button>
            <div v-if="batchForm.excelFile" class="upload-tip">已选择：{{ batchForm.excelFile.name }}</div>
          </el-upload>
        </el-form-item>

        <el-form-item label="照片 ZIP 包" required>
          <el-upload
            class="upload-demo"
            :auto-upload="false"
            :on-change="handleZipChange"
            :limit="1"
            accept=".zip"
          >
            <el-button type="primary">选择照片 ZIP 包</el-button>
            <div v-if="batchForm.zipFile" class="upload-tip">已选择：{{ batchForm.zipFile.name }}</div>
          </el-upload>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="batchOpen = false">取消</el-button>
        <el-button type="primary" :loading="batchLoading" @click="submitBatchImport">开始导入</el-button>
      </template>
    </el-dialog>

    <!-- 人脸比对对话框 -->
    <el-dialog v-model="compareOpen" title="人脸比对" width="680px" append-to-body>
      <el-form label-width="100px">
        <el-form-item label="分组ID">
          <el-input-number v-model="compareForm.groupId" :min="1" style="width: 200px" />
        </el-form-item>
        <el-form-item label="相似度阈值">
          <el-input-number v-model="compareForm.threshold" :min="0" :max="1" :step="0.01" style="width: 200px" />
          <span style="margin-left: 10px; color: #666;">（推荐 0.7）</span>
        </el-form-item>

        <el-form-item label="比对照片">
          <el-upload
            class="compare-uploader"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleCompareImageChange"
            accept="image/jpeg,image/png"
            :limit="1"
          >
            <img v-if="compareForm.image" :src="compareForm.image" class="compare-avatar" />
            <div v-else class="upload-placeholder">
              <el-icon style="font-size: 36px; margin-bottom: 8px"><Plus /></el-icon>
              <div>点击上传比对照片</div>
            </div>
          </el-upload>
          <div class="el-upload__tip">支持 JPG/PNG，正面清晰人脸照</div>
        </el-form-item>
      </el-form>

      <div v-if="compared" class="compare-results">
        <div v-if="compareResult.length > 0">
          <div class="result-item" v-for="(item, index) in compareResult" :key="index">
            <el-image
              style="width: 80px; height: 80px; border-radius: 8px; flex-shrink: 0;"
              :src="item.pics"
              fit="cover"
            />
            <div class="info">
              <div><strong>姓名：</strong>{{ item.name || '未知' }}</div>
              <div><strong>分组ID：</strong>{{ item.group_id || item.groupId }}</div>
              <div><strong>相似度：</strong>
                <span :style="{ color: (item.similarity || item.score || 0) >= compareForm.threshold ? '#67C23A' : '#E6A23C' }">
                  {{ ((item.similarity || item.score || 0) * 100).toFixed(2) }}%
                </span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="no-result">未找到匹配的人员（相似度低于阈值）</div>
      </div>

      <template #footer>
        <el-button @click="compareOpen = false">关闭</el-button>
        <el-button type="primary" :loading="compareLoading" @click="doFaceCompare">单张比对</el-button>
        <el-button type="success" :loading="compareLoading" @click="doFaceCompareAll">全库比对</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, toRefs } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listPeople,
  addPeople,
  updatePeople,
  delPeople,
  batchImportPeople,
  faceCompare,
  faceCompareAll
} from '@/api/binhua/people'

const loading = ref(false)
const compareLoading = ref(false)
const batchLoading = ref(false)
const total = ref(0)
const peopleList = ref([])

const open = ref(false)
const batchOpen = ref(false)
const compareOpen = ref(false)
const title = ref('')
const submitLoading = ref(false)

const peopleFormRef = ref(null)

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    name: undefined,
    groupId: undefined
  }
})
const { queryParams } = toRefs(data)

const form = reactive({
  id: undefined,
  groupId: undefined,
  name: '',
  pics: ''          // Base64 字符串（用于预览和提交）
})

const batchForm = reactive({
  excelFile: null,
  zipFile: null
})

const compareForm = reactive({
  groupId: 1,
  threshold: 0.7,
  image: ''
})

const compareResult = ref([])
const compared = ref(false)

const rules = {
  groupId: [{ required: true, message: '分组ID不能为空', trigger: 'change' }],
  name: [{ required: true, message: '姓名不能为空', trigger: 'blur' }],
  pics: [{ required: true, message: '请上传人脸照片', trigger: 'change' }]
}

// 获取人员列表
const getList = async () => {
  loading.value = true
  try {
    const res = await listPeople(queryParams.value)
    const rows = res.data?.rows || res.data?.records || []
    total.value = res.data?.total || 0
    peopleList.value = rows
  } catch (err) {
    ElMessage.error(err.msg || '获取列表失败')
  } finally {
    loading.value = false
  }
}

const handleQuery = () => {
  queryParams.value.pageNum = 1
  getList()
}

const resetQuery = () => {
  queryParams.value.name = undefined
  queryParams.value.groupId = undefined
  handleQuery()
}

// 新增
const handleAdd = () => {
  resetForm()
  title.value = '添加人员'
  open.value = true
}

// 修改
const handleUpdate = (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    groupId: row.groupId,
    name: row.name,
    pics: row.pics
  })
  title.value = '修改人员'
  open.value = true
}

// 图片转 Base64
const handleAvatarChange = (file) => {
  const reader = new FileReader()
  reader.onload = () => {
    form.pics = reader.result
  }
  reader.readAsDataURL(file.raw)
}

// 提交新增/修改（关键修复）
const submitForm = async () => {
  if (!peopleFormRef.value) return

  peopleFormRef.value.validate(async (valid) => {
    if (!valid) return

    if (!form.id && !form.pics) {
      ElMessage.warning('请上传人脸照片')
      return
    }

    submitLoading.value = true

    // 后端 PeopleModel 使用 to_camel，字段应传 groupId
    const submitData = {
      groupId: form.groupId,
      name: form.name,
      pics: form.pics
    }

    console.log('=== 发送给后端的 JSON 数据 ===', submitData)

    try {
      let res
      if (form.id) {
        res = await updatePeople(form.id, submitData)
      } else {
        res = await addPeople(submitData)
      }

      ElMessage.success(form.id ? '修改成功' : '添加成功')
      open.value = false
      getList()
    } catch (err) {
      console.error('提交失败完整信息：', err)
      if (err.response?.data) {
        const detail = err.response.data.detail
        const errorMsg = Array.isArray(detail) 
          ? (detail[0]?.msg || JSON.stringify(detail))
          : (err.response.data.msg || '操作失败')
        ElMessage.error(errorMsg)
      } else {
        ElMessage.error(err.msg || '操作失败')
      }
    } finally {
      submitLoading.value = false
    }
  })
}

// 重置表单
const resetForm = () => {
  form.id = undefined
  form.groupId = undefined
  form.name = ''
  form.pics = ''
  peopleFormRef.value?.resetFields()
}

// ==================== 批量导入（保持原样） ====================
const handleBatchImport = () => {
  batchForm.excelFile = null
  batchForm.zipFile = null
  batchOpen.value = true
}

const handleExcelChange = (file) => { batchForm.excelFile = file.raw }
const handleZipChange = (file) => { batchForm.zipFile = file.raw }

const submitBatchImport = async () => {
  if (!batchForm.excelFile || !batchForm.zipFile) {
    ElMessage.warning('请同时选择 Excel 文件和照片 ZIP 包')
    return
  }

  batchLoading.value = true
  const formData = new FormData()
  formData.append('excel_file', batchForm.excelFile)
  formData.append('images_zip', batchForm.zipFile)

  try {
    const res = await batchImportPeople(formData)
    if (res.code === 200) {
      ElMessage.success(res.msg || '批量导入成功')
      batchOpen.value = false
      getList()
    }
  } catch (err) {
    ElMessage.error(err.msg || '导入失败')
  } finally {
    batchLoading.value = false
  }
}

// ==================== 人脸比对 ====================
const handleFaceCompare = () => {
  compareOpen.value = true
  compareResult.value = []
  compared.value = false
  compareForm.groupId = 1
  compareForm.threshold = 0.7
  compareForm.image = ''
}

const handleCompareImageChange = (file) => {
  const reader = new FileReader()
  reader.onload = () => { compareForm.image = reader.result }
  reader.readAsDataURL(file.raw)
}

const doFaceCompare = async () => await doCompare(faceCompare)
const doFaceCompareAll = async () => await doCompare(faceCompareAll)

const doCompare = async (apiFn) => {
  if (!compareForm.image) {
    ElMessage.warning('请先上传比对照片')
    return
  }
  compareLoading.value = true
  compared.value = true
  try {
    const res = await apiFn(compareForm)
    if (res.code === 200) {
      const data = res.data || []
      compareResult.value = Array.isArray(data) ? data : data ? [data] : []
      ElMessage.success(res.msg || '比对完成')
    }
  } catch (err) {
    ElMessage.error(err.msg || '比对失败')
    compareResult.value = []
  } finally {
    compareLoading.value = false
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确认删除 "${row.name}" 吗？`, '警告', { type: 'warning' })
    .then(async () => {
      await delPeople(row.id)
      ElMessage.success('删除成功')
      getList()
    })
}

onMounted(() => {
  getList()
})
</script>

<style scoped>
.app-container { padding: 20px; }
.search-wrapper { margin-bottom: 20px; }

.avatar-uploader .avatar,
.compare-avatar {
  width: 178px;
  height: 178px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid #ebeef5;
}

.avatar-uploader-icon,
.upload-placeholder {
  width: 178px;
  height: 178px;
  border: 1px dashed #d9d9d9;
  border-radius: 10px;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #8c939d;
  cursor: pointer;
}

.compare-results {
  margin-top: 20px;
  max-height: 420px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.result-item:last-child {
  border-bottom: none;
}

.no-result {
  text-align: center;
  color: #999;
  padding: 60px 20px;
  font-size: 15px;
}

.upload-tip {
  margin-top: 8px;
  color: #67C23A;
  font-size: 14px;
}

.el-upload__tip {
  margin-top: 8px;
  font-size: 13px;
  color: #666;
}
</style>
