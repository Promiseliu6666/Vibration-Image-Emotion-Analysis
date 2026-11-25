<template>
  <section class="monitor-panel" aria-label="实时状态监测">
    <header class="monitor-panel__heading">
      <div class="monitor-tabs" role="tablist" aria-label="监测指标类型">
        <button v-for="tab in tabs" :key="tab.id" :ref="element => tabRefs[tab.id] = element"
          type="button" role="tab" :id="`${panelId}-tab-${tab.id}`"
          :aria-selected="activeId === tab.id" :aria-controls="`${panelId}-${tab.id}`"
          :tabindex="activeId === tab.id ? 0 : -1" :class="{ 'is-active':activeId === tab.id }"
          @click="activeId = tab.id" @keydown="navigate($event, tab.id)">
          <svg class="monitor-tabs__icon" viewBox="0 0 24 24" aria-hidden="true">
            <path v-if="tab.id === 'vibration'" d="M3 12h4l2.5-6 5 12 2.5-6h4" />
            <template v-else><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" /></template>
          </svg>
          <span>{{ tab.label }}</span>
        </button>
      </div>
    </header>
    <div class="monitor-panel__body">
      <div v-if="algorithmIds.includes('vibration')" v-show="activeId === 'vibration'"
        class="monitor-panel__psychological"
        :id="`${panelId}-vibration`" role="tabpanel" :aria-labelledby="`${panelId}-tab-vibration`">
        <slot name="psychological" />
      </div>
      <div v-if="algorithmIds.includes('fatigue')" v-show="activeId === 'fatigue'"
        class="monitor-panel__fatigue"
        :id="`${panelId}-fatigue`" role="tabpanel" :aria-labelledby="`${panelId}-tab-fatigue`">
        <slot name="fatigue" />
      </div>
    </div>
    <footer v-if="notificationsVisible" class="monitor-panel__notifications" aria-label="邮件预警通知">
      <slot name="notifications" />
    </footer>
  </section>
</template>

<script setup>
import {computed,getCurrentInstance,ref,watch} from 'vue'
const props=defineProps({algorithmIds:{type:Array,default:()=>['vibration']},notificationsVisible:Boolean})
const panelId=`monitor-${getCurrentInstance().uid}`
const activeId=ref(props.algorithmIds[0] || 'vibration')
const tabRefs=ref({})
const tabs=computed(()=>[
  {id:'vibration',label:'心理状态'},
  {id:'fatigue',label:'疲劳状态'}
].filter(tab=>props.algorithmIds.includes(tab.id)))
watch(()=>props.algorithmIds.slice(),ids=>{if(!ids.includes(activeId.value)) activeId.value=ids[0]})
function navigate(event,id){
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return
  event.preventDefault()
  const current=tabs.value.findIndex(tab=>tab.id===id)
  const index=event.key==='Home'?0:event.key==='End'?tabs.value.length-1:
    (current+(event.key==='ArrowRight'?1:-1)+tabs.value.length)%tabs.value.length
  activeId.value=tabs.value[index].id
  tabRefs.value[activeId.value]?.focus()
}
</script>

<style scoped>
.monitor-panel{height:100%;min-width:0;display:flex;flex-direction:column;background:#fff;border:1px solid #e2e9f1;border-radius:18px;overflow:hidden;box-shadow:0 10px 30px #263b5310;color:#20364d;box-sizing:border-box}
.monitor-panel__heading{padding:0 18px;flex-shrink:0}
.monitor-tabs{display:flex;gap:22px;border-bottom:1px solid #e6ecf3}
.monitor-tabs button{position:relative;flex:1;display:flex;align-items:center;justify-content:center;gap:9px;padding:17px 8px 15px;border:0;background:transparent;color:#8795a7;font:inherit;font-size:14px;font-weight:500;cursor:pointer;transition:color .18s,background .18s}
.monitor-tabs button::after{position:absolute;content:'';height:3px;left:14px;right:14px;bottom:-1px;background:#2d6fb5;border-radius:3px 3px 0 0;transform:scaleX(0);transition:transform .18s}
.monitor-tabs button:hover{color:#2d6fb5;background:linear-gradient(0deg,#f5f9fd,transparent)}
.monitor-tabs button.is-active{color:#245e9b;font-weight:700}
.monitor-tabs button.is-active::after{transform:scaleX(1)}
.monitor-tabs button:focus-visible{outline:2px solid #85add7;outline-offset:-4px;border-radius:6px}
.monitor-tabs__icon{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;flex-shrink:0}
.monitor-panel__body{flex:1;min-height:0;overflow:auto;padding:12px 14px}
.monitor-panel__fatigue{display:flex;min-height:100%;width:100%}
.monitor-panel__psychological{display:flex;min-height:100%;width:100%}
@media(max-height:800px){.monitor-tabs button{padding-top:12px;padding-bottom:10px}.monitor-panel__body{padding-top:8px;padding-bottom:8px}}
.monitor-panel__notifications{flex-shrink:0;border-top:1px solid #edf1f5;padding:8px 12px;background:#fafbfd;max-height:96px;overflow:auto}
@media(max-width:600px){.monitor-panel__heading{padding:0 14px}.monitor-tabs{gap:14px}.monitor-tabs button{font-size:13px;padding:14px 6px 12px}.monitor-panel__body{padding:12px}}
</style>
