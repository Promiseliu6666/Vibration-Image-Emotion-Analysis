import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, h, markRaw, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

const moduleUrl = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64')
const cameraUrl = new URL('../src/utils/camera.js', import.meta.url).href
const managementUrl = new URL('../src/utils/cameraManagement.js', import.meta.url).href
const previewSource = readFileSync(new URL('../src/views/camera-overview/preview.js', import.meta.url), 'utf8')
  .replace("from '@/utils/camera'", `from '${cameraUrl}'`)
const previewUrl = moduleUrl(previewSource)
const { cameraPreviewUrl } = await import(previewUrl)
const iconStub = { render: () => null }
globalThis.__overviewIcons = Object.fromEntries(['ArrowRight', 'FullScreen', 'Grid', 'Monitor', 'Refresh', 'Setting', 'VideoCamera'].map(name => [name, iconStub]))
function compileView(file) {
  const { descriptor } = parse(readFileSync(new URL(file, import.meta.url), 'utf8'))
  return compileScript(descriptor, { id: file, inlineTemplate: true }).content
    .replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
    .replace(/import \{([^}]+)\} from '@element-plus\/icons-vue'/, 'const {$1} = globalThis.__overviewIcons')
    .replace("from '@/utils/cameraManagement'", `from '${managementUrl}'`)
    .replace(/import\.meta\.env\.VITE_APP_BASE_API/g, "'/dev-api'")
}
const tileCode = compileView('../src/views/camera-overview/CameraPreview.vue')
  .replace("from './preview'", `from '${previewUrl}'`)
const { default: Preview } = await import(moduleUrl(tileCode))
globalThis.__overviewPreview = Preview
const resultMounts = [], activeResults = new Set()
globalThis.__overviewResults = { props: ['activeMetric'], setup(props) {
  const instance = { get metric() { return props.activeMetric } }
  onMounted(() => { resultMounts.push(instance); activeResults.add(instance) })
  onBeforeUnmount(() => activeResults.delete(instance))
  return () => h('div', '当前摄像头分析指标')
} }
globalThis.__overviewDetection = { emits: ['detected', 'close'], setup(_, { emit }) {
  return () => h('div', { 'data-detection': true, onDetected: id => emit('detected', id), onClose: () => emit('close') })
} }
const pageCode = compileView('../src/views/camera-overview/index.vue')
  .replace(/import \{ onBeforeRouteLeave \} from '[^']*'/, 'const onBeforeRouteLeave = () => {}')
  .replace(/import \{ ElMessage \} from '[^']*'/, 'const ElMessage = { info() {}, warning() {}, success() {} }')
  .replace(/import CameraAnalysisDrawer from '[^']*'/, 'const CameraAnalysisDrawer = { render: () => null }')
  .replace(/import useCameraStore from '[^']*'/, 'const useCameraStore = () => globalThis.__overviewStore')
  .replace(/import \{ useMonitorViewport \} from '[^']*'/, "const useMonitorViewport = () => '700px'")
  .replace(/import CameraPreview from '[^']*'/, 'const CameraPreview = globalThis.__overviewPreview')
  .replace(/import CameraResultsPanel from '[^']*'/, 'const CameraResultsPanel = globalThis.__overviewResults')
  .replace(/import XiaozhiWorkspace from '[^']*'/, 'const XiaozhiWorkspace = globalThis.__overviewDetection')
const { default: Overview } = await import(moduleUrl(pageCode))

