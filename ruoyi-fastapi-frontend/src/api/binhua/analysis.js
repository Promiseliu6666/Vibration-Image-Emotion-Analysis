// analysis.js
import request from '@/utils/request'

// 查询分析记录列表（分页）
export function listAnalysis(query) {
  return request({
    url: '/analysis/list',
    method: 'get',
    params: query
  })
}

// 查询某人员的分析历史记录
export function getAnalysisHistory(personId) {
  return request({
    url: `/analysis/person/${personId}`,
    method: 'get'
  })
}

// 查询单条分析记录详情
export function getAnalysis(id) {
  return request({
    url: `/analysis/${id}`,
    method: 'get'
  })
}

// 新增分析记录
export function addAnalysis(data) {
  return request({
    url: '/analysis/',
    method: 'post',
    data
  })
}

// 修改分析记录
export function updateAnalysis(id, data) {
  return request({
    url: `/analysis/${id}`,
    method: 'put',
    data
  })
}

// 删除单条分析记录
export function delAnalysis(id) {
  return request({
    url: `/analysis/${id}`,
    method: 'delete'
  })
}

// 批量删除分析记录
export function batchDelAnalysis(data) {
  return request({
    url: '/analysis/batch-delete',
    method: 'post',
    data
  })
}