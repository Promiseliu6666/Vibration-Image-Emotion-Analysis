import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createRenderer, h, nextTick, onBeforeUnmount, onMounted } from 'vue'

globalThis.window = { location: { search: '' } }
globalThis.localStorage = { getItem: () => null, setItem() {} }
const cameraUrl = new URL('../src/utils/camera.js', import.meta.url).href
const source = readFileSync(new URL('../src/store/modules/camera.js', import.meta.url), 'utf8')
  .replace("from 'pinia'", `from '${import.meta.resolve('pinia')}'`)
  .replace(/import \{[^}]*\} from '@\/api\/camera'/, `
    const listCameras = async () => globalThis.__deferredCatalog || ({ cameras: [
      {camera_id:'local', source:'local', analysis:{algorithm_id:'vibration',scene:'心理状态观察',show_overlay:false}},
      {camera_id:'xiaozhi:watcher-1', source:'xiaozhi', device_id:'watcher-1', online:true, analysis:{algorithm_id:'fatigue',scene:'值班室',show_overlay:false}}
    ] })
    const listAnalysisAlgorithms = async () => ({algorithms:[]})
    const saveCameraAnalysis = async (camera_id, analysis) => {
      if (globalThis.__failCameraSave) throw new Error('save failed')
      return {camera_id, analysis}
    }
  `)
  .replace("from '@/utils/camera'", `from '${cameraUrl}'`)
const { default: useCameraStore } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)

test('switching cameras selects its own algorithm and card configuration', async () => {
  setActivePinia(createPinia())
  const store = useCameraStore()
  await store.loadXiaozhiDevices(true)
  assert.equal(store.selectedAnalysis.algorithm_id, 'vibration')
  store.selectCamera('xiaozhi:watcher-1')
  assert.equal(store.selectedAnalysis.algorithm_id, 'fatigue')
  assert.equal(store.selectedAnalysis.show_overlay, false)
  store.selectCamera('local')
  assert.equal(store.selectedAnalysis.scene, '心理状态观察')
})

test('successful assignment updates monitor immediately and failed save preserves it', async () => {
  setActivePinia(createPinia())
  const store = useCameraStore()
  await store.loadXiaozhiDevices(true)
  await store.configureCamera('local', {algorithm_id:'fatigue',scene:'门岗',show_overlay:false})
  assert.equal(store.selectedAnalysis.algorithm_id, 'fatigue')
  globalThis.__failCameraSave = true
  try {
    await assert.rejects(store.configureCamera('local', {algorithm_id:'vibration',scene:'员工观察'}))
    assert.equal(store.selectedAnalysis.algorithm_id, 'fatigue')
  } finally { globalThis.__failCameraSave = false }
})

test('a device refresh started before saving cannot restore an older algorithm assignment', async () => {
  setActivePinia(createPinia())
  const store = useCameraStore()
  await store.loadXiaozhiDevices(true)
  const oldCatalog = JSON.parse(JSON.stringify(store.cameraCatalog))
  let releaseRefresh
  globalThis.__deferredCatalog = new Promise(resolve => { releaseRefresh = resolve })
  const refreshing = store.loadXiaozhiDevices(true)
  try {
    await store.configureCamera('local', { algorithm_ids: ['vibration', 'fatigue'], scene: '值班室', show_overlay: false })
    releaseRefresh({ cameras: oldCatalog })
    await refreshing
    assert.deepEqual(store.selectedAnalysis.algorithm_ids, ['vibration', 'fatigue'])
    assert.equal(store.selectedAnalysis.scene, '值班室')
    delete globalThis.__deferredCatalog
    await store.loadXiaozhiDevices(true)
    assert.equal(store.selectedAnalysis.algorithm_id, 'vibration', 'A later refresh must still accept changes saved elsewhere')
  } finally { delete globalThis.__deferredCatalog }
})

