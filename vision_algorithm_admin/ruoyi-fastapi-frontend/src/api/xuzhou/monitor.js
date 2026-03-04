import request from '@/utils/request'

// 查询部门列表
export function commandRunningClients() {
  return request({
    url: '/xuzhou/command/running/clients',
    method: 'get'
  })
}

// 根据key获取缓存消息
export function getCacheMessages(key) {
  return request({
    url: `/xuzhou/command/cache_messages/${key}`,
    method: 'get'
  })
}