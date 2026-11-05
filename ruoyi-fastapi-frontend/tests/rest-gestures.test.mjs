import test from 'node:test'
import assert from 'node:assert/strict'
import { GestureGate, interpretGesture, eligibleRestGesture } from '../src/utils/restGestures.js'
const observe = (gate, label, time, frame, score = 0.9) => gate.update(label, score, time, frame)
const hold = (gate, label, start = 0, prefix = 'frame') => [observe(gate, label, start, `${prefix}-1`), observe(gate, label, start + 500, `${prefix}-2`), observe(gate, label, start + 1000, `${prefix}-3`)]

test('confident open palm needs both hold time and distinct frames', () => {
  const states = hold(new GestureGate(), 'open_palm')
  assert.deepEqual(states[0], { trigger: null, progress: 0, label: 'open_palm' })
  assert.equal(states[1].progress, 0.5)
  assert.deepEqual(states[2], { trigger: 'open_palm', progress: 1, label: 'open_palm' })
})
test('replayed frames neither count nor advance hold progress', () => {
  const gate = new GestureGate()
  observe(gate, 'thumb_up', 0, 'a')
  assert.equal(observe(gate, 'thumb_up', 1000, 'a').progress, 0)
  const two = observe(gate, 'thumb_up', 1100, 'b')
  assert.equal(two.trigger, null); assert.ok(two.progress < 1)
  assert.equal(observe(gate, 'thumb_up', 1200, 'c').trigger, 'thumb_up')
})
test('older frame replay is ignored even when a fresh frame intervened', () => {
  const gate = new GestureGate()
  observe(gate, 'open_palm', 0, 'a'); observe(gate, 'open_palm', 500, 'b')
  assert.equal(observe(gate, 'open_palm', 1100, 'a').progress, 0.5)
  assert.equal(observe(gate, 'open_palm', 1200, 'c').trigger, 'open_palm')
})
test('low confidence or no hand clears the stable window', () => {
  for (const label of ['open_palm', null]) {
    const gate = new GestureGate()
    observe(gate, 'open_palm', 0, 'a'); observe(gate, 'open_palm', 500, 'b')
    assert.equal(observe(gate, label, 800, 'c', label ? 0.3 : 0.9).label, null)
    assert.equal(observe(gate, 'open_palm', 1100, 'd').progress, 0)
    assert.equal(observe(gate, 'open_palm', 1600, 'e').trigger, null)
    assert.equal(observe(gate, 'open_palm', 2100, 'f').trigger, 'open_palm')
  }
})
test('changing the gesture starts a new hold window', () => {
  const gate = new GestureGate()
  observe(gate, 'open_palm', 0, 'a'); observe(gate, 'open_palm', 600, 'b')
  assert.equal(observe(gate, 'thumb_up', 800, 'c').progress, 0)
  assert.equal(observe(gate, 'thumb_up', 1300, 'd').trigger, null)
  assert.equal(observe(gate, 'thumb_up', 1800, 'e').trigger, 'thumb_up')
})
test('a held gesture cannot retrigger after cooldown without release', () => {
  const gate = new GestureGate()
  assert.equal(hold(gate, 'open_palm')[2].trigger, 'open_palm')
  for (let i = 0; i < 16; i++) assert.equal(observe(gate, 'open_palm', 1500 + i * 500, `held-${i}`).trigger, null)
  observe(gate, null, 9600, 'released')
  assert.equal(hold(gate, 'open_palm', 10000, 'again')[2].trigger, 'open_palm')
})
test('cooldown is global and excludes early hold time for the next gesture', () => {
  const gate = new GestureGate(); hold(gate, 'open_palm')
  assert.equal(observe(gate, 'thumb_up', 1500, 't1').trigger, null)
  assert.equal(observe(gate, 'thumb_up', 3000, 't2').progress, 0)
  assert.equal(observe(gate, 'thumb_up', 3500, 't3').progress, 0)
  assert.equal(observe(gate, 'thumb_up', 4000, 't4').trigger, null)
  assert.equal(observe(gate, 'thumb_up', 4500, 't5').trigger, 'thumb_up')
})
test('a long frame gap requires a new stable window', () => {
  const gate = new GestureGate({ maxGapMs: 1500 })
  observe(gate, 'thumb_up', 0, 'a'); observe(gate, 'thumb_up', 500, 'b')
  assert.equal(observe(gate, 'thumb_up', 3000, 'c').progress, 0)
  assert.equal(observe(gate, 'thumb_up', 3500, 'd').trigger, null)
  assert.equal(observe(gate, 'thumb_up', 4000, 'e').trigger, 'thumb_up')
})
test('clock rollback and reset clear stale state', () => {
  const gate = new GestureGate(); hold(gate, 'open_palm', 1000)
  assert.equal(observe(gate, 'thumb_up', 10, 'new-1').progress, 0)
  assert.equal(observe(gate, 'thumb_up', 510, 'new-2').trigger, null)
  assert.equal(observe(gate, 'thumb_up', 1010, 'new-3').trigger, 'thumb_up')
  gate.reset(); assert.equal(hold(gate, 'open_palm', 2000, 'reset')[2].trigger, 'open_palm')
})
test('missing frame keys, invalid timestamps and unknown labels cannot trigger', () => {
  const gate = new GestureGate()
  for (const time of [0, 500, 1000, 1500]) assert.equal(gate.update('open_palm', 0.9, time).trigger, null)
  assert.deepEqual(gate.update('open_palm', 0.9, NaN, 'x'), { trigger: null, progress: 0, label: null })
  assert.equal(observe(gate, 'constructor', 0, 'y').label, null)
})
test('interpretation uses model categories and corresponding landmarks', () => {
  const hand = [{ x: 0.2, y: 0.5, z: 0 }]
  assert.deepEqual(interpretGesture({ gestures: [[{ categoryName: 'Thumb_Up', score: 0.95 }]], landmarks: [hand] }), { label: 'thumb_up', score: 0.95, landmarks: hand })
  assert.equal(interpretGesture({ gestures: [[{ categoryName: 'None', score: 0.95 }, { categoryName: 'Open_Palm', score: 0.05 }]] }).label, null)
  assert.deepEqual(interpretGesture(undefined), { label: null, score: 0, landmarks: [] })
})
test('invalid options are rejected', () => {
  for (const options of [{ holdMs: 0 }, { minFrames: 0 }, { cooldownMs: -1 }, { scoreThreshold: 2 }, { maxGapMs: 0 }]) assert.throws(() => new GestureGate(options), RangeError)
})


test('a thumb held before the end rearms when confirmation becomes available', () => {
  const gate = new GestureGate({scoreThreshold:0.6})
  for (const [i,t] of [0,500,1000].entries()) assert.equal(gate.update(eligibleRestGesture('running','thumb_up'),0.9,t,`early-${i}`).trigger,null)
  const times=[1500,2000,2500]
  const results=times.map((t,i)=>gate.update(eligibleRestGesture('awaiting_confirmation','thumb_up'),0.9,t,`ready-${i}`))
  assert.equal(results[0].trigger,null);assert.equal(results[2].trigger,'thumb_up')
  assert.equal(eligibleRestGesture('paused','open_palm'),null)
  assert.equal(eligibleRestGesture(undefined,'thumb_up'),null)
})
test('the room confidence threshold still requires a stable distinct-frame hold', () => {
  const gate = new GestureGate({scoreThreshold:0.6})
  assert.equal(gate.update('open_palm',0.59,0,'low').label,null)
  const results=[100,600,1100].map((t,i)=>gate.update('open_palm',0.602,t,`palm-${i}`))
  assert.equal(results[1].trigger,null);assert.equal(results[2].trigger,'open_palm')
})
