import request from '@/utils/request'

// 查询回调列表
export function listCallback(query) {
  return request({
    url: '/tool/callback/list',
    method: 'get',
    params: query
  })
}

// 查询回调详细
export function getCallback(callbackId) {
  return request({
    url: '/tool/callback/' + callbackId,
    method: 'get'
  })
}

// 新增回调
export function addCallback(data) {
  return request({
    url: '/tool/callback',
    method: 'post',
    data: data
  })
}

// 修改回调
export function updateCallback(data) {
  return request({
    url: '/tool/callback',
    method: 'put',
    data: data
  })
}

// 删除回调
export function delCallback(callbackId) {
  return request({
    url: '/tool/callback/' + callbackId,
    method: 'delete'
  })
}
