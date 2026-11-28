import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import vm from 'node:vm'

const embeddedSource = readFileSync(new URL('../../xiaozhi-study/static/health-embedded.js', import.meta.url), 'utf8')
const consoleSource = readFileSync(new URL('../../xiaozhi-study/static/console.js', import.meta.url), 'utf8')

function embed({ action = 'detect-device', portal = 'http://127.0.0.1:5173', role = null } = {}) {
  const events = new Map(), messages = [], elements = new Map(), classes = new Set(), timers = new Map()
  let starts = 0
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: '', hidden: false, disabled: false, open: false,
      showModal() { this.open = true }, addEventListener: (name, handler) => events.set(id + ':' + name, handler)
    })
    return elements.get(id)
  }
  const context = vm.createContext({
    URLSearchParams, location: { search: '?' + new URLSearchParams({ embedded: 'health', portal, action }) },
    window: { parent: { postMessage: (message, origin) => messages.push({ message, origin }) } },
    document: { body: { classList: { add: name => classes.add(name) } }, head: { append() {} },
      createElement: () => ({}), getElementById: id => id === 'studyTaskForm' ? null : element(id),
      querySelectorAll: () => [], addEventListener: (name, handler) => events.set(name, handler) },
    setTimeout: handler => { timers.set(1, handler); return 1 }, clearTimeout: id => timers.delete(id),
    workspaceUser: role ? { role } : null, showPreview: true, clearPreview() {},
    openWizard: async () => { starts++ }
  })
  vm.runInContext(embeddedSource, context)
  return { context, events, messages, classes, timers, element, starts: () => starts }
}

test('the inline detector waits for permissions and only offers detection to administrators', () => {
  const ui = embed()
  assert.ok(ui.classes.has('health-device-detection'))
  assert.equal(ui.element('wizard').open, true)
  assert.equal(ui.element('verify').disabled, true)
  assert.equal(ui.starts(), 0)
  ui.context.workspaceUser = { role: 'admin' }
  ui.events.get('workspace:ready')()
  assert.equal(ui.starts(), 1)
  assert.equal(ui.element('rescanUsb').hidden, false)
  assert.equal(ui.timers.size, 0)
  ui.events.get('workspace:device-detected')({ detail: { deviceId: 'watcher-123' } })
  assert.equal(ui.messages[0].origin, 'http://127.0.0.1:5173')
  assert.equal(ui.messages[0].message.type, 'xiaozhi-device-detected')
  assert.equal(ui.messages[0].message.deviceId, 'watcher-123')
  ui.events.get('wizard:close')()
  assert.equal(ui.messages[1].message.type, 'xiaozhi-detection-closed')
  const viewer = embed({ role: 'viewer' })
  assert.equal(viewer.starts(), 0)
  assert.equal(viewer.element('verify').disabled, true)
  assert.equal(viewer.element('rescanUsb').hidden, true)
  assert.match(viewer.element('wizardMessage').textContent, /管理员/)
})

test('ordinary embedded pages and untrusted parent origins cannot open the inline detector', () => {
  for (const options of [{ action: '' }, { portal: 'http://untrusted.example' }]) {
    const ui = embed(options)
    assert.equal(ui.classes.has('health-device-detection'), false)
    assert.equal(ui.events.has('workspace:device-detected'), false)
    assert.equal(ui.starts(), 0)
  }
})

test('detection announces a device only after this collector has fresh frames and completed analysis', () => {
  const events = [], controls = Object.fromEntries(['usbPort', 'wizardMessage', 'physicalIdentity', 'verify'].map(id => [id, {}]))
  controls.usbPort.value = 'COM5'
  controls.steps = { children: Array.from({ length: 4 }, () => ({ classList: { toggle() {} } })) }
  controls.device = {}
  const now = Date.now() / 1000
  const collector = { collector_pid: 123, port: 'COM5', device_id: 'watcher-123', identified: true }
  const live = { last_received: now, last_analyzed: now - 100, analysis_fresh: false }
  const context = vm.createContext({
    $: id => controls[id], verifying: now - 1, wizardPid: 123, Date,
    data: { capture: { ports: ['COM5'], collectors: [collector] }, devices: [{ device_id: 'watcher-123', live }] },
    choose: id => { context.selected = id },
    document: { dispatchEvent: event => events.push(event) },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail } }
  })
  vm.runInContext(consoleSource.slice(consoleSource.indexOf('function renderWizard()'), consoleSource.indexOf('function notifyPhoneWarnings')), context)
  context.renderWizard()
  assert.equal(events.length, 0)
  live.last_analyzed = now; live.analysis_fresh = true
  collector.collector_pid = 999
  context.renderWizard()
  assert.equal(events.length, 0)
  collector.collector_pid = 123
  context.renderWizard()
  assert.equal(events.length, 1)
  assert.equal(events[0].type, 'workspace:device-detected')
  assert.equal(events[0].detail.deviceId, 'watcher-123')
  context.renderWizard()
  assert.equal(events.length, 1)
})

test('rescanning USB preserves the embedded wizard instead of closing its parent dialog', async () => {
  let closed = 0, searches = 0
  const controls = { wizard: { close: () => closed++ }, heroConnect: {}, rescanUsb: {}, historyRange: {}, showTests: {} }
  const context = vm.createContext({ $: id => controls[id], verifying: 0,
    openWizard: async () => searches++, renderDevices() {} })
  vm.runInContext(consoleSource.split('\n').find(line => line.startsWith("$('heroConnect').onclick=")), context)
  await controls.rescanUsb.onclick()
  assert.equal(searches, 1)
  assert.equal(closed, 0)
  context.verifying = 1
  await controls.rescanUsb.onclick()
  assert.equal(searches, 1)
})
