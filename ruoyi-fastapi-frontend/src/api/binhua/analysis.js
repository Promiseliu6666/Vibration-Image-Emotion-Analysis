import request from '@/utils/request'

export function listAnalysis(params) {
  // 手动映射为后端期望的 snake_case 参数名（解决搜索过滤不生效）
  const mappedParams = {
    page_num: params.pageNum,
    page_size: params.pageSize,
    person_id: params.personId ?? undefined,
    source: params.source ?? undefined,
  }

  // 清理 undefined/null/空字符串（避免传无效参数）
  Object.keys(mappedParams).forEach(key => {
    if (mappedParams[key] === undefined || mappedParams[key] === null || mappedParams[key] === '') {
      delete mappedParams[key]
    }
  })

  return request({
    url: '/analysis/list',
    method: 'get',
    params: mappedParams
  })
}

export function getAnalysisHistory(personId) {
  return request({
    url: `/analysis/person/${personId}`,
    method: 'get'
  })
}

export function getAnalysis(id) {
  return request({
    url: `/analysis/${id}`,
    method: 'get'
  })
}

export function addAnalysis(data) {
  return request({
    url: '/analysis/',
    method: 'post',
    data
  })
}

export function updateAnalysis(id, data) {
  return request({
    url: `/analysis/${id}`,
    method: 'put',
    data
  })
}

export function delAnalysis(id) {
  return request({
    url: `/analysis/${id}`,
    method: 'delete'
  })
}

export function batchDelAnalysis(data) {
  return request({
    url: '/analysis/batch-delete',
    method: 'post',
    data
  })
}