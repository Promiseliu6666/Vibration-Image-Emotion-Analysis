import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { compile, parse as parseTemplate } from '@vue/compiler-dom'
import { parse } from '@vue/compiler-sfc'
import * as Vue from 'vue'
import { renderToString } from 'vue/server-renderer'

const source = readFileSync(new URL('../src/views/fatigue/index.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)

function findOverlay(node) {
  if (node.tag === 'svg' && node.props.some(prop => (
    prop.name === 'class' && prop.value?.content === 'detection-overlay'
  ))) return node
  for (const child of node.children || []) {
    const match = findOverlay(child)
    if (match) return match
  }
}

// Compile the actual page overlay, so a unit mismatch in the template regresses here.
const overlay = findOverlay(parseTemplate(descriptor.template.content))
assert.ok(overlay, 'The fatigue page must expose a detection overlay')
const { code } = compile(overlay.loc.source, { mode: 'function', prefixIdentifiers: true })
const render = new Function('Vue', code)(Vue)

async function renderOverlay(width, height, showBoxes = true) {
  return renderToString(Vue.createSSRApp({
    render,
    setup: () => ({
      showBoxes,
      videoSize: { width, height },
      detectionBoxes: [{
        name: 'face', x1: 0.25, y1: 0.25, width: 0.5, height: 0.5,
        labelY: 0.2, label: 'face', color: '#a1e26e'
      }],
      poseSegments: [{ x1: 0.25, y1: 0.25, x2: 0.75, y2: 0.75 }],
      poseKeypoints: [{ x: 0.5, y: 0.5 }]
    })
  }))
}

for (const [width, height] of [[640, 480], [1280, 720], [480, 640]]) {
  test(`overlay uses video pixels at ${width}x${height}`, async () => {
    const html = await renderOverlay(width, height)
    assert.ok(html.includes(`viewBox="0 0 ${width} ${height}"`))
    assert.ok(html.includes(`<rect x="${width / 4}" y="${height / 4}" width="${width / 2}" height="${height / 2}"`))
    assert.ok(html.includes(`<text x="${width / 4}" y="${height * 0.2}"`))
    assert.ok(html.includes(`<line x1="${width / 4}" y1="${height / 4}" x2="${width * 0.75}" y2="${height * 0.75}"`))
    assert.ok(html.includes(`<circle cx="${width / 2}" cy="${height / 2}" r="3"`))
    assert.match(html, /<circle[^>]*vector-effect="non-scaling-stroke"/)
  })
}

test('hiding detection boxes removes the overlay', async () => {
  assert.doesNotMatch(await renderOverlay(640, 480, false), /<svg/)
})
