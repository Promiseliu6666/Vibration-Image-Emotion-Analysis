import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createRenderer, h, nextTick, reactive, ref } from 'vue'
import { cameraAnalysis, cameraConnectionState, filterCameras } from '../src/utils/cameraManagement.js'

test('configured cameras with unverified video are distinct from live and missing feeds', () => {
  assert.equal(cameraConnectionState({ configured: true, online: null }).type, 'info')
  assert.equal(cameraConnectionState({ configured: true, online: true }).label, '有画面')
  assert.equal(cameraConnectionState({ configured: true, online: false }).type, 'warning')
  assert.equal(cameraConnectionState({ configured: false, online: null }).label, '待配置连接')
})

test('device search combines source, saved algorithm and scene while retaining legacy configurations', () => {
  const cameras = [
    { camera_id: 'local', name: '本机摄像头', source: 'local', analysis: { algorithm_id: 'vibration', scene: '门岗' } },
    { camera_id: 'xiaozhi:usb', name: '值班摄像头', source: 'xiaozhi', analysis: { algorithm_ids: ['vibration', 'fatigue'], scene: '值班室' } }
  ]
  assert.deepEqual(filterCameras(cameras, { search: '值班', source: 'xiaozhi', algorithm: 'fatigue' }).map(camera => camera.camera_id), ['xiaozhi:usb'])
  assert.deepEqual(filterCameras(cameras, { algorithm: 'vibration' }).map(camera => camera.camera_id), ['local', 'xiaozhi:usb'])
  const draft = cameraAnalysis(cameras[1])
  draft.algorithm_ids.pop()
  assert.deepEqual(cameras[1].analysis.algorithm_ids, ['vibration', 'fatigue'])
})

const messages = { success: [], confirms: [], discard: false }
globalThis.__cameraEditorMessages = {
  ElMessage: { success: message => messages.success.push(message) },
  ElMessageBox: { confirm: async message => {
    messages.confirms.push(message)
    if (!messages.discard) throw new Error('continue editing')
  } }
}
const editorSource = readFileSync(new URL('../src/components/CameraAnalysisDrawer/index.vue', import.meta.url), 'utf8')
const { descriptor } = parse(editorSource)
const editorCode = compileScript(descriptor, { id: 'camera-editor-test', inlineTemplate: true }).content
  .replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
  .replace(/import \{ ElMessage, ElMessageBox \} from '[^']*'/, 'const { ElMessage, ElMessageBox } = globalThis.__cameraEditorMessages')
  .replace(/import \{ VideoCamera \} from '[^']*'/, 'const VideoCamera = { render: () => null }')
  .replace(/import useCameraStore from '[^']*'/, 'const useCameraStore = () => globalThis.__cameraEditorStore')
  .replace("from '@/utils/cameraManagement'", `from '${new URL('../src/utils/cameraManagement.js', import.meta.url).href}'`)
const { default: Editor } = await import(`data:text/javascript;base64,${Buffer.from(editorCode).toString('base64')}`)

async function mountEditor({ preferred = '', analysis } = {}) {
  messages.success = []; messages.confirms = []; messages.discard = false
  const camera = reactive({ camera_id: 'local', name: '本机摄像头', source: 'local', configured: true,
    analysis: analysis || { scene: '门岗', algorithm_ids: ['vibration'], show_overlay: false } })
  const calls = [], monitored = []
  let fail = false
  const store = reactive({
    algorithms: [
      { id: 'vibration', name: '振动分析', selectable: true, scenes: ['门岗'], sources: ['local'], metrics: [] },
      { id: 'fatigue', name: '疲劳检测', selectable: true, scenes: ['值班室'], sources: ['local'], metrics: [] }
    ],
    async configureCamera(id, config) {
      calls.push({ id, config })
      if (fail) throw new Error('network failure')
      camera.analysis = config
      return config
    },
    async loadAlgorithms() {}
  })
  globalThis.__cameraEditorStore = store
  const opened = ref(true)
  function node(type, text = '') { return { type, text, props: {}, children: [], parent: null } }
  const renderer = createRenderer({
    createElement: node, createText: text => node('text', text), createComment: text => node('comment', text),
    setText: (target, text) => { target.text = text }, setElementText: (target, text) => { target.text = text },
    patchProp: (target, key, old, value) => { target.props[key] = value },
    parentNode: target => target.parent, nextSibling: () => null,
    insert(target, parent) { target.parent = parent; parent.children.push(target) },
    remove(target) { if (target.parent) target.parent.children = target.parent.children.filter(child => child !== target) }
  })
  const app = renderer.createApp({ setup: () => () => h(Editor, {
    modelValue: opened.value, camera, preferredAlgorithm: preferred,
    'onUpdate:modelValue': value => { opened.value = value }, onMonitor: id => monitored.push(id)
  }) })
  for (const name of ['drawer', 'form', 'form-item', 'select', 'option', 'checkbox-group', 'checkbox', 'switch', 'empty', 'alert', 'tag', 'icon', 'button']) {
    app.component('el-' + name, { props: ['modelValue'], inheritAttrs: false, setup: (props, { attrs, slots }) => () => {
      if (name === 'drawer' && !props.modelValue) return null
      return h(name === 'button' ? 'button' : 'div', { ...attrs, modelValue: props.modelValue, 'data-control': name }, [name === 'alert' ? attrs.title : '', slots.default?.(), slots.footer?.()])
    } })
  }
  const root = node('root')
  app.mount(root)
  await nextTick()
  const collect = current => [current, ...current.children.flatMap(collect)]
  const controls = name => collect(root).filter(target => target.props['data-control'] === name)
  const text = target => target.text + target.children.map(text).join('')
  const button = label => controls('button').find(target => text(target).includes(label))
  const update = async (control, value) => { controls(control)[0].props['onUpdate:modelValue'](value); await nextTick() }
  const click = async label => { await button(label).props.onClick(); await nextTick() }
  return { app, camera, calls, monitored, opened, controls, update, click, text: () => text(root), setFail: value => { fail = value } }
}

