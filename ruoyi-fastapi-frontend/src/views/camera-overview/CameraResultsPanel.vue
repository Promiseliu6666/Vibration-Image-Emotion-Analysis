<template>
  <div class="camera-results-panel">
    <WellbeingMonitor v-if="analysis.algorithm_ids.includes('vibration')" :key="cameraStore.cameraId + ':vibration'"
      results-only hide-metric-tabs :active-metric="activeMetric" :signal-available="vibrationAvailable" :algorithm-ids="analysis.algorithm_ids">
      <template #fatigue>
        <FatigueMonitor v-if="analysis.algorithm_ids.includes('fatigue')" :key="cameraStore.cameraId + ':fatigue'"
          embedded :show-overlay="analysis.show_overlay" />
      </template>
    </WellbeingMonitor>
    <FatigueMonitor v-else-if="analysis.algorithm_ids.includes('fatigue')" :key="cameraStore.cameraId + ':fatigue'"
      embedded :show-overlay="analysis.show_overlay" />
    <el-empty v-else description="请为当前摄像头配置分析算法" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import useCameraStore from '@/store/modules/camera'
import { cameraAnalysis } from '@/utils/cameraManagement'
import WellbeingMonitor from '@/views/monitor/druid/WellbeingMonitor.vue'
import FatigueMonitor from '@/views/fatigue/index.vue'

defineProps({ vibrationAvailable: { type: Boolean, default: true }, activeMetric: { type: String, default: '' } })
const cameraStore = useCameraStore()
const analysis = computed(() => cameraAnalysis(cameraStore.selectedCamera))
</script>

