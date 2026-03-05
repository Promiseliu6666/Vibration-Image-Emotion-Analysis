import request from '@/utils/request'

export function listPeople(params) {
  return request({
    url: '/people/list',  // 保持原样（已有 / 开头）
    method: 'get',
    params
  })
}

export function addPeople(data) {
  return request({
    url: '/people/',       // 保持原样
    method: 'post',
    data
  })
}

export function updatePeople(id, data) {
  return request({
    url: `/people/${id}`,  // 保持原样
    method: 'put',
    data
  })
}

export function delPeople(id) {
  return request({
    url: `/people/${id}`,  // 保持原样
    method: 'delete'
  })
}

export function faceCompare(data) {
  return request({
    url: '/people/face-compare',  // 保持原样
    method: 'post',
    data
  })
}

export function faceCompareAll(data) {
  return request({
    url: '/people/face-compare-all',  // 保持原样
    method: 'post',
    data
  })
}