import request from '@/utils/request'

export function listAnalysisAlgorithms() {
  return request({ url: '/video/algorithms', method: 'get' })
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
