import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, h, markRaw, nextTick, ref } from 'vue'

test('embedded psychological results open no video and clear stale scores when analysis video is unavailable', async () => {
  const source = readFileSync(new URL('../src/views/monitor/druid/WellbeingMonitor.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  let switchers = 0
  globalThis.__wellbeingResultsStore = { source: 'local', cameraId: 'local', xiaozhiDeviceId: '', xiaozhiDevices: [], deviceError: '' }
  globalThis.__wellbeingResultsSwitcher = { setup() { switchers++; return () => h('select') } }
  globalThis.__wellbeingResultsPanel = { setup: (_, { slots }) => () => h('div', [slots.psychological?.(), slots.fatigue?.(), slots.notifications?.()]) }
  const cameraUrl = new URL('../src/utils/camera.js', import.meta.url).href
  const code = compileScript(descriptor, { id: 'wellbeing-results-test', inlineTemplate: true }).content
    .replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
    .replace(/import \{ ElMessage \} from '[^']*'/, 'const ElMessage = { info() {}, warning() {}, success() {} }')
    .replace(/import \{ getToken \} from '[^']*'/, "const getToken = () => ''")
    .replace(/import CameraSwitcher from '[^']*'/, 'const CameraSwitcher = globalThis.__wellbeingResultsSwitcher')
    .replace(/import MonitorPanel from '[^']*'/, 'const MonitorPanel = globalThis.__wellbeingResultsPanel')
    .replace(/import useCameraStore from '[^']*'/, 'const useCameraStore = () => globalThis.__wellbeingResultsStore')
    .replace("from '@/utils/camera'", `from '${cameraUrl}'`)
    .replace(/import \{ Message, Refresh, User \} from '[^']*'/, 'const Message = {render:()=>null}, Refresh = Message, User = Message')
    .replace(/import\.meta\.env\.VITE_APP_BASE_API/g, "'/dev-api'")
  const { default: Results } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
  const originalFetch = globalThis.fetch
  const requests = [], listeners = new Map()
  globalThis.document = { hidden: false, addEventListener: (name, handler) => listeners.set(name, handler), removeEventListener: name => listeners.delete(name) }
  globalThis.fetch = async (url, options) => {
    requests.push({ url, signal: options.signal })
    return { ok: true, json: async () => ({ analyzing: true, has_results: true, results: { e12: 75 }, message: '持续评估中' }) }
  }
  const node = (type, text = '') => markRaw({ type, text, props: {}, style: {}, children: [], parent: null })
  const renderer = createRenderer({
    createElement: type => node(type), createText: text => node('text', text), createComment: text => node('comment', text),
    setText: (target, text) => { target.text = text }, setElementText: (target, text) => { target.text = text; target.children = [] },
    patchProp: (target, key, old, value) => { target.props[key] = value }, parentNode: target => target.parent,
    nextSibling: target => target.parent?.children[target.parent.children.indexOf(target) + 1] || null,
    insert(target, parent, anchor) {
      if (target.parent) target.parent.children = target.parent.children.filter(child => child !== target)
      const index = anchor ? parent.children.indexOf(anchor) : -1
      if (index < 0) parent.children.push(target); else parent.children.splice(index, 0, target)
      target.parent = parent
    },
    remove(target) { if (target.parent) target.parent.children = target.parent.children.filter(child => child !== target); target.parent = null }
  })
  const available = ref(true)
  const app = renderer.createApp({ setup: () => () => h(Results, { resultsOnly: true, signalAvailable: available.value }) })
  for (const control of ['icon', 'tag', 'button', 'checkbox', 'alert']) {
    app.component('el-' + control, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h('div', attrs, [attrs.title || '', attrs.description || '', slots.default?.()]) })
  }
  app.component('router-link', { render: () => h('a') })
  const root = node('root')
  const all = current => [current, ...current.children.flatMap(all)]
  const text = current => String(current.text || '') + current.children.map(text).join('')
  const settled = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
  try {
    app.mount(root)
    await settled()
    assert.equal(all(root).filter(target => target.type === 'img').length, 0)
    assert.equal(switchers, 0)
    assert.equal(requests.length, 1)
    assert.match(requests[0].url, /\/video\/results\?camera_id=local/)
    assert.match(text(root), /幸福指数综合评估/)
    available.value = false
    await settled()
    assert.equal(requests[0].signal.aborted, true)
    assert.equal(requests.length, 1)
    assert.doesNotMatch(text(root), /幸福指数综合评估/)
    assert.match(text(root), /振动分析暂时不可用/)
    available.value = true
    await settled()
    assert.equal(requests.length, 2)
    assert.match(text(root), /幸福指数综合评估/)
  } finally {
    app.unmount()
    globalThis.fetch = originalFetch
  }
  assert.equal(listeners.size, 0)
  assert.equal(requests.at(-1).signal.aborted, true)
})
