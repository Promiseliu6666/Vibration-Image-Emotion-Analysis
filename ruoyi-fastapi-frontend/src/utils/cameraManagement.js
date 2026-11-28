export const cameraSourceLabels = { local: '本机摄像头', rtsp: '网络摄像头', xiaozhi: '小智摄像头' }

export function cameraAnalysis(camera) {
  const config = camera?.analysis || {}
  const ids = Array.isArray(config.algorithm_ids) && config.algorithm_ids.length
    ? config.algorithm_ids : [config.algorithm_id || 'vibration']
  return { scene: config.scene || '心理状态观察', algorithm_ids: [...new Set(ids)], show_overlay: Boolean(config.show_overlay) }
}

export function cameraConnectionState(camera) {
  if (camera?.configured === false) return { label: '待配置连接', type: 'warning', detail: '请先配置摄像头连接地址' }
  if (camera?.online === true) return { label: '有画面', type: 'success', detail: '最近已收到设备画面' }
  if (camera?.online === false) return { label: '暂无画面', type: 'warning', detail: '检查设备连接和采集状态' }
  return { label: '待验证画面', type: 'info', detail: '进入实时监测后验证画面连接' }
}

export function validateCameraAnalysis(config) {
  if (!config.algorithm_ids?.length) return '请至少选择一种分析算法'
  if (!config.scene?.trim() || config.scene.trim().length > 80) return '应用场景须为 1–80 个字符'
  return ''
}

export function sameCameraAnalysis(left, right) {
  return left.scene.trim() === right.scene.trim() && left.show_overlay === right.show_overlay
    && [...left.algorithm_ids].sort().join(',') === [...right.algorithm_ids].sort().join(',')
}

export function filterCameras(cameras, { search = '', source = '', algorithm = '' } = {}) {
  const query = search.trim().toLowerCase()
  return cameras.filter(camera => {
    const analysis = cameraAnalysis(camera)
    return (!source || camera.source === source) && (!algorithm || analysis.algorithm_ids.includes(algorithm))
      && `${camera.name} ${camera.camera_id} ${analysis.scene}`.toLowerCase().includes(query)
  })
}
