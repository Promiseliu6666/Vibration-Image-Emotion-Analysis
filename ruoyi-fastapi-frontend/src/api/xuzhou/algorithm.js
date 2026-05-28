import request from '@/utils/request'

// 查询算法列表
export function listAlgorithm(query) {
  return request({
    url: '/xuzhou/algorithm/list',
    method: 'get',
    params: query
  })
}

// 新增算法
export function addAlgorithm(data) {
  return request({
    url: '/xuzhou/algorithm/',
    method: 'post',
    data: data
  })
}

// 修改算法
export function updateAlgorithm(data) {
  return request({
    url: '/xuzhou/algorithm/',
    method: 'put',
    data: data
  })
}

// 删除算法
export function delAlgorithm(algId) {
  return request({
    url: '/xuzhou/algorithm/' + algId,
    method: 'delete'
  })
}

// 获取统计信息
export function getStatistics() {
  return request({
    url: '/xuzhou/algorithm/statistics',
    method: 'get'
  })
}

// 上传算法权重
export function uploadAlgorithmWeight(data, onUploadProgress) {
  return request({
    url: '/xuzhou/algorithm/upload-weight',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress
  })
}

export function getCharts() {
  return request({
    url: '/xuzhou/algorithm/charts',
    method: 'get'
  })
}