test('monitor swaps actual panel instances and releases previous panel on camera or algorithm change', async () => {
  setActivePinia(createPinia())
  const store = useCameraStore()
  await store.loadXiaozhiDevices(true)
  const active = new Set()
  const mounted = []
  function panel(name) {
    return {
      props: { showOverlay: Boolean, embedded: Boolean, resultsOnly: Boolean },
      setup(props, {slots}) {
        const instance = { name, get overlay() { return props.showOverlay }, get embedded() { return props.embedded }, get resultsOnly() { return props.resultsOnly } }
        onMounted(() => { active.add(instance); mounted.push(instance) })
        onBeforeUnmount(() => active.delete(instance))
        return () => h('div', [h('span',name), slots.fatigue?.()])
      }
    }
  }
  globalThis.__cameraTestStore = store
  globalThis.__cameraTestPanels = { fatigue:panel('fatigue'), vibration:panel('vibration') }
  const page = readFileSync(new URL('../src/views/camera-overview/CameraResultsPanel.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(page)
  const code = compileScript(descriptor, { id:'monitor-test', inlineTemplate:true }).content
    .replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
    .replace(/import useCameraStore from '[^']*'/, 'const useCameraStore = () => globalThis.__cameraTestStore')
    .replace("from '@/utils/cameraManagement'", `from '${new URL('../src/utils/cameraManagement.js', import.meta.url).href}'`)
    .replace(/import FatigueMonitor from '[^']*'/, 'const FatigueMonitor = globalThis.__cameraTestPanels.fatigue')
    .replace(/import WellbeingMonitor from '[^']*'/, 'const WellbeingMonitor = globalThis.__cameraTestPanels.vibration')
    .replace(/import CameraAnalysisDrawer from '[^']*'/, 'const CameraAnalysisDrawer = { render: () => null }')
    .replace(/import \{ onBeforeRouteLeave \} from '[^']*'/, 'const onBeforeRouteLeave = () => {}')
    .replace(/import \{useMonitorViewport\} from '[^']*'/, "const useMonitorViewport = () => '600px'")
  const { default: Monitor } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
  function node(type, text = '') { return {type, text, children:[],parent:null} }
  const renderer = createRenderer({
    createElement:node, createText:text => node('text',text), createComment:text => node('comment',text),
    setText:(node,text) => { node.text = text }, setElementText:(node,text) => { node.text = text },
    parentNode:node => node.parent, nextSibling:() => null, patchProp:() => {},
    insert(node,parent) { node.parent = parent; parent.children.push(node) },
    remove(node) { if (node.parent) node.parent.children = node.parent.children.filter(child => child !== node) }
  })
  const app = renderer.createApp(Monitor)
  app.component('router-link', { setup:(_, {slots}) => () => h('a',slots.default?.()) })
  app.component('el-button', { render:() => h('button') })
  app.component('el-alert', { render:() => h('aside') })
  app.component('el-empty', { render:() => h('div') })
  app.directive('loading', {})
  app.mount(node('root'))
  try {
    await new Promise(resolve => setImmediate(resolve))
    await nextTick()
    assert.deepEqual([...active].map(p => p.name), ['vibration'])
    assert.equal([...active][0].resultsOnly, true, 'The merged results panel must not open a second video')
    store.selectCamera('xiaozhi:watcher-1')
    await nextTick()
    assert.deepEqual([...active].map(p => p.name), ['fatigue'])
    assert.equal([...active][0].overlay, false)
    await store.configureCamera('xiaozhi:watcher-1', {algorithm_id:'vibration',scene:'门岗',show_overlay:false})
    await nextTick()
    assert.deepEqual([...active].map(p => p.name), ['vibration'])
    assert.equal(mounted.length, 3)
    await store.configureCamera('xiaozhi:watcher-1', {algorithm_ids:['vibration','fatigue'],scene:'门岗',show_overlay:false})
    await nextTick()
    assert.deepEqual([...active].map(p => p.name).sort(), ['fatigue','vibration'])
    assert.equal([...active].find(p => p.name === 'fatigue').embedded, true)
    assert.equal(mounted.length, 4, 'Existing vibration panel must keep running when fatigue is added')
    await store.configureCamera('xiaozhi:watcher-1', {algorithm_ids:['vibration','fatigue'],scene:'值班室',show_overlay:true})
    await nextTick()
    assert.equal(mounted.length, 4, 'Changing scene or overlay must preserve both running algorithms')
    assert.equal([...active].find(p => p.name === 'fatigue').overlay, true)
  } finally { app.unmount() }
  assert.equal(active.size, 0)
})
