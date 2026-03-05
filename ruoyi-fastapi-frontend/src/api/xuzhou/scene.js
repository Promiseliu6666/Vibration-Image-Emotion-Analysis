import request from '@/utils/request'

// 查询场景列表
export function listScene(query) {
  return request({
    url: '/xuzhou/scene/list',
    method: 'get',
    params: query
  })
}

// 新增场景
export function addScene(data) {
  return request({
    url: '/xuzhou/scene',
    method: 'post',
    data: data
  })
}

// 修改场景
export function updateScene(data) {
  return request({
    url: '/xuzhou/scene',
    method: 'put',
    data: data
  })
}

// 删除场景
export function delScene(sceneId) {
  return request({
    url: '/xuzhou/scene/' + sceneId,
    method: 'delete'
  })
}

// 获取场景详细信息
export function getScene(sceneId) {
  return request({
    url: '/xuzhou/scene/' + sceneId,
    method: 'get'
  })
}
