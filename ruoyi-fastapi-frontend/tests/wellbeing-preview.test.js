import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse, compileScript } from '@vue/compiler-sfc'
import { ref } from 'vue'
import { cameraQueryString, toCameraId } from '../src/utils/camera.js'

test('parallel preview keeps selected Watcher analysis live while other tiles use raw video', () => {
  const source = readFileSync(new URL('../src/views/monitor/druid/WellbeingMonitor.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, {id:'preview-test'})
  const declaration = script.scriptSetupAst.flatMap(node => node.declarations || [])
    .find(node => node.id.name === 'deviceStreamUrl')
  assert.ok(declaration)
  const selected = ref('watcher-1')
  const deviceStreamUrl = new Function('baseURL', 'cameraQueryString', 'toCameraId', 'parallelRevisions', 'xiaozhiDevice',
    `return (${descriptor.scriptSetup.content.slice(declaration.init.start, declaration.init.end)})`
  )('/dev-api', cameraQueryString, toCameraId, ref(new Map()), selected)
  assert.match(deviceStreamUrl('watcher-1'), /\/feed\/analysis\?camera_id=xiaozhi%3Awatcher-1/)
  assert.match(deviceStreamUrl('watcher-2'), /\/feed\/raw\?camera_id=xiaozhi%3Awatcher-2/)
  selected.value = 'watcher-2'
  assert.match(deviceStreamUrl('watcher-1'), /\/feed\/raw\?/) 
  assert.match(deviceStreamUrl('watcher-2'), /\/feed\/analysis\?/) 
})