function render(component) {
  const node = (type, text = '') => markRaw({ type, text, props: {}, style: {}, children: [], parent: null })
  const renderer = createRenderer({
    createElement: type => node(type), createText: text => node('text', text), createComment: text => node('comment', text),
    setText: (target, text) => { target.text = text },
    setElementText: (target, text) => { target.text = text; target.children = [] },
    patchProp: (target, key, old, value) => { target.props[key] = value },
    parentNode: target => target.parent,
    nextSibling: target => target.parent?.children[target.parent.children.indexOf(target) + 1] || null,
    insert(target, parent, anchor) {
      if (target.parent) target.parent.children = target.parent.children.filter(child => child !== target)
      const index = anchor ? parent.children.indexOf(anchor) : -1
      if (index < 0) parent.children.push(target)
      else parent.children.splice(index, 0, target)
      target.parent = parent
    },
    remove(target) { if (target.parent) target.parent.children = target.parent.children.filter(child => child !== target); target.parent = null }
  })
  const app = renderer.createApp(component)
  for (const control of ['icon', 'button', 'input', 'tag', 'alert', 'empty', 'select', 'option']) {
    app.component('el-' + control, { props: ['modelValue'], inheritAttrs: false, setup: (props, { attrs, slots }) => () => h(control === 'button' ? 'button' : 'div', { ...attrs, modelValue: props.modelValue, 'data-control': control }, [attrs.title || '', slots.default?.()]) })
  }
  app.component('router-link', { setup: (_, { slots }) => () => h('a', slots.default?.()) })
  app.component('el-dialog', { props: ['modelValue'], setup: (props, { slots }) => () => props.modelValue ? h('dialog', slots.default?.()) : null })
  app.directive('loading', {})
  const root = node('root')
  app.mount(root)
  const nodes = target => [target, ...target.children.flatMap(nodes)]
  const text = target => String(target.text || '') + target.children.map(text).join('')
  const select = label => nodes(root).find(target => target.props['data-control'] === 'select' && target.props['aria-label'] === label)
  return { app, all: () => nodes(root), images: () => nodes(root).filter(target => target.type === 'img'), text: () => text(root),
    select, options: label => nodes(select(label)).filter(target => target.props['data-control'] === 'option').map(target => target.props.value),
    button: label => nodes(root).find(target => target.type === 'button' && text(target).includes(label)) }
}
const camera = (cameraId = 'local') => ({ camera_id: cameraId, name: cameraId, source: cameraId.startsWith('xiaozhi:') ? 'xiaozhi' : cameraId,
  configured: true, online: null, analysis: { scene: '门岗', algorithm_ids: ['vibration'], show_overlay: false } })

test('overview streams use the authenticated same-origin raw feed and reject missing or invalid devices', () => {
  const url = cameraPreviewUrl(camera('xiaozhi:watcher-1'), '/dev-api/', '0-1')
  assert.match(url, /^\/dev-api\/video\/feed\/raw\?/)
  assert.equal(new URL(url, 'http://localhost').searchParams.get('camera_id'), 'xiaozhi:watcher-1')
  assert.doesNotMatch(url, /token|analysis|fatigue/)
  assert.match(cameraPreviewUrl(camera(), '/dev-api', 0, 'analysis'), /\/video\/feed\/analysis\?/)
  const fatigueUrl = new URL(cameraPreviewUrl(camera(), '/dev-api', 0, 'fatigue'), 'http://localhost')
  assert.equal(fatigueUrl.pathname, '/dev-api/fatigue/feed')
  assert.equal(fatigueUrl.searchParams.get('show_boxes'), '1')
  assert.equal(cameraPreviewUrl({ ...camera('rtsp'), configured: false }), '')
  assert.equal(cameraPreviewUrl(camera('xiaozhi')), '')
  assert.equal(cameraPreviewUrl(camera('invalid-camera')), '')
})

test('preview opens real video without algorithm initialization and releases it when the page is hidden', async () => {
  const enabled = ref(true), states = []
  const view = render({ setup: () => () => h(Preview, { camera: camera(), enabled: enabled.value, onStateChange: value => states.push(value) }) })
  try {
    await nextTick()
    assert.equal(view.images().length, 1)
    const image = view.images()[0]
    image.props.onLoad({ currentTarget: image })
    await nextTick()
    assert.match(view.text(), /画面已连接/)
    assert.doesNotMatch(view.text(), /local|本机摄像头/)
    enabled.value = false
    await nextTick()
    assert.equal(view.images().length, 0)
    assert.equal(states.at(-1).state, 'paused')
    enabled.value = true
    await nextTick()
    assert.equal(view.images().length, 1)
    assert.equal(states.at(-1).state, 'connecting')
  } finally { view.app.unmount() }
  assert.equal(states.at(-1).state, 'paused')
})

