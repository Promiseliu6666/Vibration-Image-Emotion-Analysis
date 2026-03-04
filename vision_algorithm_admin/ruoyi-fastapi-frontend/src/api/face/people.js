import request from '@/utils/request'

// 查询人员列表（不分组）
export function listPeople(query) {
  return request({
    url: '/people/list',
    method: 'get',
    params: query
  })
}

// 查看成员列表（组内）
export function listGroupMembers(groupId, query) {
  return request({
    url: `/group/${groupId}/members`,
    method: 'get',
    params: query
  })
}

// 获取成员信息
export function getPeople(groupId, memberId) {
  return request({
    url: `/group/${groupId}/members/${memberId}`,
    method: 'get'
  })
}

// 添加成员
export function addPeople(data) {
  return request({
    url: '/people/',
    method: 'post',
    data: data
  })
}

// 编辑成员信息
export function updatePeople(peopleId, data) {
  return request({
    url: `/people/${peopleId}`,
    method: 'put',
    data: data
  })
}

// 删除人员
export function delPeople(peopleId) {
  return request({
    url: `/people/${peopleId}`,
    method: 'delete'
  })
}

// 人脸比对
export function faceCompare(data) {
  return request({
    url: '/people/face-compare',
    method: 'post',
    data: data
  })
}