import request from '@/utils/request'

// 查询视频列表
export function listVideo(query) {
  return request({
    url: '/xuzhou/video/list',
    method: 'get',
    params: query
  })
}

// 新增视频
export function addVideo(data) {
  return request({
    url: '/xuzhou/video/',
    method: 'post',
    data: data
  })
}

// 修改视频
export function updateVideo(data) {
  return request({
    url: '/xuzhou/video/',
    method: 'put',
    data: data
  })
}

// 删除视频
export function delVideo(vidId) {
  return request({
    url: '/xuzhou/video/',
    method: 'delete',
    data: { vidIds: vidId.toString() }
  })
}

// 获取视频详细信息
export function getVideo(vidId) {
  return request({
    url: `/xuzhou/video/${vidId}`,
    method: 'get'
  })
}

// 启动视频推流
export function startVideoStream(data) {
  return request({
    url: '/xuzhou/video/stream',
    method: 'post',
    data: data
  })
}

// 推送视频配置
export function pushVideoConfig(vidId) {
  return request({
    url: '/xuzhou/command/push_video_config',
    method: 'post',
    data: { vid_id: vidId }
  })
}
