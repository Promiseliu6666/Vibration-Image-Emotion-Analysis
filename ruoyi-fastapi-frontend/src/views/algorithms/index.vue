<template>
  <div class="app-container algorithm-page">
    <header><div><h2>算法管理</h2><p>汇集已接入的实时分析算法、依赖能力及各自输出指标。</p></div><router-link to="/cameras">配置摄像头 →</router-link></header>
    <el-input v-model="search" placeholder="搜索算法或指标" clearable style="max-width:360px;margin-bottom:22px" />
    <el-alert v-if="error" :title="error" type="error" :closable="false"><el-button @click="load">重试</el-button></el-alert>
    <div v-loading="loading" class="algorithm-grid">
      <el-card v-for="algorithm in filteredAlgorithms" :key="algorithm.id" shadow="hover">
        <template #header><div class="card-heading"><strong>{{ algorithm.name }}</strong><el-tag :type="algorithm.selectable ? 'success' : 'info'">{{ algorithm.selectable ? '主分析算法' : '辅助能力' }}</el-tag></div></template>
        <p>{{ algorithm.description }}</p>
        <div class="metric-tags"><el-tag v-for="metric in algorithm.metrics" :key="metric.key" effect="plain">{{ metric.label }}</el-tag></div>
        <p>支持：本地摄像头 / RTSP / 小智 Watcher</p>
        <p v-if="algorithm.scenes.length">参考场景：{{ algorithm.scenes.join('、') }}</p>
        <el-button v-if="algorithm.selectable" type="primary" plain @click="router.push('/cameras')">为摄像头配置</el-button>
        <span v-else class="helper-note">随主分析流程运行</span>
      </el-card>
    </div>
    <el-empty v-if="!loading && !error && !filteredAlgorithms.length" description="暂无匹配算法" />
    <el-card class="external-catalog">
      <template #header><strong>外部服务算法</strong></template>
      <p>以下为原系统登记的算法，由外部分析服务执行；输出指标由对应服务提供。</p>
      <el-alert v-if="externalError" :title="externalError" type="warning" :closable="false" />
      <el-table v-loading="externalLoading" :data="externalRows">
        <el-table-column prop="algName" label="算法名称" />
        <el-table-column prop="algSerial" label="算法编号" />
        <el-table-column prop="algVersion" label="版本" />
        <el-table-column label="接入方式"><template #default>外部服务</template></el-table-column>
      </el-table>
      <el-pagination v-if="externalTotal > 20" v-model:current-page="externalPage" :page-size="20" :total="externalTotal" layout="prev, pager, next" @current-change="loadExternal" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import useCameraStore from '@/store/modules/camera'
import { listAlgorithm } from '@/api/xuzhou/algorithm'
const cameraStore = useCameraStore()
const router = useRouter()
const search = ref('')
const loading = ref(false)
const error = ref('')
const externalRows = ref([])
const externalLoading = ref(false)
const externalError = ref('')
const externalPage = ref(1)
const externalTotal = ref(0)
let externalRequest = 0
let searchTimer
async function loadExternal() {
  const requestId = ++externalRequest
  externalLoading.value = true
  externalError.value = ''
  try {
    const response = await listAlgorithm({pageNum:externalPage.value,pageSize:20,algName:search.value.trim() || undefined})
    if (requestId !== externalRequest) return
    externalRows.value = response.rows || []
    externalTotal.value = response.total || 0
  } catch {
    if (requestId === externalRequest) {
      externalRows.value = []
      externalError.value = '外部算法目录暂时不可用，已接入的实时算法仍可配置。'
    }
  } finally { if (requestId === externalRequest) externalLoading.value = false }
}
watch(search, () => {
  clearTimeout(searchTimer)
  ++externalRequest
  searchTimer = setTimeout(() => { externalPage.value = 1; loadExternal() }, 300)
})
const filteredAlgorithms = computed(() => cameraStore.algorithms.filter(a =>
  `${a.name} ${a.description} ${a.metrics.map(m => m.label).join(' ')}`.toLowerCase().includes(search.value.trim().toLowerCase())
))
async function load() {
  loading.value = true
  error.value = ''
  try { await cameraStore.loadAlgorithms() }
  catch { error.value = '算法列表读取失败，请重试。' }
  finally { loading.value = false }
}
onMounted(() => { load(); loadExternal() })
onBeforeUnmount(() => { clearTimeout(searchTimer); ++externalRequest })
</script>

<style scoped>
header, .card-heading { display:flex; justify-content:space-between; align-items:center; gap:14px; }
header { margin-bottom:20px; }
h2 { margin:0 0 10px; color:#253b53; }
p, .helper-note { color:#718197; line-height:1.8; }
.algorithm-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:20px; min-height:160px; }
.metric-tags { display:flex; flex-wrap:wrap; gap:8px; }
a { color:#287baf; }
.external-catalog { margin-top:24px; }
@media(max-width:600px) { .algorithm-grid { grid-template-columns:1fr; } header { align-items:flex-start; } }
</style>
