<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="算法名称" prop="algName">
        <el-input
          v-model="queryParams.algName"
          placeholder="请输入算法名称"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="算法版本" prop="algVersion">
        <el-input
          v-model="queryParams.algVersion"
          placeholder="请输入算法版本"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="openEditDialog()">新增算法</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="success" plain icon="Upload" @click="openUploadDialog">上传权重版本</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table
      v-loading="loading"
      :data="algorithmList"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="序号" type="index" width="80" align="center">
        <template #default="scope">
          <span>{{ (queryParams.pageNum - 1) * queryParams.pageSize + scope.$index + 1 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="算法名称" align="center" prop="algName" :show-overflow-tooltip="true" />
      <el-table-column label="算法编号" align="center" prop="algSerial" :show-overflow-tooltip="true" />
      <el-table-column label="算法版本" align="center" prop="algVersion" :show-overflow-tooltip="true" />
      <el-table-column label="运行位置" align="center" prop="algRuntimeType" width="110">
        <template #default="scope">
          <el-tag :type="scope.row.algRuntimeType === 'local' ? 'success' : 'warning'">
            {{ runtimeTypeLabel(scope.row.algRuntimeType) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="权重文件" align="center" prop="algWeightPath" :show-overflow-tooltip="true" />
      <el-table-column label="状态" align="center" prop="algEnabled" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.algEnabled ? 'success' : 'info'">
            {{ scope.row.algEnabled ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="默认配置" align="center" prop="algDefaultConf" :show-overflow-tooltip="true">
        <template #default="scope">
          <span>{{ formatConfigPreview(scope.row.algDefaultConf) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width" width="240">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="showSceneDetail(scope.row)">详情</el-button>
          <el-button link type="primary" icon="Edit" @click="openEditDialog(scope.row)">编辑</el-button>
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

    <el-dialog v-model="editDialogVisible" :title="editForm.algId ? '编辑算法' : '新增算法'" width="620px" destroy-on-close>
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="算法名称"><el-input v-model="editForm.algName" /></el-form-item>
        <el-form-item label="算法编号"><el-input v-model="editForm.algSerial" /></el-form-item>
        <el-form-item label="算法版本"><el-input v-model="editForm.algVersion" /></el-form-item>
        <el-form-item label="运行位置">
          <el-select v-model="editForm.algRuntimeType" style="width: 100%">
            <el-option label="本地" value="local" />
            <el-option label="盒子" value="external_box" />
          </el-select>
        </el-form-item>
        <el-form-item label="权重路径"><el-input v-model="editForm.algWeightPath" /></el-form-item>
        <el-form-item label="启用状态"><el-switch v-model="editForm.algEnabled" /></el-form-item>
        <el-form-item label="默认配置"><el-input v-model="editForm.algDefaultConfText" type="textarea" :rows="6" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传算法权重版本" width="620px" destroy-on-close>
      <el-form :model="uploadForm" label-width="110px">
        <el-form-item label="算法名称"><el-input v-model="uploadForm.algName" /></el-form-item>
        <el-form-item label="算法编号"><el-input v-model="uploadForm.algSerial" /></el-form-item>
        <el-form-item label="算法版本"><el-input v-model="uploadForm.algVersion" /></el-form-item>
        <el-form-item label="运行位置">
          <el-select v-model="uploadForm.algRuntimeType" style="width: 100%">
            <el-option label="本地" value="local" />
            <el-option label="盒子" value="external_box" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认配置"><el-input v-model="uploadForm.algDefaultConf" type="textarea" :rows="5" /></el-form-item>
        <el-form-item label="权重文件">
          <el-upload ref="uploadRef" :auto-upload="false" :limit="1" :on-change="handleWeightSelected" :on-remove="handleWeightRemoved">
            <el-button type="primary">选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-progress v-if="uploadProgress > 0" :percentage="uploadProgress" />
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitWeightUpload">上传并创建版本</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailDialogVisible"
      :title="`算法详情: ${detailAlgorithm?.algName || ''}`"
      width="700px"
      destroy-on-close
    >
      <el-descriptions v-if="detailAlgorithm" :column="1" border>
        <el-descriptions-item label="算法名称">{{ detailAlgorithm.algName }}</el-descriptions-item>
        <el-descriptions-item label="算法编号">{{ detailAlgorithm.algSerial }}</el-descriptions-item>
        <el-descriptions-item label="算法版本">{{ detailAlgorithm.algVersion }}</el-descriptions-item>
        <el-descriptions-item label="运行位置">{{ runtimeTypeLabel(detailAlgorithm.algRuntimeType) }}</el-descriptions-item>
        <el-descriptions-item label="默认配置">
          <pre class="detail-json">{{ prettyJson(detailAlgorithm.algDefaultConf) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup name="Algorithm">
import { ref, reactive, toRefs, getCurrentInstance, onMounted } from 'vue'
import { listAlgorithm, delAlgorithm, addAlgorithm, updateAlgorithm, uploadAlgorithmWeight } from '@/api/xuzhou/algorithm'
import { listVideo } from '@/api/xuzhou/video'

const { proxy } = getCurrentInstance()

const queryRef = ref()
const algorithmList = ref([])
const loading = ref(true)
const showSearch = ref(true)
const ids = ref([])
const single = ref(true)
const multiple = ref(true)
const total = ref(0)
const detailDialogVisible = ref(false)
const editDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const uploadRef = ref()
const uploadFile = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const detailAlgorithm = ref(null)

const editForm = reactive({
  algId: undefined,
  algName: '',
  algSerial: '',
  algVersion: '',
  algWeightPath: '',
  algRuntimeType: 'external_box',
  algEnabled: true,
  algDefaultConfText: '{}'
})
const uploadForm = reactive({
  algName: '',
  algSerial: '',
  algVersion: '',
  algRuntimeType: 'external_box',
  algDefaultConf: '{}'
})

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    algName: undefined,
    algVersion: undefined
  }
})

const { queryParams } = toRefs(data)

function parseJson(value) {
  if (!value) return {}
  if (typeof value === 'object') return value
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      return {}
    }
  }
  return {}
}

function normalizeAlgorithmList(value) {
  if (!value) return []
  if (Array.isArray(value)) return value
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
}

function runtimeTypeLabel(runtimeType) {
  return runtimeType === 'local' ? '本地' : '盒子'
}

function formatConfigPreview(value) {
  const conf = parseJson(value)
  const keys = Object.keys(conf)
  if (!keys.length) return '-'
  return keys.slice(0, 2).map(key => `${key}: ${typeof conf[key] === 'object' ? '[...]' : conf[key]}`).join('，')
}

function prettyJson(value) {
  const conf = parseJson(value)
  return JSON.stringify(conf, null, 2)
}

function cameraHasAlgorithm(camera, algId) {
  return normalizeAlgorithmList(camera.vidAlgorithm).some(item => Number(item.algId) === Number(algId))
}

/** 查询算法列表 */
function getList() {
  loading.value = true
  listAlgorithm(queryParams.value).then(response => {
    algorithmList.value = response.rows || []
    total.value = response.total || 0
  }).finally(() => {
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
  ids.value = selection.map(item => item.algId)
  single.value = selection.length !== 1
  multiple.value = !selection.length
}

function openEditDialog(row) {
  Object.assign(editForm, {
    algId: row?.algId,
    algName: row?.algName || '',
    algSerial: row?.algSerial || '',
    algVersion: row?.algVersion || '',
    algWeightPath: row?.algWeightPath || '',
    algRuntimeType: row?.algRuntimeType || 'external_box',
    algEnabled: row?.algEnabled !== false,
    algDefaultConfText: JSON.stringify(parseJson(row?.algDefaultConf), null, 2)
  })
  editDialogVisible.value = true
}

async function saveEdit() {
  let algDefaultConf
  try {
    algDefaultConf = JSON.stringify(JSON.parse(editForm.algDefaultConfText || '{}'))
  } catch {
    proxy.$modal.msgError('默认配置必须是合法 JSON')
    return
  }
  const payload = {
    algId: editForm.algId,
    algName: editForm.algName,
    algSerial: editForm.algSerial,
    algVersion: editForm.algVersion,
    algWeightPath: editForm.algWeightPath,
    algRuntimeType: editForm.algRuntimeType,
    algEnabled: editForm.algEnabled,
    algDefaultConf
  }
  if (payload.algId) {
    await updateAlgorithm(payload)
  } else {
    await addAlgorithm(payload)
  }
  proxy.$modal.msgSuccess('保存成功')
  editDialogVisible.value = false
  getList()
}

function openUploadDialog() {
  Object.assign(uploadForm, { algName: '', algSerial: '', algVersion: '', algRuntimeType: 'external_box', algDefaultConf: '{}' })
  uploadFile.value = null
  uploadProgress.value = 0
  uploadDialogVisible.value = true
  uploadRef.value?.clearFiles?.()
}

function handleWeightSelected(file) {
  uploadFile.value = file.raw
}

function handleWeightRemoved() {
  uploadFile.value = null
}

async function submitWeightUpload() {
  if (!uploadFile.value) {
    proxy.$modal.msgError('请选择权重文件')
    return
  }
  uploading.value = true
  uploadProgress.value = 0
  const formData = new FormData()
  formData.append('alg_name', uploadForm.algName)
  formData.append('alg_serial', uploadForm.algSerial)
  formData.append('alg_version', uploadForm.algVersion)
  formData.append('alg_runtime_type', uploadForm.algRuntimeType)
  formData.append('alg_default_conf', uploadForm.algDefaultConf || '{}')
  formData.append('file', uploadFile.value)
  try {
    await uploadAlgorithmWeight(formData, event => {
      if (event.total) uploadProgress.value = Math.round((event.loaded * 100) / event.total)
    })
    proxy.$modal.msgSuccess('上传成功')
    uploadDialogVisible.value = false
    getList()
  } finally {
    uploading.value = false
  }
}

function showSceneDetail(row) {
  detailAlgorithm.value = row
  detailDialogVisible.value = true
}

async function handleDelete(row) {
  const algorithmIds = row?.algId ? [row.algId] : ids.value
  if (!algorithmIds.length) return

  try {
    const response = await listVideo({ pageNum: 1, pageSize: 1000 })
    const videoRows = response.rows || []
    for (const algId of algorithmIds) {
      const boundVideos = videoRows.filter(video => cameraHasAlgorithm(video, algId))
      if (boundVideos.length > 0) {
        proxy.$modal.msgWarning(`算法 ${algId} 已绑定 ${boundVideos.length} 个摄像头，请先解绑后再删除`)
        return
      }
    }

    await proxy.$modal.confirm(`是否确认删除算法编号为"${algorithmIds.join(', ')}"的数据项？`)
    for (const algId of algorithmIds) {
      await delAlgorithm(algId)
    }
    proxy.$modal.msgSuccess('删除成功')
    await getList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

onMounted(() => {
  getList()
})
</script>

<style scoped>
.detail-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: var(--el-font-family-monospace, monospace);
}
</style>
