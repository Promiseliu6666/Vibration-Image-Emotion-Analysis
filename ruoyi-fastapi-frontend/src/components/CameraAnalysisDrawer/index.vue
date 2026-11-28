<template>
  <el-drawer :model-value="modelValue" title="配置摄像头算法" size="min(540px, 100vw)"
    :before-close="beforeClose" :close-on-click-modal="!saving" :close-on-press-escape="!saving"
    :show-close="!saving" @update:model-value="emit('update:modelValue', $event)">
    <template v-if="camera">
      <div class="assignment-device">
        <el-icon :size="24"><VideoCamera /></el-icon>
        <div><strong>{{ camera.name }}</strong><small>{{ cameraSourceLabels[camera.source] }} · {{ camera.camera_id }}</small></div>
        <el-tag :type="connection.type" size="small">{{ connection.label }}</el-tag>
      </div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <el-form label-position="top" class="assignment-form" @submit.prevent="save(false)">
        <el-form-item label="应用场景" required>
          <el-select v-model="draft.scene" filterable allow-create default-first-option
            placeholder="选择或输入应用场景" :disabled="saving" style="width:100%" aria-label="应用场景">
            <el-option v-for="scene in scenes" :key="scene" :label="scene" :value="scene" />
          </el-select>
          <small class="field-note">为当前设备标记使用位置或观察用途，最多 80 个字符。</small>
        </el-form-item>
        <el-form-item label="启用的算法" required>
          <el-checkbox-group v-model="draft.algorithm_ids" :disabled="saving" class="assignment-algorithms">
            <el-checkbox v-for="algorithm in selectableAlgorithms" :key="algorithm.id" :label="algorithm.id"
              :disabled="algorithm.sources?.length > 0 && !algorithm.sources.includes(camera.source)"
              class="assignment-algorithm" :class="{ 'is-selected': draft.algorithm_ids.includes(algorithm.id) }">
              <strong>{{ algorithm.name }}</strong><span>{{ algorithm.description }}</span>
              <small>{{ algorithm.metrics?.map(metric => metric.label).join(' · ') }}</small>
            </el-checkbox>
          </el-checkbox-group>
          <el-empty v-if="!selectableAlgorithms.length" :image-size="50" description="算法目录尚未加载">
            <el-button :loading="loadingAlgorithms" @click="reloadAlgorithms">重新加载算法</el-button>
          </el-empty>
          <small class="field-note">可同时启用多个算法。保存后，实时监测会按新配置展示结果。</small>
        </el-form-item>
        <div v-if="draft.algorithm_ids.includes('fatigue')" class="assignment-overlay">
          <div><strong>疲劳检测线框</strong><p>在画面中显示检测位置，关闭后仍继续分析。</p></div>
          <el-switch v-model="draft.show_overlay" :disabled="saving" aria-label="显示疲劳检测线框" />
        </div>
        <p class="assignment-note">{{ draft.algorithm_ids.includes('fatigue') ? '疲劳检测开始后需要预热，检测状态和有效数据会在实时监测中显示。' : '设备连接状态与算法分析状态分别展示，进入监测后查看实时结果。' }}</p>
      </el-form>
    </template>
    <template #footer>
      <div class="assignment-footer">
        <span>{{ dirty ? '有未保存的修改' : '配置已同步' }}</span>
        <el-button :disabled="saving" @click="close">取消</el-button>
        <el-button :loading="saving && !monitorAfterSave" :disabled="saving || !selectableAlgorithms.length" @click="save(false)">保存配置</el-button>
        <el-button type="primary" :loading="saving && monitorAfterSave"
          :disabled="saving || !selectableAlgorithms.length || camera?.configured === false" @click="save(true)">保存并监测</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoCamera } from '@element-plus/icons-vue'
import useCameraStore from '@/store/modules/camera'
import { cameraAnalysis, cameraConnectionState, cameraSourceLabels, sameCameraAnalysis, validateCameraAnalysis } from '@/utils/cameraManagement'

