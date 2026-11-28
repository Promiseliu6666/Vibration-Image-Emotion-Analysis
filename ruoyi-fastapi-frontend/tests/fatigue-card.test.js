import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { compile } from '@vue/compiler-dom'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { fatiguePresentation as present } from '../src/utils/fatiguePresentation.js'

const { descriptor } = parse(readFileSync(new URL('../src/components/FatigueStatusCard/index.vue', import.meta.url), 'utf8'))
compileScript(descriptor, { id: 'fatigue-card' })
const { code } = compile(descriptor.template.content, { mode: 'function', prefixIdentifiers: true })
const render = new Function('Vue', code)(Vue)
async function card(result = {}, error = '') {
  return renderToString(Vue.createSSRApp({ render, setup: () => ({ result, error, resetting: false, showMetricHelp: false, view: present(result, error) }) }))
}
test('incomplete collection never displays process mechanics or a safe zero', async () => {
  const result = { warmup_progress: 264, warmup_target: 720, feature_buffer: 0, feature_target: 30 }
  assert.equal(present(result).value, null)
  const html = await card(result)
  assert.match(html, /暂未出分/)
  assert.match(html, /—/)
  assert.doesNotMatch(html, /建立基线|准备进度|了解你|行为基线|动态特征|校准|CPU|90 秒|24%|class="grade[^"]*active/)
})
test('invalid numeric inputs never become safe zero scores', () => {
  for (const fatigue_score of [null, undefined, '', '  ', NaN, Infinity, false, [], {}]) {
    assert.equal(present({ fatigue_score }).ready, false)
    assert.equal(present({ fatigue_score }).value, null)
  }
})
test('zero is valid and boundaries preserve one decimal', async () => {
  for (const [fatigue_score, tone, value] of [[0, 'alert', 0], [.449, 'alert', 44.9], [.45, 'drowsy', 45], [.7, 'drowsy', 70], [.701, 'fatigued', 70.1]]) {
    const view = present({ fatigue_score })
    assert.equal(view.ready, true)
    assert.equal(view.tone, tone)
    assert.equal(view.value, value)
    const html = await card({ fatigue_score })
    assert.match(html, new RegExp(value.toFixed(1)))
    assert.equal((html.match(/class="grade [^"]*active/g) || []).length, 1)
  }
})
test('wakefulness fallback remains inverse and zero direct takes priority', () => {
  assert.equal(present({ score_ema: .8 }).value, 20)
  assert.equal(present({ fatigue_score: 0, score_ema: .1 }).value, 0)
})
test('error and missing face suppress stale scores without exposing internal errors', async () => {
  assert.equal(present({ fatigue_score: 0, face_detected: false }).ready, false)
  const html = await card({ fatigue_score: 0 }, 'CPU internal calibration failure')
  assert.match(html, /数据暂不可用/)
  assert.doesNotMatch(html, /CPU internal|class="grade[^"]*active/)
})
test('all grades and boundaries stay visible while pending', async () => {
  const html = await card()
  for (const text of ['清醒', '轻度疲劳', '明显疲劳', '0–&lt;45', '45–70', '&gt;70', '重新检测', '指标说明']) assert.ok(html.includes(text), text)
  assert.match(html, /aria-expanded="false"/)
  assert.doesNotMatch(html, /分值越高，疲劳程度越高。/)
})

test('supporting indicators show actual percentages and keep missing data neutral', async () => {
  const result = {face_detected:true,last_step:{valid:true,features:{perclos:.125,mouth_open_ratio:0,kpt_visibility:.96}}}
  const view = present(result)
  assert.equal(view.metrics[0].text,'12.5%')
  assert.equal(view.metrics[1].text,'0.0%')
  assert.equal(view.metrics[2].text,'—')
  const html=await card(result)
  for(const label of ['疲劳指数综合评估','行为监测指标','闭眼时间占比','姿态信号完整度','指标说明','12.5%']) assert.ok(html.includes(label),label)
})
