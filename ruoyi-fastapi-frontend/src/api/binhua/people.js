// people.js
import request from '@/utils/request'

// 查询人员列表
export function listPeople(query) {
  return request({
    url: '/people/list',
    method: 'get',
    params: query
  })
}

// 新增人员
export function addPeople(data) {
  return request({
    url: '/people/',
    method: 'post',
    data
  })
}

// 修改人员
export function updatePeople(id, data) {
  return request({
    url: `/people/${id}`,
    method: 'put',
    data
  })
}

// 删除人员
export function delPeople(id) {
  return request({
    url: `/people/${id}`,
    method: 'delete'
  })
}

// 人脸比对
export function faceCompare(data) {
  return request({
    url: '/people/face-compare',
    method: 'post',
    data
  })
}

export function faceCompareAll(data) {
  return request({
    url: '/people/face-compare-all',
    method: 'post',
    data
  })
}

// ==================== 批量导入（Excel + ZIP） ====================
export function batchImportPeople(data) {
  return request({
    url: '/people/import',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}