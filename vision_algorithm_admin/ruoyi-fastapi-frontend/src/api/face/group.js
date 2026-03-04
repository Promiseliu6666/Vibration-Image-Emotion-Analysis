import request from '@/utils/request'

// 查询分组列表
export function listGroup(query) {
  return request({
    url: '/group/list',
    method: 'get',
    params: query
  })
}

// 查询分组详细
export function getGroup(groupId) {
  return request({
    url: '/group/' + groupId,
    method: 'get'
  })
}

// 新增分组
export function addGroup(data) {
  return request({
    url: '/group/',
    method: 'post',
    data: data
  })
}

// 修改分组
export function updateGroup(data) {
  return request({
    url: '/group/' + data.id,
    method: 'put',
    data: data
  })
}

// 删除分组
export function delGroup(groupId) {
  return request({
    url: '/group/' + groupId,
    method: 'delete'
  })
}