import request from '@/utils/request'

export function listCameras() {
  return request({
    url: '/video/cameras',
    method: 'get',
    timeout: 20000
  })
}

export function listXiaozhiCameras() {
  return request({
    url: '/video/xiaozhi/devices',
    method: 'get',
    timeout: 20000
  })
}
