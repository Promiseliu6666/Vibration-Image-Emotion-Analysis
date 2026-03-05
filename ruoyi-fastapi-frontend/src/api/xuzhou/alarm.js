import request from '@/utils/request'

// 获取预警消息列表
export function getAlarmList(query) {
  return request({
    url: '/xuzhou/alarm/list',
    method: 'get',
    params: query
  })
}
