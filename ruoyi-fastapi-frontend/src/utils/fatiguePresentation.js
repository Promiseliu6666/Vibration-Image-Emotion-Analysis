const finite = value => (typeof value !== 'number' && typeof value !== 'string') || (typeof value === 'string' && !value.trim())
  ? null : Number.isFinite(Number(value)) ? Number(value) : null
const clamp = value => Math.max(0, Math.min(1, value))

export function fatiguePresentation(result = {}, error = '') {
  const direct = finite(result.fatigue_score)
  const wakefulness = finite(result.score_ema)
  const score = direct !== null ? clamp(direct) : wakefulness !== null ? 1 - clamp(wakefulness) : null
  const pending = /warmup|prepar|calibrat|预热|准备|校准/i.test(`${result.status || ''} ${result.fatigue_status || ''}`)
  const failed = Boolean(error) || /error|failed|错误|失败/i.test(String(result.status || ''))
  const ready = !failed && !pending && score !== null && result.face_detected !== false
    && (result.warmup_progress == null || (finite(result.warmup_progress) ?? 0) >= (finite(result.warmup_target) ?? 720))
    && (result.feature_buffer == null || (finite(result.feature_buffer) ?? 0) >= (finite(result.feature_target) ?? 30))
  const tone = failed ? 'error' : !ready ? 'pending' : score > 0.70 ? 'fatigued' : score >= 0.45 ? 'drowsy' : 'alert'
  const title = ready ? { alert: '清醒', drowsy: '轻度疲劳', fatigued: '明显疲劳' }[tone] : failed ? '数据暂不可用' : '暂未出分'
  const hint = ready ? { alert: '当前疲劳程度较低。', drowsy: '建议适当休息，关注状态变化。', fatigued: '建议及时休息，减少持续作业。' }[tone] : '结果生成后将显示疲劳等级。'
  const features = result.last_step?.features || {}
  const metrics = [
    ['perclos', '闭眼时间占比'],
    ['mouth_open_ratio', '张口时间占比'],
    ['mean_p_eye', '平均闭眼程度'],
    ['mean_p_mouth', '平均张口程度'],
    ['kpt_visibility', '姿态信号完整度']
  ].map(([key, label]) => {
    const raw = !failed && result.face_detected === true && result.last_step?.valid !== false ? finite(features[key]) : null
    const value = raw === null ? null : Math.round(clamp(raw) * 1000) / 10
    return { key, label, value, text: value === null ? '—' : `${value.toFixed(1)}%` }
  })
  return { ready, tone, title, hint, metrics, value: ready ? Math.round(score * 1000) / 10 : null, blink: finite(result.blink_total), yawn: finite(result.yawn_total) }
}
