<template>
  <section class="fatigue-card" :class="`is-${view.tone}`" aria-label="疲劳度" @keydown.esc="showMetricHelp = false">
    <header class="assessment-toolbar">
      <h3>疲劳指数综合评估</h3>
      <div class="assessment-tools">
        <button type="button" class="monitor-action-button" :disabled="resetting" @click="$emit('restart')">{{ resetting ? '正在重置…' : '重新检测' }}</button>
        <button type="button" class="monitor-info-button" :aria-expanded="showMetricHelp" @click="showMetricHelp = !showMetricHelp">
          <span class="info-symbol" aria-hidden="true">?</span>指标说明<span class="disclosure-chevron" aria-hidden="true" :class="{ 'is-open': showMetricHelp }"></span>
        </button>
      </div>
    <section v-if="showMetricHelp" class="metric-explanation" aria-label="指标说明">
      <h4>疲劳状态指标说明</h4>
      <p><strong>疲劳度</strong><span>分值越高，疲劳程度越高。</span></p>
      <p><strong>行为指标</strong><span>统计近期眼口变化；张口也可能来自说话。</span></p>
      <p><strong>信号完整度</strong><span>反映姿态识别质量，不代表疲劳程度。</span></p>
    </section>
    </header>
    <div class="fatigue-main">
    <article class="fatigue-overview">
      <header class="overview-heading">
        <span class="overview-label">疲劳程度</span>
        <span class="status-tag">{{ view.title }}</span>
      </header>
      <div class="score-display" aria-live="polite">
        <strong>{{ view.ready ? view.value.toFixed(1) : '—' }}</strong>
        <span>疲劳度 <small>/ 100</small></span>
      </div>
      <div class="score-track" :aria-label="view.ready ? `疲劳度 ${view.value.toFixed(1)}/100` : '疲劳度暂未出分'">
        <div class="score-fill" :style="{ width: `${view.value ?? 0}%` }"></div>
        <i style="left:45%"></i><i style="left:70%"></i>
      </div>
      <div class="grade-band" aria-label="疲劳等级范围">
        <div class="grade alert" :class="{ active: view.ready && view.tone === 'alert' }"><i></i><strong>清醒</strong><span>0–&lt;45</span></div>
        <div class="grade drowsy" :class="{ active: view.ready && view.tone === 'drowsy' }"><i></i><strong>轻度疲劳</strong><span>45–70</span></div>
        <div class="grade fatigued" :class="{ active: view.ready && view.tone === 'fatigued' }"><i></i><strong>明显疲劳</strong><span>&gt;70</span></div>
      </div>
      <p class="assessment-hint">{{ view.hint }}</p>
      <div class="event-counts">
        <div><span>累计眨眼</span><strong>{{ view.blink ?? '—' }}<small>次</small></strong></div>
        <div><span>累计哈欠</span><strong>{{ view.yawn ?? '—' }}<small>次</small></strong></div>
      </div>
    </article>

    <article class="behavior-panel">
      <header class="behavior-heading">
        <h3>行为监测指标</h3>
        <span class="face-state" :class="{ detected: result.face_detected === true }"><i></i>{{ result.face_detected === true ? '人脸信号正常' : result.face_detected === false ? '未检测到人脸' : '等待人脸信号' }}</span>
      </header>
      <div class="metric-list">
        <div v-for="metric in view.metrics" :key="metric.key" class="metric-row" :class="{ 'is-missing': metric.value === null }">
          <span class="metric-label">{{ metric.label }}</span>
          <div class="metric-track"><div :style="{ width: `${metric.value ?? 0}%` }"></div></div>
          <strong>{{ metric.text }}</strong>
        </div>
      </div>
    </article>
    </div>
  </section>
