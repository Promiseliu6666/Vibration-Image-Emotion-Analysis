<template>
  <div class="app-container camera-page">
    <header class="page-heading">
      <div><h2>摄像头列表</h2><p>为每个摄像头配置应用场景和一种或多种算法，同时监测并显示各自指标。</p></div>
      <el-button :loading="loading" @click="load">刷新列表</el-button>
    </header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <el-alert v-if="cameraStore.deviceError" :title="cameraStore.deviceError" type="warning" show-icon :closable="false" />
    <el-card v-loading="loading">
      <el-table :data="cameraStore.cameraCatalog" row-key="camera_id" style="width:100%">
        <el-table-column label="摄像头" min-width="175">
          <template #default="{ row }"><strong>{{ row.name }}</strong><small>{{ row.camera_id }}</small></template>
        </el-table-column>
        <el-table-column label="来源 / 状态" min-width="135">
          <template #default="{ row }">
            <div>{{ sourceLabels[row.source] }}</div>
            <el-tag :type="row.configured === false ? 'warning' : row.online === false ? 'info' : 'success'" size="small">
              {{ row.source === 'xiaozhi' ? (row.online ? '在线' : '未出图') : row.detail }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="应用场景" min-width="200">
          <template #default="{ row }">
            <el-select v-if="drafts[row.camera_id]" v-model="drafts[row.camera_id].scene" filterable allow-create default-first-option placeholder="选择或输入场景" style="width:100%" :disabled="saving === row.camera_id">
              <el-option v-for="scene in sceneOptions" :key="scene" :label="scene" :value="scene" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="分析算法（可多选）" min-width="280">
          <template #default="{ row }">
            <el-select v-if="drafts[row.camera_id]" v-model="drafts[row.camera_id].algorithm_ids" multiple style="width:100%" :disabled="saving === row.camera_id">
              <el-option v-for="algorithm in selectableAlgorithms" :key="algorithm.id" :label="algorithm.name" :value="algorithm.id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="检测线框" width="120">
          <template #default="{ row }">
            <el-switch v-if="drafts[row.camera_id]" v-model="drafts[row.camera_id].show_overlay" :disabled="!drafts[row.camera_id].algorithm_ids.includes('fatigue') || saving === row.camera_id" active-text="显示" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" :loading="saving === row.camera_id" :disabled="loading || Boolean(saving)" @click="save(row)">保存</el-button>
            <el-button size="small" :disabled="Boolean(saving)" @click="monitor(row)">监测</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p class="hint">修改后点击“保存”生效。“监测”使用已保存配置。疲劳检测线框默认隐藏，关闭线框不影响算法计算。</p>
      <router-link to="/algorithms">查看所有算法及输出指标 →</router-link>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import useCameraStore from '@/store/modules/camera'

const cameraStore = useCameraStore()
const router = useRouter()
const loading = ref(false)
const saving = ref('')
const error = ref('')
const drafts = reactive({})
const sourceLabels = { local: '本地摄像头', rtsp: 'RTSP 网络摄像头', xiaozhi: '小智 Watcher' }
const selectableAlgorithms = computed(() => cameraStore.algorithms.filter(a => a.selectable))
const sceneOptions = computed(() => [...new Set(selectableAlgorithms.value.flatMap(a => a.scenes))])

async function load() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([cameraStore.loadXiaozhiDevices(true), cameraStore.loadAlgorithms()])
    for (const camera of cameraStore.cameraCatalog) drafts[camera.camera_id] = {
      ...camera.analysis,
      algorithm_ids: [...(camera.analysis.algorithm_ids || [camera.analysis.algorithm_id || 'vibration'])]
    }
  } catch { error.value = '摄像头或算法列表读取失败，请点击刷新重试。' }
  finally { loading.value = false }
}
async function save(camera) {
  const config = drafts[camera.camera_id]
  if (!config?.algorithm_ids?.length) {
    ElMessage.warning('请至少选择一种分析算法')
    return
  }
  if (!config?.scene?.trim() || config.scene.trim().length > 80) {
    ElMessage.warning('应用场景须为 1–80 个字符')
    return
  }
  saving.value = camera.camera_id
  try {
    const saved = await cameraStore.configureCamera(camera.camera_id, { ...config, scene: config.scene.trim() })
    drafts[camera.camera_id] = { ...saved }
    ElMessage.success('场景与算法已保存')
  } catch { ElMessage.error('配置保存失败，原配置已保留，请重试。') }
  finally { saving.value = '' }
}
function monitor(camera) {
  cameraStore.selectCamera(camera.camera_id)
  router.push('/camera/live')
}
onMounted(load)
</script>

<style scoped>
.page-heading { display:flex; justify-content:space-between; align-items:center; gap:20px; margin-bottom:22px; }
h2 { margin:0 0 10px; color:#253b53; }
p, small { color:#718197; }
small { display:block; font-size:12px; overflow-wrap:anywhere; }
.el-alert { margin-bottom:16px; }
.hint { margin-top:22px; line-height:1.7; }
a { color:#287baf; }
@media (max-width:700px) { .page-heading { align-items:flex-start; } }
</style>
