import request from '@/utils/request'
import { getToken } from '@/utils/auth'

export function captureAnalyzeClip(data) {
  return request({
    url: '/xuzhou/clip-analysis/capture-analyze',
    method: 'post',
    data,
    timeout: 180000,
    headers: {
      repeatSubmit: false
    }
  })
}

export function captureClipOnly(data) {
  return request({
    url: '/xuzhou/clip-analysis/capture-only',
    method: 'post',
    data,
    timeout: 180000,
    headers: {
      repeatSubmit: false
    }
  })
}

export function analyzeCapturedClip(data) {
  return request({
    url: '/xuzhou/clip-analysis/analyze-captured',
    method: 'post',
    data,
    timeout: 180000,
    headers: {
      repeatSubmit: false
    }
  })
}

export function startLocalCameraRecording(data) {
  return request({
    url: '/xuzhou/clip-analysis/recording/local/start',
    method: 'post',
    data,
    headers: {
      repeatSubmit: false
    }
  })
}

export function stopLocalCameraRecording(data) {
  return request({
    url: '/xuzhou/clip-analysis/recording/local/stop',
    method: 'post',
    data,
    timeout: 30000,
    headers: {
      repeatSubmit: false
    }
  })
}

export function getLocalCameraRecordingStatus(sessionId) {
  return request({
    url: `/xuzhou/clip-analysis/recording/local/${sessionId}`,
    method: 'get'
  })
}

export function getClipAnalysisTaskStatus(taskId) {
  return request({
    url: `/xuzhou/clip-analysis/analysis-task/${taskId}`,
    method: 'get'
  })
}

export function listClipVideos(query) {
  return request({
    url: '/xuzhou/clip-analysis/videos',
    method: 'get',
    params: query
  })
}

export function analyzeClipVideoFile(data) {
  return request({
    url: '/analysis/v2/analyze-file',
    method: 'post',
    data,
    timeout: 180000,
    headers: {
      repeatSubmit: false
    }
  })
}

export function resetBackendLocalCamera(params) {
  return request({
    url: '/xuzhou/clip-analysis/reset-local',
    method: 'get',
    params
  })
}

export function analyzeByPath(data) {
  return request({
    url: '/analysis/v2/analyze-path',
    method: 'post',
    data,
    timeout: 180000,
    headers: {
      repeatSubmit: false
    }
  })
}

export async function getAnalysisVideoBlobUrl(analysisId) {
  const response = await fetch(`/dev-api/analysis/video/${analysisId}`, {
    method: 'GET',
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${getToken() || ''}`,
      Accept: 'video/mp4, video/*, */*'
    },
    cache: 'no-cache'
  })

  if (!response.ok) {
    throw new Error(`视频加载失败: ${response.status}`)
  }

  const blob = await response.blob()
  return URL.createObjectURL(blob)
}