</template>
<script setup>
import { computed, ref } from 'vue'
import { fatiguePresentation } from '../../utils/fatiguePresentation.js'
const props = defineProps({ result: { type: Object, default: () => ({}) }, error: { type: String, default: '' }, resetting: Boolean })
defineEmits(['restart'])
const view = computed(() => fatiguePresentation(props.result, props.error))
const showMetricHelp = ref(false)
</script>
<style scoped>
.fatigue-card{--accent:#20846b;--soft:#eaf6f0;display:flex;flex-direction:column;gap:12px;min-height:100%;width:100%;box-sizing:border-box;color:#20364d;font-family:inherit}
.fatigue-main{display:flex;flex-direction:column;flex:1;gap:12px;min-height:0}
.overview-label{font-size:13px;line-height:22px;color:#6a8099}
.is-drowsy{--accent:#b97a20;--soft:#fff5e6}.is-fatigued{--accent:#ce5158;--soft:#fceff0}.is-pending,.is-error{--accent:#8798ad;--soft:#f0f3f7}
h3,h4,p{margin:0}.fatigue-overview{padding:16px 18px;border:1px solid #e2eaf4;border-radius:12px;background:linear-gradient(140deg,#f4f8ff,#fff 75%);flex-shrink:0}
.overview-heading,.behavior-heading{display:flex;align-items:center;justify-content:space-between;gap:8px}.overview-heading h3,.behavior-heading h3{font-size:14px;font-weight:650;line-height:22px}.status-tag{color:var(--accent);background:var(--soft);border:1px solid color-mix(in srgb,var(--accent) 20%,transparent);font-size:11px;font-weight:600;line-height:20px;padding:1px 9px;border-radius:5px;white-space:nowrap}
.score-display{display:flex;flex-direction:column;align-items:center;margin:12px 0}.score-display>strong{font-size:48px;line-height:1.1;font-weight:700;letter-spacing:-1px;color:#243e61;font-variant-numeric:tabular-nums}.score-display>span{font-size:12px;color:#72859c;margin-top:6px}.score-display small{font-size:11px;color:#9aa9ba;margin-left:4px}
.score-track{position:relative;height:9px;border-radius:6px;background:#e7edf5;overflow:hidden}.score-fill{height:100%;background:var(--accent);border-radius:6px;transition:width .5s ease}.score-track>i{position:absolute;top:0;height:100%;border-left:2px solid #ffffffb8}
.grade-band{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:9px}.grade{--grade:#20846b;display:flex;align-items:center;gap:4px;color:#7d8c9f;font-size:10px;line-height:16px;white-space:nowrap}.grade.drowsy{--grade:#b97a20}.grade.fatigued{--grade:#ce5158}.grade>i{width:5px;height:5px;background:var(--grade);border-radius:50%;flex-shrink:0}.grade strong{font-size:10px;font-weight:500}.grade span{font-size:9px;color:#99a6b6}.grade.active strong{color:var(--grade);font-weight:700}.assessment-hint{font-size:11px;line-height:18px;color:#7b8ca2;margin-top:8px}
.event-counts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;border-top:1px solid #e5edf5;padding-top:11px}.event-counts>div{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 8px}.event-counts>div+div{border-left:1px solid #e1e9f2}.event-counts span{color:#7b8ca2;font-size:11px}.event-counts strong{font-size:22px;font-weight:650;line-height:24px;font-variant-numeric:tabular-nums}.event-counts small{font-size:10px;font-weight:400;color:#91a0b3;margin-left:5px}
.behavior-panel{display:flex;flex-direction:column;flex:1;border:1px solid #e5edf5;border-radius:10px;padding:12px 14px;min-height:176px}.behavior-heading{margin-bottom:7px}.face-state{display:flex;align-items:center;gap:5px;font-size:10px;color:#91a0b3;white-space:nowrap}.face-state>i{width:5px;height:5px;border-radius:50%;background:#a0aec0}.face-state.detected>i{background:#279977}.metric-list{flex:1;display:flex;flex-direction:column;justify-content:space-around;gap:8px}.metric-row{display:grid;grid-template-columns:100px minmax(30px,1fr) 50px;gap:10px;align-items:center;min-height:20px}.metric-label{font-size:11px;color:#60758f}.metric-track{height:7px;background:#edf2f8;border-radius:5px;overflow:hidden}.metric-track>div{height:100%;border-radius:5px;background:linear-gradient(90deg,#93b8eb,#548bd2);transition:width .4s ease}.metric-row strong{font-size:11px;font-weight:600;color:#3c597c;text-align:right;font-variant-numeric:tabular-nums}.metric-row.is-missing strong{color:#a5b0be}
.assessment-toolbar{position:relative}
.metric-explanation{position:absolute;z-index:5;top:calc(100% + 5px);right:0;left:0;max-height:min(340px,50vh);overflow:auto;box-sizing:border-box;background:#fff;border:1px solid #e5edf5;border-radius:9px;padding:10px 12px;box-shadow:0 8px 24px #20364d24}.metric-explanation h4{font-size:11px;font-weight:650;color:#3f5771;margin-bottom:6px}.metric-explanation p{display:flex;gap:8px;font-size:10px;line-height:18px;color:#7b8b9f}.metric-explanation strong{font-weight:500;color:#5c7087;flex-shrink:0}
@media(max-height:1000px){.fatigue-card{gap:8px}.fatigue-overview{padding:12px 14px}.score-display{margin:8px 0}.score-display>strong{font-size:40px}.event-counts{margin-top:8px;padding-top:8px}.behavior-panel{padding:9px 12px;min-height:156px}.metric-list{gap:5px}.metric-explanation{padding:7px 10px}.metric-explanation h4{margin-bottom:3px}.metric-explanation p{line-height:16px}}
@media(max-width:380px){.metric-row{grid-template-columns:90px minmax(20px,1fr) 44px;gap:7px}.grade{flex-wrap:wrap}.grade span{width:100%;padding-left:9px}.behavior-heading{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){.score-fill,.metric-track>div{transition:none}}
</style>
<style scoped src="@/assets/styles/monitor-assessment.css"></style>
<style scoped>
@media(max-height:1000px){
  .fatigue-card{gap:5px}
  .fatigue-overview{padding:7px 12px}
  .overview-heading h3{font-size:13px;line-height:18px}
  .status-tag{font-size:10px;line-height:18px;padding:0 7px}
  .score-display{flex-direction:row;justify-content:center;align-items:baseline;gap:10px;margin:5px 0}
  .score-display>strong{font-size:40px;line-height:1.1}
  .score-display>span{margin:0;font-size:11px}
  .score-track{height:7px}
  .grade-band{margin-top:6px}
  .assessment-hint{display:none}
  .event-counts{margin-top:6px;padding-top:5px}
  .event-counts strong{font-size:18px;line-height:20px}
  .behavior-panel{min-height:124px;padding:6px 10px}
  .behavior-heading{margin-bottom:4px}
  .behavior-heading h3{font-size:12px;line-height:18px}
  .metric-list{gap:2px}
  .metric-row{min-height:16px}
  .metric-explanation{padding:5px 10px}
  .metric-explanation h4{line-height:14px;margin-bottom:3px}
  .metric-explanation p{line-height:14px}
}
</style>

