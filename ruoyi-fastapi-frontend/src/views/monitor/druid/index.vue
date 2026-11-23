<template>
  <div ref="monitorRoot" class="configured-monitor" :style="{ '--monitor-height':viewportHeight }">
    <header class="monitor-config">
      <div>
        <strong>视频监测</strong>
        <span>{{ cameraStore.selectedAnalysis.scene }} · {{ algorithmName }}</span>
      </div>
      <router-link to="/cameras">配置摄像头场景与算法</router-link>
    </header>
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon>
      <el-button @click="loadConfiguration">重新读取配置</el-button>
    </el-alert>
    <div v-else-if="!configurationReady" v-loading="true" class="monitor-loading">正在读取摄像头算法配置…</div>
    <div v-else class="algorithm-panels">
      <WellbeingMonitor v-if="cameraStore.selectedAnalysis.algorithm_ids.includes('vibration')"
        :key="`${cameraStore.cameraId}:vibration`" :algorithm-ids="cameraStore.selectedAnalysis.algorithm_ids">
        <template #fatigue>
          <FatigueMonitor v-if="cameraStore.selectedAnalysis.algorithm_ids.includes('fatigue')"
            :key="`${cameraStore.cameraId}:fatigue:${cameraStore.selectedAnalysis.show_overlay}`"
            embedded :show-overlay="cameraStore.selectedAnalysis.show_overlay" />
        </template>
      </WellbeingMonitor>
      <FatigueMonitor v-else :key="`${cameraStore.cameraId}:fatigue:${cameraStore.selectedAnalysis.show_overlay}`"
        :show-overlay="cameraStore.selectedAnalysis.show_overlay" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import useCameraStore from '@/store/modules/camera'
import FatigueMonitor from '@/views/fatigue/index.vue'
import WellbeingMonitor from './WellbeingMonitor.vue'
import {useMonitorViewport} from '@/composables/useMonitorViewport'

const cameraStore = useCameraStore()
const monitorRoot=ref(null)
const viewportHeight=useMonitorViewport(monitorRoot)
const loadError = ref('')
const configurationReady = ref(false)
const monitorPanels = computed(() => [
  {id:'vibration', name:'幸福指数检测', component:WellbeingMonitor},
  {id:'fatigue', name:'疲劳检测', component:FatigueMonitor}
].filter(panel => cameraStore.selectedAnalysis.algorithm_ids.includes(panel.id)))
const algorithmName = computed(() => monitorPanels.value.map(panel => panel.name).join(' + '))
async function loadConfiguration() {
  loadError.value = ''
  configurationReady.value = false
  try {
    await cameraStore.loadXiaozhiDevices(true)
    configurationReady.value = true
  }
  catch { loadError.value = '摄像头算法配置读取失败，请重试。' }
}
onMounted(loadConfiguration)
</script>

<style scoped>
.monitor-config { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:16px 22px; background:#fff; border-bottom:1px solid #e4e9ef; }
.monitor-config strong { color:#253b53; font-size:19px; margin-right:18px; }
.monitor-config span { color:#65788c; }
.monitor-config a { color:#287baf; }
.monitor-loading { min-height:300px; padding:30px; }
.algorithm-panels { display:grid; gap:20px; }
.configured-monitor { height:var(--monitor-height,calc(100dvh - 84px));display:flex;flex-direction:column;overflow:hidden; }
.monitor-config { flex-shrink:0;padding:9px 16px;gap:10px;min-height:42px;box-sizing:border-box; }
.monitor-config strong { font-size:16px;margin-right:12px; }
.monitor-config span,.monitor-config a { font-size:12px; }
.algorithm-panels { flex:1;min-height:0;display:flex;gap:0; }
.algorithm-panels > * { min-height:0;width:100%; }
.configured-monitor :deep(.vibra-monitor) { min-height:0;height:100%;box-sizing:border-box;width:100%;max-width:none;padding:12px 16px;display:flex;flex-direction:column; }
.configured-monitor :deep(.vibra-monitor .header) { margin-bottom:12px;padding-bottom:10px;gap:10px;flex-shrink:0; }
.configured-monitor :deep(.vibra-monitor .header h2) { font-size:20px; }
.configured-monitor :deep(.vibra-monitor .controls) { gap:10px; }
.configured-monitor :deep(.main-content) { flex:1;min-height:0;height:auto;gap:20px; }
.configured-monitor :deep(.video-section) { height:100%;min-height:0; }
.configured-monitor :deep(.video-wrapper) { min-height:0;height:100%; }
.configured-monitor :deep(.params-section) { min-height:0;min-width:360px;max-width:460px; }
.configured-monitor :deep(.params-panel .person-card) { padding:12px;margin-bottom:12px; }
.configured-monitor :deep(.params-panel .person-header) { margin-bottom:8px; }
.configured-monitor :deep(.params-panel .person-header h4) { font-size:13px; }
.configured-monitor :deep(.params-panel .person-content) { gap:6px 12px; }
.configured-monitor :deep(.params-panel .person-label),.configured-monitor :deep(.params-panel .person-value) { font-size:11px; }
.configured-monitor :deep(.switch-btn-container) { margin-bottom:8px; }
.configured-monitor :deep(.wellbeing-header) { margin-bottom:12px; }
.configured-monitor :deep(.wellbeing-header h3) { font-size:16px; }
.configured-monitor :deep(.index-value) { font-size:48px; }
.configured-monitor :deep(.level-indicators) { gap:8px; }
.configured-monitor :deep(.level-label),.configured-monitor :deep(.level-value) { font-size:12px; }
@media(max-width:900px){
  .configured-monitor :deep(.main-content) { flex-direction:row; }
  .configured-monitor :deep(.video-section) { flex:1; }
  .configured-monitor :deep(.params-section) { flex:1;min-width:300px;max-width:400px;width:auto; }
}
@media(max-width:640px){
  .monitor-config { flex-direction:row;align-items:center; }
  .monitor-config span { display:none; }
  .configured-monitor :deep(.main-content) { flex-direction:column;gap:10px; }
  .configured-monitor :deep(.video-section) { flex:0 0 27%;width:100%; }
  .configured-monitor :deep(.params-section) { flex:1;min-width:0;max-width:none;width:100%; }
}
@media (max-width:700px) { .monitor-config { align-items:flex-start; flex-direction:column; } }
</style>
<style scoped>
@media(max-height:800px){
  .configured-monitor :deep(.params-panel .person-card){padding:7px 9px;margin-bottom:0}
  .configured-monitor :deep(.params-panel .person-header){display:none}
  .configured-monitor :deep(.params-panel .person-content){gap:5px 8px}
}
</style>
<style scoped>
@media(min-height:801px) and (max-height:1000px){
  .configured-monitor :deep(.params-panel .person-card){padding:9px 10px;margin-bottom:0}
  .configured-monitor :deep(.params-panel .person-header){margin-bottom:6px;padding-bottom:5px}
}
</style>