test('a broken stream offers reconnection and ignores late load events from the old image', async () => {
  const states = []
  const view = render({ setup: () => () => h(Preview, { camera: camera(), enabled: true, onStateChange: value => states.push(value) }) })
  try {
    const firstImage = view.images()[0]
    const firstUrl = firstImage.props.src
    firstImage.props.onError({ currentTarget: firstImage })
    await nextTick()
    assert.equal(view.images().length, 0)
    assert.match(view.text(), /暂时没有画面/)
    view.button('重新连接').props.onClick()
    await nextTick()
    assert.notEqual(view.images()[0].props.src, firstUrl)
    firstImage.props.onLoad({ currentTarget: firstImage })
    await nextTick()
    assert.equal(states.at(-1).state, 'connecting')
  } finally { view.app.unmount() }
})

test('an unconfigured camera stays visible with setup guidance and never opens another device', async () => {
  const device = reactive({ ...camera('rtsp'), configured: false })
  const view = render({ setup: () => () => h(Preview, { camera: device, enabled: true }) })
  try {
    assert.equal(view.images().length, 0)
    assert.match(view.text(), /请先配置摄像头/)
    device.configured = true
    await nextTick()
    assert.match(view.images()[0].props.src, /camera_id=rtsp/)
  } finally { view.app.unmount() }
})

async function mountOverview(devices = ['local', 'rtsp', 'xiaozhi:a', 'xiaozhi:b', 'xiaozhi:c', 'xiaozhi:d'].map(camera)) {
  const handlers = new Map(), destinations = []
  const stats = { configurationWrites: [], algorithmReads: 0 }
  globalThis.document = { hidden: false, addEventListener: (name, handler) => handlers.set(name, handler), removeEventListener: name => handlers.delete(name) }
  globalThis.window = { setInterval: () => 1, clearInterval() {} }
  const store = reactive({
    cameraId: 'local', cameraCatalog: devices, algorithms: [], deviceError: '',
    get selectedCamera() { return this.cameraCatalog.find(camera => camera.camera_id === this.cameraId) },
    selectCamera(id) { this.cameraId = id }, async loadXiaozhiDevices() {},
    async loadAlgorithms() { stats.algorithmReads++; throw new Error('Algorithm catalog unavailable') },
    async configureCamera(...args) { stats.configurationWrites.push(args) }
  })
  globalThis.__overviewStore = store
  globalThis.__overviewRouter = { push: path => destinations.push(path) }
  const view = render(Overview)
  await new Promise(resolve => setImmediate(resolve))
  await nextTick()
  return { view, store, handlers, destinations, stats }
}

test('the unified monitor keeps video stable while results expand or collapse and grid streams stay bounded', async () => {
  const { view, store, handlers, destinations, stats } = await mountOverview()
  try {
    await new Promise(resolve => setImmediate(resolve))
    await nextTick()
    assert.equal(view.images().length, 1)
    assert.match(view.images()[0].props.src, /camera_id=local/)
    const initialImage = view.images()[0]
    view.button('四画面').props.onClick()
    await nextTick()
    assert.equal(view.images().length, 4)
    assert.ok(view.images().includes(initialImage), 'Changing layout must preserve the existing camera stream')
    const nextGroup = view.all().find(target => target.props['aria-label'] === '下一组摄像头')
    nextGroup.props.onClick()
    await nextTick()
    assert.equal(view.images().length, 2)
    assert.match(view.images()[0].props.src, /camera_id=xiaozhi%3Ac/)
    view.button('单画面').props.onClick()
    await nextTick()
    assert.equal(store.cameraId, 'xiaozhi:c', 'Single view must keep the camera from the displayed group')
    assert.equal(view.images().length, 1)
    view.button('四画面').props.onClick()
    await nextTick()
    assert.equal(view.images().length, 2)
    document.hidden = true
    handlers.get('visibilitychange')()
    await nextTick()
    assert.equal(view.images().length, 0)
    document.hidden = false
    handlers.get('visibilitychange')()
    await nextTick()
    assert.equal(view.images().length, 2)
    view.button('查看大画面').props.onClick()
    await nextTick()
    assert.equal(view.images().length, 1)
    assert.equal(store.cameraId, 'xiaozhi:c')
    const beforeResults = view.images()[0]
    const mountedBefore = resultMounts.length
    view.button('收起').props.onClick()
    await nextTick()
    assert.equal(view.all().find(target => target.props['aria-label'] === '当前摄像头分析结果').style.display, 'none')
    assert.equal(view.images()[0], beforeResults)
    view.select('查看指标').props.onChange('vibration')
    await nextTick()
    assert.notEqual(view.all().find(target => target.props['aria-label'] === '当前摄像头分析结果').style.display, 'none')
    assert.deepEqual(destinations, [], 'Results must open on the same page')
    assert.equal(resultMounts.length, mountedBefore, 'Collapsing the results must retain the analysis session')
    assert.equal(view.images().length, 1)
    assert.equal(stats.configurationWrites.length, 0)
    assert.equal(stats.algorithmReads, 0, 'Monitoring uses saved device bindings without depending on the algorithm catalog')
  } finally { view.app.unmount() }
  assert.equal(handlers.size, 0)
  assert.equal(activeResults.size, 0)
})