test('assigning from an algorithm adds a draft without changing the saved camera until confirmation', async () => {
  const view = await mountEditor({ preferred: 'fatigue' })
  try {
    assert.deepEqual(view.controls('checkbox-group')[0].props.modelValue, ['vibration', 'fatigue'])
    assert.deepEqual(view.camera.analysis.algorithm_ids, ['vibration'])
    assert.equal(view.calls.length, 0)
    await view.click('保存并监测')
    assert.deepEqual(view.calls[0].config.algorithm_ids, ['vibration', 'fatigue'])
    assert.deepEqual(view.monitored, ['local'])
    assert.equal(view.opened.value, false)
  } finally { view.app.unmount() }
})

test('failed saves retain the draft and existing configuration and never navigate to monitoring', async () => {
  const view = await mountEditor()
  try {
    await view.update('select', ' 值班室 ')
    view.setFail(true)
    await view.click('保存并监测')
    assert.equal(view.camera.analysis.scene, '门岗')
    assert.equal(view.controls('select')[0].props.modelValue, ' 值班室 ')
    assert.equal(view.opened.value, true)
    assert.deepEqual(view.monitored, [])
    assert.match(view.text(), /配置保存失败/)
    view.setFail(false)
    await view.click('保存并监测')
    assert.equal(view.calls[1].id, 'local')
    assert.equal(view.calls[1].config.scene, '值班室')
    assert.deepEqual(view.monitored, ['local'])
  } finally { view.app.unmount() }
})

test('cancelling an edited assignment offers to keep editing before discarding', async () => {
  const view = await mountEditor()
  try {
    await view.update('select', '值班室')
    await view.click('取消')
    assert.equal(view.opened.value, true)
    assert.equal(messages.confirms.length, 1)
    messages.discard = true
    await view.click('取消')
    assert.equal(view.opened.value, false)
    assert.equal(view.camera.analysis.scene, '门岗')
    assert.equal(view.calls.length, 0)
  } finally { view.app.unmount() }
})

test('empty algorithm selection cannot save and removing fatigue clears its overlay setting', async () => {
  const view = await mountEditor({ analysis: { scene: '门岗', algorithm_ids: ['vibration', 'fatigue'], show_overlay: true } })
  try {
    await view.update('checkbox-group', [])
    await view.click('保存配置')
    assert.equal(view.calls.length, 0)
    assert.match(view.text(), /请至少选择一种分析算法/)
    await view.update('checkbox-group', ['vibration'])
    await view.click('保存配置')
    assert.equal(view.calls[0].config.show_overlay, false)
    assert.deepEqual(view.monitored, [])
  } finally { view.app.unmount() }
})

test('invalid scenes stay editable without sending a request', async () => {
  const view = await mountEditor()
  try {
    for (const scene of ['   ', '场'.repeat(81)]) {
      await view.update('select', scene)
      await view.click('保存配置')
      assert.equal(view.calls.length, 0)
      assert.equal(view.opened.value, true)
      assert.match(view.text(), /应用场景须为/)
    }
    assert.equal(view.camera.analysis.scene, '门岗')
  } finally { view.app.unmount() }
})