const props = defineProps({ modelValue: Boolean, camera: { type: Object, default: null }, preferredAlgorithm: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue', 'saved', 'monitor'])
const cameraStore = useCameraStore()
const draft = reactive({ scene: '', algorithm_ids: [], show_overlay: false })
const baseline = ref({ scene: '', algorithm_ids: [], show_overlay: false })
const saving = ref(false)
const monitorAfterSave = ref(false)
const loadingAlgorithms = ref(false)
const error = ref('')
const selectableAlgorithms = computed(() => cameraStore.algorithms.filter(algorithm => algorithm.selectable))
const scenes = computed(() => [...new Set(selectableAlgorithms.value.flatMap(algorithm => algorithm.scenes || []))])
const connection = computed(() => cameraConnectionState(props.camera))
const dirty = computed(() => !sameCameraAnalysis(draft, baseline.value))
watch(() => [props.modelValue, props.camera?.camera_id], () => {
  if (!props.modelValue || !props.camera) return
  const current = cameraAnalysis(props.camera)
  baseline.value = current
  Object.assign(draft, { ...current, algorithm_ids: [...current.algorithm_ids] })
  if (selectableAlgorithms.value.some(algorithm => algorithm.id === props.preferredAlgorithm)
      && !draft.algorithm_ids.includes(props.preferredAlgorithm)) draft.algorithm_ids.push(props.preferredAlgorithm)
  error.value = ''
}, { immediate: true })
async function reloadAlgorithms() {
  loadingAlgorithms.value = true
  try { await cameraStore.loadAlgorithms(); error.value = '' }
  catch { error.value = '算法目录读取失败，请重试。' }
  finally { loadingAlgorithms.value = false }
}
async function confirmDiscard() {
  if (saving.value) return false
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm('修改尚未保存，确定放弃这些修改？', '离开配置', {
      confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning'
    })
    return true
  } catch { return false }
}
async function beforeClose(done) { if (await confirmDiscard()) done() }
async function close() { if (await confirmDiscard()) emit('update:modelValue', false) }
async function save(monitor) {
  if (saving.value || !props.camera) return
  error.value = validateCameraAnalysis(draft)
  if (error.value) return
  const cameraId = props.camera.camera_id
  const config = { scene: draft.scene.trim(), algorithm_ids: [...draft.algorithm_ids], show_overlay: draft.algorithm_ids.includes('fatigue') && draft.show_overlay }
  saving.value = true
  monitorAfterSave.value = monitor
  try {
    const saved = await cameraStore.configureCamera(cameraId, config)
    baseline.value = cameraAnalysis({ analysis: saved })
    Object.assign(draft, { ...baseline.value, algorithm_ids: [...baseline.value.algorithm_ids] })
    ElMessage.success('摄像头算法配置已保存')
    emit('saved', { cameraId, analysis: saved })
    emit('update:modelValue', false)
    if (monitor) emit('monitor', cameraId)
  } catch { error.value = '配置保存失败，修改已保留，请重试。' }
  finally { saving.value = false }
}
defineExpose({ confirmDiscard })
</script>

<style scoped>
.assignment-device { display:flex;align-items:center;gap:12px;padding:16px;background:var(--el-fill-color-light);border-radius:8px;margin-bottom:22px;color:var(--el-text-color-primary); }
.assignment-device > div { flex:1;min-width:0; }
.assignment-device small { display:block;margin-top:6px;overflow-wrap:anywhere; }
.assignment-device small,.field-note,.assignment-note { color:var(--el-text-color-secondary);font-size:12px;line-height:1.8; }
.assignment-form { margin-top:20px; }
.assignment-algorithms { display:grid;gap:12px;width:100%; }
.assignment-algorithm { margin:0;height:auto;align-items:flex-start;white-space:normal;padding:16px;border:1px solid var(--el-border-color);border-radius:8px; }
.assignment-algorithm.is-selected { border-color:var(--el-color-primary);background:var(--el-color-primary-light-9); }
.assignment-algorithm :deep(.el-checkbox__input) { margin-top:3px; }
.assignment-algorithm :deep(.el-checkbox__label) { white-space:normal;line-height:1.65; }
.assignment-algorithm strong,.assignment-algorithm span,.assignment-algorithm small { display:block; }
.assignment-algorithm strong { font-size:14px;color:var(--el-text-color-primary); }
.assignment-algorithm span { margin:7px 0;color:var(--el-text-color-regular);font-size:13px; }
.assignment-algorithm small { color:var(--el-text-color-secondary);font-size:12px; }
.assignment-overlay { display:flex;justify-content:space-between;align-items:center;gap:16px;padding:16px 0;border-top:1px solid var(--el-border-color-light); }
.assignment-overlay strong { font-size:14px; }
.assignment-overlay p { font-size:12px;color:var(--el-text-color-secondary);margin:7px 0 0; }
.assignment-footer { display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap; }
.assignment-footer > span { flex:1;font-size:12px;color:var(--el-text-color-secondary);text-align:left; }
.assignment-footer :deep(.el-button + .el-button) { margin-left:0; }
@media(max-width:500px) { .assignment-device { flex-wrap:wrap; }.assignment-footer > span { flex-basis:100%; } }
</style>
