import request from '@/utils/request'

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