test('selecting Xiaozhi prompts detection on the monitor and reconnects the verified physical device', async () => {
  const { view, store, destinations, stats } = await mountOverview()
  const detector = () => view.all().find(target => target.props['data-detection'])
  try {
    assert.equal(detector(), undefined)
    view.select('选择摄像头').props.onChange('rtsp')
    await nextTick()
    assert.equal(detector(), undefined)
    view.select('选择摄像头').props.onChange('xiaozhi:a')
    await nextTick()
    assert.ok(detector())
    assert.match(view.text(), /请先检测设备/)
    detector().props.onClose()
    await nextTick()
    assert.equal(detector(), undefined)
    assert.equal(store.cameraId, 'xiaozhi:a')
    const oldUrl = view.images()[0].props.src
    view.button('检测设备').props.onClick()
    await nextTick()
    await detector().props.onDetected('a')
    await nextTick()
    assert.equal(detector(), undefined)
    assert.notEqual(view.images()[0].props.src, oldUrl, 'Successful detection must reconnect an errored stream')
    view.select('选择摄像头').props.onChange('xiaozhi:b')
    await nextTick()
    await detector().props.onDetected('b')
    await nextTick()
    assert.equal(store.cameraId, 'xiaozhi:b')
    assert.equal(detector(), undefined)
    assert.deepEqual(destinations, [])
    assert.equal(stats.configurationWrites.length, 0)
  } finally { view.app.unmount() }
})

test('a missing Xiaozhi camera can be detected from the main monitor without falling back to local', async () => {
  const { view, store } = await mountOverview([camera('local'), camera('rtsp')])
  const detector = () => view.all().find(target => target.props['data-detection'])
  try {
    assert.ok(view.options('选择摄像头').includes('xiaozhi'))
    view.select('选择摄像头').props.onChange('xiaozhi')
    await nextTick()
    assert.equal(store.cameraId, 'xiaozhi')
    assert.equal(view.images().length, 0)
    assert.ok(detector())
    await view.all().find(target => target.props['aria-label'] === '刷新设备').props.onClick()
    await nextTick()
    assert.equal(store.cameraId, 'xiaozhi')
    store.loadXiaozhiDevices = async () => { store.cameraCatalog.push(camera('xiaozhi:new-device')) }
    await detector().props.onDetected('new-device')
    await nextTick()
    assert.equal(store.cameraId, 'xiaozhi:new-device')
    assert.equal(detector(), undefined)
    assert.equal(view.images().length, 1)
    assert.match(view.images()[0].props.src, /camera_id=xiaozhi%3Anew-device/)
  } finally { view.app.unmount() }
})

