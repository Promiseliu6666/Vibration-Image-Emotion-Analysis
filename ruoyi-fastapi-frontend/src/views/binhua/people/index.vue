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

    <!-- 列表与操作 -->
    <el-card shadow="never" class="table-wrapper">
      <template #header>
        <div class="flex justify-between items-center">
          <el-button type="primary" icon="Plus" @click="handleAdd">新增人员</el-button>
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
        v-show="total > 0"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getList"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="open" :title="title" width="500px" append-to-body>
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

    <!-- 人脸比对对话框 -->
    <el-dialog v-model="compareOpen" title="人脸比对" width="600px" append-to-body>
      <el-form label-width="100px">
        <el-form-item label="分组ID" required>
          <el-input-number v-model="compareForm.groupId" :min="1" style="width: 200px" />
        </el-form-item>
        <el-form-item label="比对阈值">
          <el-slider v-model="compareForm.threshold" :min="0.1" :max="1" :step="0.05" show-input style="width: 300px" />
        </el-form-item>
        <el-form-item label="上传照片">
          <el-upload
            class="compare-uploader"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleCompareImageChange"
            accept="image/jpeg,image/png"
          >
            <img v-if="compareForm.image" :src="compareForm.image" class="compare-avatar" />
            <div v-else class="upload-placeholder">
              <el-icon><UploadFilled /></el-icon>
              <div>点击上传人脸照片</div>
            </div>
          </el-upload>
        </el-form-item>
      </el-form>

      <!-- 比对结果 -->
      <div v-if="compareResult.length > 0" class="compare-results">
        <h4>匹配结果（按相似度排序）</h4>
        <div v-for="item in compareResult" :key="item.id" class="result-item">
          <el-image :src="item.pics" style="width: 100px; height: 100px;" fit="cover" />
          <div class="info">
            <p><strong>姓名：</strong>{{ item.name }}</p>
            <p><strong>ID：</strong>{{ item.id }}</p>
            <p><strong>相似度：</strong><el-tag type="success">{{ (item.similarity * 100).toFixed(2) }}%</el-tag></p>
          </div>
        </div>
      </div>
      <div v-else-if="compared" class="no-result">未找到匹配人员</div>

      <template #footer>
        <el-button @click="compareOpen = false">关闭</el-button>
        <el-button type="primary" :loading="compareLoading" :disabled="!compareForm.image" @click="doFaceCompareAll">
          开始比对（显示全部）
        </el-button>
        <el-button type="success" :loading="compareLoading" :disabled="!compareForm.image" @click="doFaceCompare">
          比对（仅最相似）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listPeople,
  addPeople,
  updatePeople,
  delPeople,
  faceCompare,
  faceCompareAll
} from '@/api/binhua/people' // 请确保路径正确

const loading = ref(false)
const total = ref(0)
const peopleList = ref([])
const open = ref(false)
const compareOpen = ref(false)
const title = ref('')
const submitLoading = ref(false)
const compareLoading = ref(false)
const compared = ref(false)

const peopleFormRef = ref(null)

const queryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  name: undefined,
  groupId: undefined
})

const form = reactive({
  id: undefined,
  groupId: undefined,
  name: '',
  pics: ''
})

const compareForm = reactive({
  groupId: 1,
  threshold: 0.7,
  image: ''
})

const compareResult = ref([])

const rules = {
  groupId: [{ required: true, message: '分组ID不能为空', trigger: 'change' }],
  name: [{ required: true, message: '姓名不能为空', trigger: 'blur' }],
  pics: [{ required: true, message: '请上传人脸照片', trigger: 'change' }]
}

// 获取列表
const getList = async () => {
  loading.value = true
  try {
    const res = await listPeople(queryParams)
    peopleList.value = res.data.rows || res.data
    total.value = res.data.total || 0
  } finally {
    loading.value = false
  }
}

// 搜索与重置
const handleQuery = () => {
  queryParams.pageNum = 1
  getList()
}
const resetQuery = () => {
  queryParams.name = undefined
  queryParams.groupId = undefined
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

// 图片上传转base64
const handleAvatarChange = (file) => {
  const reader = new FileReader()
  reader.onload = () => {
    form.pics = reader.result
  }
  reader.readAsDataURL(file.raw)
}

// 人脸比对图片上传
const handleCompareImageChange = (file) => {
  const reader = new FileReader()
  reader.onload = () => {
    compareForm.image = reader.result
  }
  reader.readAsDataURL(file.raw)
}

// 提交表单
const submitForm = () => {
  peopleFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitLoading.value = true
    try {
      if (form.id) {
        await updatePeople(form.id, form)
        ElMessage.success('修改成功')
      } else {
        await addPeople(form)
        ElMessage.success('添加成功')
      }
      open.value = false
      getList()
    } catch (err) {
      ElMessage.error(err.msg || '操作失败')
    } finally {
      submitLoading.value = false
    }
  })
}

// 删除
const handleDelete = (row) => {
  ElMessageBox.confirm(`确认删除人员 "${row.name}" 吗？`, '警告', { type: 'warning' }).then(async () => {
    await delPeople(row.id)
    ElMessage.success('删除成功')
    getList()
  })
}

// 重置表单
const resetForm = () => {
  form.id = undefined
  form.groupId = undefined
  form.name = ''
  form.pics = ''
  if (peopleFormRef.value) peopleFormRef.value.resetFields()
}

// 人脸比对相关
const handleFaceCompare = () => {
  compareOpen.value = true
  compareResult.value = []
  compared.value = false
  compareForm.groupId = 1
  compareForm.threshold = 0.7
  compareForm.image = ''
}

const doFaceCompare = async () => {
  await doCompare('/face-compare')
}

const doFaceCompareAll = async () => {
  await doCompare('/face-compare-all')
}

const doCompare = async (path) => {
  if (!compareForm.image) {
    ElMessage.warning('请上传比对照片')
    return
  }
  compareLoading.value = true
  compared.value = true
  try {
    const res = path === '/face-compare'
      ? await faceCompare(compareForm)
      : await faceCompareAll(compareForm)

    if (res.code === 200) {
      const data = res.data
      if (Array.isArray(data)) {
        compareResult.value = data
      } else if (data && data.id) {
        compareResult.value = [data]
      } else {
        compareResult.value = []
      }
      ElMessage.success(res.msg || '比对完成')
    }
  } catch (err) {
    ElMessage.error(err.msg || '比对失败')
  } finally {
    compareLoading.value = false
  }
}

onMounted(() => {
  getList()
})
</script>

<style scoped>
.search-wrapper { margin-bottom: 20px; }
.avatar-uploader .avatar {
  width: 178px;
  height: 178px;
  display: block;
  object-fit: cover;
  border-radius: 10px;
}
.avatar-uploader-icon {
  font-size: 32px;
  color: #8c939d;
  width: 178px;
  height: 178px;
  line-height: 178px;
  text-align: center;
  border: 1px dashed #d9d9d9;
  border-radius: 10px;
  background: #fafafa;
}
.compare-uploader .compare-avatar {
  width: 200px;
  height: 200px;
  border-radius: 10px;
}
.upload-placeholder {
  width: 200px;
  height: 200px;
  border: 2px dashed #dcdfe6;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #8c939d;
  cursor: pointer;
}
.compare-results {
  margin-top: 20px;
  max-height: 400px;
  overflow-y: auto;
}
.result-item {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}
.result-item .info {
  flex: 1;
}
.no-result {
  text-align: center;
  color: #999;
  padding: 40px 0;
}
</style>