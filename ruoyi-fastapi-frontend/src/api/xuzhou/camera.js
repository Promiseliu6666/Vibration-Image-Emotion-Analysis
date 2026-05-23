import request from '@/utils/request'

// 获取摄像头列表（含运行状态）
export function listCameras() {
  return request({
    url: '/xuzhou/command/camera_list',
    method: 'get'
  })
}

// 推送视频配置（启动推理）
export function startCamera(vidId) {
  return request({
    url: '/xuzhou/command/push_video_config',
    method: 'post',
    data: { vid_id: vidId }
  })
}

// 停止推理
export function stopCamera(vidId) {
  return request({
    url: '/xuzhou/command/push_video_config',
    method: 'post',
    data: { vid_id: vidId, action: 'stop' }
  })
}

// 获取设备状态
export function getDeviceStatus(vidId) {
  return request({
    url: '/xuzhou/command/device_status',
    method: 'get',
    params: { vid_id: vidId }
  })
}

// 获取在线盒子列表
export function listBoxes() {
  return request({
    url: '/xuzhou/command/boxes',
    method: 'get'
  })
}

// 获取盒子本地摄像头 MJPEG 实时流地址
export function getCameraStreamUrl(vidId) {
  return request({
    url: `/xuzhou/command/camera_stream_url/${vidId}`,
    method: 'get'
  })
}

// 获取盒子本地摄像头快照
export function getCameraSnapshot(vidId) {
  return request({
    url: `/xuzhou/command/camera_snapshot/${vidId}`,
    method: 'get',
    params: { t: Date.now() },
    responseType: 'blob'
  })
}

// ==================== 本地服务器摄像头（无盒子） ====================

// 启动本地服务器摄像头采集
export function startLocalCamera(vidId) {
  return request({
    url: `/xuzhou/command/local_camera/start/${vidId}`,
    method: 'get'
  })
}

// 停止本地服务器摄像头采集
export function stopLocalCamera(vidId) {
  return request({
    url: `/xuzhou/command/local_camera/stop/${vidId}`,
    method: 'get'
  })
}

// 获取本地服务器摄像头 MJPEG 实时流地址
export function getLocalCameraStreamUrl(vidId) {
  return request({
    url: `/xuzhou/command/local_camera/stream_url/${vidId}`,
    method: 'get'
  })
}

// 获取本地服务器摄像头快照
export function getLocalCameraSnapshot(vidId) {
  return request({
    url: `/xuzhou/command/local_camera/snapshot/${vidId}`,
    method: 'get',
    params: { t: Date.now() },
    responseType: 'blob'
  })
}
