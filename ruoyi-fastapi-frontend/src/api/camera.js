import request from '@/utils/request'

export function listAnalysisAlgorithms() {
  return request({ url: '/video/algorithms', method: 'get', silent: true })
}

export function getFatigueServiceStatus() {
  return request({ url: '/fatigue/status', method: 'get', timeout: 5000, silent: true })
}

export function saveCameraAnalysis(cameraId, analysis) {
  return request({
    url: `/video/cameras/${encodeURIComponent(cameraId)}/analysis`,
    method: 'put', data: analysis
  })
}

export function listCameras(options = {}) {
  return request({
    url: '/video/cameras',
    method: 'get',
    timeout: 20000,
    silent: options.silent === true
  })
}

export function listXiaozhiCameras() {
  return request({
    url: '/video/xiaozhi/devices',
    method: 'get',
    timeout: 20000
  })
}
