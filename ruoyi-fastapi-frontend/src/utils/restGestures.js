/** Local MediaPipe gesture recognition and frame-aware confirmation for rest activities. */
const LABELS = Object.freeze({ Open_Palm: 'open_palm', Thumb_Up: 'thumb_up', open_palm: 'open_palm', thumb_up: 'thumb_up' })
const normalizedLabel = (label) => typeof label === 'string' && Object.prototype.hasOwnProperty.call(LABELS, label) ? LABELS[label] : null
const confidence = (value) => Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0

/** Call close() on the returned recognizer when leaving the page. No image is uploaded. */
export async function createRestRecognizer() {
  try {
    const { FilesetResolver, GestureRecognizer } = await import('@mediapipe/tasks-vision')
    const fileset = await FilesetResolver.forVisionTasks('/gesture-assets/wasm')
    return await GestureRecognizer.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: '/gesture-assets/gesture_recognizer.task', delegate: 'CPU' },
      runningMode: 'VIDEO', numHands: 1,
      minHandDetectionConfidence: 0.5, minHandPresenceConfidence: 0.5, minTrackingConfidence: 0.5
    })
  } catch (error) {
    throw new Error('手势识别资源加载失败，请检查本地模型文件，或使用按钮继续。', { cause: error })
  }
}

/** A lower-ranked Open_Palm must not override a stronger model category of None. */
export function interpretGesture(result) {
  let best = null
  let handIndex = 0
  const hands = Array.isArray(result?.gestures) ? result.gestures : []
  hands.forEach((categories, index) => {
    if (!Array.isArray(categories)) return
    categories.forEach((category) => {
      if (!category || !Number.isFinite(category.score)) return
      if (!best || category.score > best.score) { best = category; handIndex = index }
    })
  })
  return {
    label: normalizedLabel(best?.categoryName), score: confidence(best?.score),
    landmarks: Array.isArray(result?.landmarks?.[handIndex]) ? result.landmarks[handIndex] : []
  }
}

/**
 * now: monotonic milliseconds; frameKey: source plus frame identity (string/number).
 * Only distinct frames advance a hold. A fired gesture must be released/changed
 * before rearming, including after the global cooldown has elapsed.
 */
export class GestureGate {
  constructor({ holdMs = 1000, minFrames = 3, cooldownMs = 2500, scoreThreshold = 0.65, maxGapMs = 2000 } = {}) {
    if (!Number.isFinite(holdMs) || holdMs <= 0) throw new RangeError('holdMs must be positive')
    if (!Number.isInteger(minFrames) || minFrames < 1) throw new RangeError('minFrames must be a positive integer')
    if (!Number.isFinite(cooldownMs) || cooldownMs < 0) throw new RangeError('cooldownMs must be nonnegative')
    if (!Number.isFinite(scoreThreshold) || scoreThreshold < 0 || scoreThreshold > 1) throw new RangeError('scoreThreshold must be between 0 and 1')
    if (!Number.isFinite(maxGapMs) || maxGapMs <= 0) throw new RangeError('maxGapMs must be positive')
    this.holdMs = holdMs; this.minFrames = minFrames; this.cooldownMs = cooldownMs
    this.scoreThreshold = scoreThreshold; this.maxGapMs = maxGapMs
    this.reset()
  }
  reset() {
    this.lastNow = null; this.lastFreshAt = null; this.cooldownUntil = -Infinity
    this.latchedLabel = null; this.lastLabel = null
    this.seenFrames = new Set(); this.frameOrder = []
    this._clearCandidate()
  }
  _clearCandidate() { this.candidateLabel = null; this.startedAt = null; this.frameCount = 0; this.progress = 0 }
  _snapshot(trigger = null) { return { trigger, progress: this.progress, label: this.lastLabel } }
  update(label, score, now, frameKey) {
    if (!Number.isFinite(now)) { this.reset(); return this._snapshot() }
    if (this.lastNow !== null && now < this.lastNow) this.reset()
    this.lastNow = now
    if (this.lastFreshAt !== null && now - this.lastFreshAt > this.maxGapMs) this._clearCandidate()
    const validKey = (typeof frameKey === 'string' && frameKey.length > 0) || (typeof frameKey === 'number' && Number.isFinite(frameKey))
    if (!validKey) { this._clearCandidate(); this.lastLabel = null; return this._snapshot() }
    if (this.seenFrames.has(frameKey)) return this._snapshot()
    this.seenFrames.add(frameKey); this.frameOrder.push(frameKey)
    if (this.frameOrder.length > 128) this.seenFrames.delete(this.frameOrder.shift())
    this.lastFreshAt = now
    const candidate = normalizedLabel(label)
    this.lastLabel = candidate && confidence(score) >= this.scoreThreshold ? candidate : null
    if (!this.lastLabel) { this.latchedLabel = null; this._clearCandidate(); return this._snapshot() }
    if (this.latchedLabel && this.lastLabel !== this.latchedLabel) this.latchedLabel = null
    if (now < this.cooldownUntil || this.latchedLabel === this.lastLabel) { this._clearCandidate(); return this._snapshot() }
    if (this.candidateLabel !== this.lastLabel) { this._clearCandidate(); this.candidateLabel = this.lastLabel; this.startedAt = now }
    this.frameCount += 1
    this.progress = Math.min(1, (now - this.startedAt) / this.holdMs, this.frameCount / this.minFrames)
    if (this.progress < 1) return this._snapshot()
    const trigger = this.lastLabel
    this.latchedLabel = trigger; this.cooldownUntil = now + this.cooldownMs
    this._clearCandidate(); this.progress = 1
    return this._snapshot(trigger)
  }
}

/** Only executable gestures enter the stability gate; early thumbs cannot latch. */
export function eligibleRestGesture(phase, label) {
  if (!phase) return label === 'open_palm' ? label : null
  return phase === 'awaiting_confirmation' && label === 'thumb_up' ? label : null
}