<style scoped>
.camera-results-panel { height:100%;min-height:0;min-width:0;width:100%;overflow:hidden;container:camera-results / size; }
.camera-results-panel > * { height:100%;min-height:0;width:100%;box-sizing:border-box; }
.camera-results-panel :deep(.monitor-panel) { border:0;border-radius:0;box-shadow:none; }
.camera-results-panel :deep(.fatigue-page--embedded) { padding:0;margin:0;max-width:none;background:transparent; }
.camera-results-panel :deep(.fatigue-page--embedded .primary-grid) { display:block;margin:0;height:100%;min-height:0; }
.camera-results-panel :deep(.fatigue-page--embedded .fatigue-panel-host) { height:100%;min-height:0; }
.camera-results-panel :deep(.monitor-panel__body) { box-sizing:border-box;overscroll-behavior:contain; }
.camera-results-panel :deep(.monitor-panel__psychological),
.camera-results-panel :deep(.monitor-panel__fatigue) { height:100%;min-height:0; }
.camera-results-panel :deep(.params-section .params-panel) { height:100%;min-height:0;grid-template-rows:minmax(0,1fr);box-sizing:border-box; }
.camera-results-panel :deep(.person-details) { min-height:0;box-sizing:border-box; }
.camera-results-panel :deep(.person-content) { min-height:0;gap:12px; }
.camera-results-panel :deep(.fatigue-page--embedded .fatigue-card) { height:100%;min-height:0; }
@container camera-results (min-width:560px) {
  .camera-results-panel :deep(.fatigue-page--embedded .fatigue-main) { display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);grid-template-rows:minmax(0,1fr);gap:12px;min-height:280px; }
  .camera-results-panel :deep(.fatigue-card .fatigue-overview) { display:flex;flex-direction:column;justify-content:center;min-height:0;padding:16px; }
  .camera-results-panel :deep(.fatigue-card .overview-heading) { flex-wrap:wrap; }
  .camera-results-panel :deep(.fatigue-card .score-display) { flex-direction:column;align-items:center;gap:6px;margin:12px 0; }
  .camera-results-panel :deep(.fatigue-card .score-display > strong) { font-size:56px; }
  .camera-results-panel :deep(.fatigue-card .behavior-panel) { min-height:0;padding:18px; }
  .camera-results-panel :deep(.fatigue-card .behavior-heading) { flex-wrap:wrap; }
  .camera-results-panel :deep(.fatigue-card .metric-row) { grid-template-columns:82px minmax(18px,1fr) 44px;gap:7px; }
  .camera-results-panel :deep(.fatigue-card .grade) { flex-wrap:wrap; }
  .camera-results-panel :deep(.fatigue-card .grade span) { width:100%;padding-left:9px; }
  .camera-results-panel :deep(.fatigue-card .event-counts > div) { padding:0;gap:4px; }
  .camera-results-panel :deep(.fatigue-card .metric-explanation) { padding:14px 18px; }
  .camera-results-panel :deep(.fatigue-card .metric-explanation p) { font-size:12px;line-height:1.8; }
}
@container camera-results (max-width:380px) {
  .camera-results-panel :deep(.fatigue-card .grade) { flex-wrap:wrap; }
  .camera-results-panel :deep(.fatigue-card .grade span) { width:100%;padding-left:9px; }
  .camera-results-panel :deep(.fatigue-card .behavior-heading) { flex-wrap:wrap; }
  .camera-results-panel :deep(.fatigue-card .metric-row) { grid-template-columns:90px minmax(20px,1fr) 44px;gap:7px; }
}
/* Keep the embedded results readable even when viewport-height styles compact the original pages. */
.camera-results-panel :deep(.fatigue-card .overview-heading h3),
.camera-results-panel :deep(.fatigue-card .behavior-heading h3) { font-size:16px;line-height:24px; }
.camera-results-panel :deep(.params-panel .psychological-results .index-value) { font-size:clamp(42px,28cqw,64px) !important;line-height:1.1;font-variant-numeric:tabular-nums; }
.camera-results-panel :deep(.params-panel .index-progress) { height:12px; }
.camera-results-panel :deep(.params-panel .level-label) { font-size:14px;line-height:22px; }
.camera-results-panel :deep(.params-panel .level-value) { font-size:20px;line-height:28px; }
.camera-results-panel :deep(.params-panel .param-label .name),
.camera-results-panel :deep(.params-panel .value) { font-size:15px; }
.camera-results-panel :deep(.params-panel .param-label .key) { font-size:18px; }
.camera-results-panel :deep(.fatigue-card .score-display > strong) { font-size:64px;line-height:1.1; }
.camera-results-panel :deep(.fatigue-card .score-display > span) { font-size:14px; }
.camera-results-panel :deep(.fatigue-card .score-display small) { font-size:12px; }
.camera-results-panel :deep(.fatigue-card .status-tag) { font-size:13px;line-height:22px;padding:2px 9px; }
.camera-results-panel :deep(.fatigue-card .score-track) { height:12px; }
.camera-results-panel :deep(.fatigue-card .grade strong) { font-size:12px;line-height:20px; }
.camera-results-panel :deep(.fatigue-card .grade span) { font-size:11px;line-height:18px; }
.camera-results-panel :deep(.fatigue-card .event-counts span) { font-size:13px; }
.camera-results-panel :deep(.fatigue-card .event-counts strong) { font-size:26px;line-height:32px; }
.camera-results-panel :deep(.fatigue-card .event-counts small) { font-size:12px; }
.camera-results-panel :deep(.fatigue-card .behavior-panel) { min-height:240px; }
.camera-results-panel :deep(.fatigue-card .face-state) { font-size:12px;line-height:20px; }
.camera-results-panel :deep(.fatigue-card .metric-row) { grid-template-columns:minmax(84px,1.15fr) minmax(24px,1fr) 54px;gap:10px;min-height:30px; }
.camera-results-panel :deep(.fatigue-card .metric-label),
.camera-results-panel :deep(.fatigue-card .metric-row strong) { font-size:14px;line-height:22px; }
.camera-results-panel :deep(.fatigue-card .metric-track) { height:10px; }
.camera-results-panel :deep(.fatigue-card .metric-explanation h4) { font-size:14px;line-height:22px; }
.camera-results-panel :deep(.fatigue-card .metric-explanation p) { font-size:13px;line-height:1.7; }
@container camera-results (min-width:720px) {
  .camera-results-panel :deep(.params-panel .psychological-results .index-value) { font-size:clamp(64px,22cqw,80px) !important; }
  .camera-results-panel :deep(.fatigue-card .score-display > strong) { font-size:80px; }
}
@container camera-results (max-width:340px) {
  .camera-results-panel :deep(.params-section .params-panel) { grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr); }
  .camera-results-panel :deep(.person-content) { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px; }
}
@container camera-results (max-height:520px) {
  .camera-results-panel :deep(.fatigue-card) { gap:8px; }
  .camera-results-panel :deep(.fatigue-card .assessment-toolbar) { row-gap:6px;padding-bottom:8px; }
  .camera-results-panel :deep(.fatigue-card .fatigue-main) { gap:8px;min-height:0; }
  .camera-results-panel :deep(.fatigue-card .fatigue-overview) { padding:10px 12px; }
  .camera-results-panel :deep(.fatigue-card .score-display) { margin:5px 0; }
  .camera-results-panel :deep(.fatigue-card .score-display > strong) { font-size:52px; }
  .camera-results-panel :deep(.fatigue-card .behavior-panel) { min-height:0;padding:10px 12px; }
  .camera-results-panel :deep(.fatigue-card .metric-list) { gap:4px; }
  .camera-results-panel :deep(.fatigue-card .metric-row) { min-height:24px; }
  .camera-results-panel :deep(.fatigue-card .event-counts) { margin-top:8px;padding-top:8px; }
  .camera-results-panel :deep(.params-panel .level-indicators) { gap:8px; }
  .camera-results-panel :deep(.params-panel .index-value) { margin-bottom:8px; }
  .camera-results-panel :deep(.person-details) { padding:12px 10px; }
  .camera-results-panel :deep(.person-header) { padding-bottom:8px;margin-bottom:10px; }
}
@container camera-results (min-width:300px) and (max-width:559px) and (max-height:520px) {
  .camera-results-panel :deep(.fatigue-card .fatigue-main) { display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-rows:minmax(0,1fr);align-items:stretch; }
  .camera-results-panel :deep(.fatigue-card .fatigue-overview),
  .camera-results-panel :deep(.fatigue-card .behavior-panel) { min-width:0;min-height:0;padding:8px; }
  .camera-results-panel :deep(.fatigue-card .overview-heading) { flex-wrap:wrap;gap:3px; }
  .camera-results-panel :deep(.fatigue-card .overview-label) { font-size:11px; }
  .camera-results-panel :deep(.fatigue-card .score-display) { flex-direction:column;gap:2px;margin:5px 0; }
  .camera-results-panel :deep(.fatigue-card .score-display > strong) { font-size:40px; }
  .camera-results-panel :deep(.fatigue-card .score-display > span) { font-size:11px; }
  .camera-results-panel :deep(.fatigue-card .grade-band) { grid-template-columns:minmax(0,1fr);gap:2px; }
  .camera-results-panel :deep(.fatigue-card .grade) { flex-wrap:nowrap;line-height:16px; }
  .camera-results-panel :deep(.fatigue-card .grade strong) { font-size:11px;line-height:16px; }
  .camera-results-panel :deep(.fatigue-card .grade span) { width:auto;padding-left:0;font-size:10px;line-height:16px; }
  .camera-results-panel :deep(.fatigue-card .event-counts) { grid-template-columns:minmax(0,1fr);gap:4px; }
  .camera-results-panel :deep(.fatigue-card .event-counts > div + div) { border-left:0; }
  .camera-results-panel :deep(.fatigue-card .event-counts span) { font-size:11px; }
  .camera-results-panel :deep(.fatigue-card .event-counts strong) { font-size:18px;line-height:20px; }
  .camera-results-panel :deep(.fatigue-card .event-counts small) { font-size:10px; }
  .camera-results-panel :deep(.fatigue-card .behavior-heading) { flex-direction:column;align-items:flex-start;gap:3px; }
  .camera-results-panel :deep(.fatigue-card .behavior-heading h3) { font-size:13px;line-height:22px; }
  .camera-results-panel :deep(.fatigue-card .face-state) { font-size:10px; }
  .camera-results-panel :deep(.fatigue-card .metric-row) { grid-template-columns:minmax(0,1fr) auto;gap:3px 6px;min-height:0; }
  .camera-results-panel :deep(.fatigue-card .metric-label) { grid-column:1;grid-row:1;font-size:11px;line-height:18px; }
  .camera-results-panel :deep(.fatigue-card .metric-row strong) { grid-column:2;grid-row:1;font-size:11px;line-height:18px; }
  .camera-results-panel :deep(.fatigue-card .metric-track) { grid-column:1 / -1;grid-row:2;height:6px; }
}
@container camera-results (min-width:560px) and (max-height:360px) {
  .camera-results-panel :deep(.fatigue-card .score-display) { flex-direction:row;align-items:baseline;justify-content:center;gap:8px; }
  .camera-results-panel :deep(.fatigue-card .score-display > strong) { font-size:44px; }
  .camera-results-panel :deep(.fatigue-card .fatigue-overview) { padding:8px 12px; }
  .camera-results-panel :deep(.fatigue-card .event-counts strong) { font-size:22px;line-height:26px; }
}
</style>
