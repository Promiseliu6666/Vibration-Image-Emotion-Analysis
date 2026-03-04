import request from '@/utils/request'

// 查询系统对接日志列表
export function list(query) {
  return request({
    url: '/monitor/integration/list',
    method: 'get',
    params: query
  })
}

// 删除系统对接日志
export function delIntegrationLog(logIds) {
  return request({
    url: '/monitor/integration/' + logIds,
    method: 'delete'
  })
}

// 清空系统对接日志
export function cleanIntegrationLog() {
  return request({
    url: '/monitor/integration/clean',
    method: 'delete'
  })
}

// 导出系统对接日志
export function exportIntegrationLog(query) {
  return request({
    url: '/monitor/integration/export',
    method: 'post',
    data: query
  })
}