test('metric choices follow each camera binding and never persist display preferences as device configuration', async () => {
  const devices = [camera('local'), camera('rtsp')]
  devices[0].analysis.algorithm_ids = ['vibration', 'fatigue']
  devices[1].analysis.algorithm_ids = ['fatigue']
  const { view, store, stats } = await mountOverview(devices)
  const saved = JSON.stringify(store.cameraCatalog.map(device => device.analysis))
  try {
    assert.deepEqual(view.options('查看指标'), ['vibration', 'fatigue'])
    const image = view.images()[0], mounted = resultMounts.length
    view.select('查看指标').props.onChange('fatigue')
    await nextTick()
    assert.equal(view.select('查看指标').props.modelValue, 'fatigue')
    assert.equal(resultMounts.at(-1).metric, 'fatigue')
    assert.equal(resultMounts.length, mounted)
    assert.equal(view.images()[0], image)
    view.select('选择摄像头').props.onChange('rtsp')
    await nextTick()
    assert.deepEqual(view.options('查看指标'), ['fatigue'])
    assert.equal(view.select('查看指标').props.modelValue, 'fatigue')
    view.select('查看指标').props.onChange('vibration')
    await nextTick()
    assert.equal(view.select('查看指标').props.modelValue, 'fatigue', 'An unconfigured metric cannot be selected')
    view.select('选择摄像头').props.onChange('local')
    await nextTick()
    assert.equal(view.select('查看指标').props.modelValue, 'fatigue', 'Each camera retains only its local viewing preference')
    assert.equal(JSON.stringify(store.cameraCatalog.map(device => device.analysis)), saved)
    assert.equal(stats.configurationWrites.length, 0)
    store.cameraCatalog[0].analysis.algorithm_ids = ['vibration']
    await nextTick()
    assert.deepEqual(view.options('查看指标'), ['vibration'])
    assert.equal(view.select('查看指标').props.modelValue, 'vibration', 'Device configuration remains the source of truth')
    const currentImage = view.images()[0], source = currentImage.props.src
    assert.equal(view.select('画面显示方式'), undefined)
    assert.equal(view.all().find(target => target.props.class === 'camera-context'), undefined)
    assert.equal(view.all().filter(target => target.type === 'h1').length, 0)
    assert.doesNotMatch(view.text(), /裁切边缘|铺满画面/)
    assert.equal(view.images()[0], currentImage)
    assert.equal(view.images()[0].props.src, source)
    assert.equal(stats.configurationWrites.length, 0)
  } finally { view.app.unmount() }
})

test('the camera window fits landscape and portrait frames into available space without cropping or reconnecting', async () => {
  const previousObserver = globalThis.ResizeObserver, observers = [], states = []
  globalThis.ResizeObserver = class {
    constructor(callback) { this.callback = callback; observers.push(this) }
    observe(target) { this.target = target }
    disconnect() { this.disconnected = true }
    resize(width, height) { this.callback([{ target: this.target, contentRect: { width, height } }]) }
  }
  const view = render({ setup: () => () => h(Preview, { camera: camera(), enabled: true, onStateChange: state => states.push(state) }) })
  try {
    const image = view.images()[0], url = image.props.src
    const frame = view.all().find(target => target.props.class === 'preview-frame')
    observers[0].resize(1000, 600)
    image.naturalWidth = 1280; image.naturalHeight = 720
    image.props.onLoad({ currentTarget: image })
    await nextTick()
    assert.equal(states.at(-1).width, 1280)
    assert.equal(states.at(-1).height, 720)
    assert.deepEqual(frame.props.style, { width: '1000px', height: '562.5px' })
    const updates = states.length
    observers[0].resize(600, 600)
    await nextTick()
    assert.deepEqual(frame.props.style, { width: '600px', height: '337.5px' })
    assert.equal(view.images()[0], image)
    assert.equal(view.images()[0].props.src, url)
    assert.equal(states.length, updates)
    for (const [width, height, expected] of [
      [640, 480, { width: '600px', height: '450px' }],
      [720, 1280, { width: '337.5px', height: '600px' }],
      [640, 640, { width: '600px', height: '600px' }]
    ]) {
      image.naturalWidth = width; image.naturalHeight = height
      image.props.onLoad({ currentTarget: image })
      await nextTick()
      assert.deepEqual(frame.props.style, expected)
      assert.equal(view.images()[0], image)
      assert.equal(image.props.src, url)
    }
    const styles = readFileSync(new URL('../src/views/camera-overview/CameraPreview.vue', import.meta.url), 'utf8')
    assert.match(styles, /object-fit:contain/)
    assert.doesNotMatch(styles, /object-fit:cover/)
  } finally {
    view.app.unmount()
    globalThis.ResizeObserver = previousObserver
  }
  assert.equal(observers[0].disconnected, true)
})

test('workspace gives a 640x480 camera its fitted width and all remaining space to the results without restarting monitoring', async () => {
  const previousObserver = globalThis.ResizeObserver, observers = []
  globalThis.ResizeObserver = class {
    constructor(callback) { this.callback = callback; this.targets = []; observers.push(this) }
    observe(target) { this.targets.push(target) }
    disconnect() { this.disconnected = true }
    resize(target, width, height) { this.callback([{ target, contentRect: { width, height }, borderBoxSize: [{ blockSize: height }] }]) }
  }
  const { view, stats } = await mountOverview([camera()])
  try {
    const workspace = view.all().find(target => target.props.class?.includes('overview-workspace'))
    const observer = observers.find(observer => observer.targets.includes(workspace))
    const image = view.images()[0], url = image.props.src, mountedResults = resultMounts.length
    image.naturalWidth = 640; image.naturalHeight = 480
    image.props.onLoad({ currentTarget: image })
    observer.resize(workspace, 1600, 700)
    await nextTick()
    const fittedWidth = 700 * 4 / 3
    assert.ok(Math.abs(parseFloat(workspace.props.style['--monitor-video-width']) - fittedWidth) < 0.001)
    observer.resize(workspace, 2200, 700)
    await nextTick()
    assert.ok(Math.abs(parseFloat(workspace.props.style['--monitor-video-width']) - fittedWidth) < 0.001,
      'Extra screen width belongs to the results instead of empty space around the fitted video')
    observer.resize(workspace, 1000, 900)
    await nextTick()
    assert.equal(parseFloat(workspace.props.style['--monitor-video-width']), 692,
      'A narrow workspace must preserve enough room for readable results')
    view.button('收起').props.onClick()
    await nextTick()
    view.select('查看指标').props.onChange('vibration')
    await nextTick()
    assert.equal(view.images()[0], image)
    assert.equal(image.props.src, url)
    assert.equal(resultMounts.length, mountedResults)
    assert.equal(stats.configurationWrites.length, 0)
  } finally {
    view.app.unmount()
    globalThis.ResizeObserver = previousObserver
  }
  assert.ok(observers.every(observer => observer.disconnected))
})

test('home, overview and monitoring aliases share one pinned real-time monitoring entry', async () => {
  const source = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const declaration = source.split('export const constantRoutes =')[1].split('// 动态路由')[0]
    .replace(/\(\)\s*=>\s*import\('[^']+'\)/g, '() => Promise.resolve({render:()=>null})')
  const routes = new Function('Layout', `return (${declaration.trim()})`)({ render: () => null })
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push('/camera/overview')
  assert.equal(router.currentRoute.value.name, 'ConfiguredVideoMonitor')
  assert.equal(router.currentRoute.value.meta.affix, true)
  for (const path of ['/', '/index', '/camera/live']) {
    await router.push(path)
    assert.equal(router.currentRoute.value.path, '/monitor/druid')
  }
  await router.push('/algorithms')
  assert.equal(router.currentRoute.value.name, 'AnalysisAlgorithms')
  await router.push('/cameras')
  assert.equal(router.currentRoute.value.name, 'CameraAssignments')
})

test('an unavailable analysis feed falls back to raw video and can retry without opening parallel streams', async () => {
  const states = []
  const view = render({ setup: () => () => h(Preview, { camera: camera(), enabled: true, feed: 'analysis', onStateChange: value => states.push(value) }) })
  try {
    const analysisImage = view.images()[0]
    assert.match(analysisImage.props.src, /\/feed\/analysis\?/)
    analysisImage.props.onError({ currentTarget: analysisImage })
    await nextTick()
    assert.equal(view.images().length, 1)
    const rawImage = view.images()[0]
    assert.match(rawImage.props.src, /\/feed\/raw\?/)
    assert.equal(states.at(-1).feed, 'raw')
    rawImage.props.onLoad({ currentTarget: rawImage })
    await nextTick()
    assert.match(view.text(), /已显示原始画面/)
    view.button('重新尝试').props.onClick()
    await nextTick()
    assert.equal(view.images().length, 1)
    assert.match(view.images()[0].props.src, /\/feed\/analysis\?/)
  } finally { view.app.unmount() }
})
