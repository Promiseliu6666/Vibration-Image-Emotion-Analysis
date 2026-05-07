// analysis.js
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import Cookies from 'js-cookie'

// ====================== Token 获取函数 ======================
const getToken = () => {
  return (
    Cookies.get('Admin-Token') ||
    localStorage.getItem('Admin-Token') ||
    localStorage.getItem('token') ||
    localStorage.getItem('access_token') ||
    ''
  )
}

// 查询分析记录列表（分页）
export function listAnalysis(query) {
  return request({
    url: '/analysis/list',
    method: 'get',
    params: query
  })
}

// 查询某人员的分析历史记录
export function getAnalysisHistory(personId) {
  return request({
    url: `/analysis/person/${personId}`,
    method: 'get'
  })
}

// 查询单条分析记录详情
export function getAnalysis(id) {
  return request({
    url: `/analysis/${id}`,
    method: 'get'
  })
}

// 新增分析记录
export function addAnalysis(data) {
  return request({
    url: '/analysis/',
    method: 'post',
    data
  })
}

// 修改分析记录
export function updateAnalysis(id, data) {
  return request({
    url: `/analysis/${id}`,
    method: 'put',
    data
  })
}

// 删除单条分析记录
export function delAnalysis(id) {
  return request({
    url: `/analysis/${id}`,
    method: 'delete'
  })
}

// 批量删除分析记录
export function batchDelAnalysis(data) {
  return request({
    url: '/analysis/batch-delete',
    method: 'post',
    data
  })
}

// 导出分析记录
export function exportAnalysis(query) {
  const form = new URLSearchParams()
  Object.entries(query).forEach(([k, v]) => {
    if (v != null && v !== '') form.append(k, v)
  })

  return request({
    url: '/analysis/export',
    method: 'post',
    data: form,
    responseType: 'blob'
  })
}
// 获取所有人名列表（用于下拉框）
export function getPersonNames() {
  return request({
    url: '/analysis/person-names',
    method: 'get'
  })
}
// 导出个人心理分析报告 PDF（已修复超时：60秒超时）
export function exportPersonReport(data) {
  return request({
    url: '/analysis/export-person-report',
    method: 'post',
    responseType: 'blob',
    timeout: 60000,  // 👈 这里加了 60 秒超时
    data
  })
}
// ====================== 视频播放相关（支持 Token 校验） ======================

/**
 * 获取视频播放 Blob URL（用于 <video> 标签）
 */
export async function getVideoBlobUrl(analysisId) {
  const token = getToken()
  if (!token) {
    ElMessage.error('Token 不存在，请重新登录')
    throw new Error('Token is empty')
  }

  const response = await fetch(`/dev-api/analysis/video/${analysisId}`, {
    method: 'GET',
    credentials: 'include',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'video/mp4, video/*, */*'
    },
    cache: 'no-cache'
  })

  if (!response.ok) {
    if (response.status === 401) {
      ElMessage.error('登录已过期，请重新登录')
    } else if (response.status === 404) {
      ElMessage.error('视频文件不存在')
    } else {
      ElMessage.error(`视频请求失败: ${response.status}`)
    }
    throw new Error(`请求失败: ${response.status}`)
  }

  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

/**
 * 下载视频（带 Token，手动触发下载）
 */
export async function downloadVideo(analysisId, fileName = '分析视频.mp4') {
  const token = getToken()
  if (!token) {
    ElMessage.error('Token 不存在，请重新登录')
    return
  }

  try {
    const response = await fetch(`/dev-api/analysis/video/${analysisId}`, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'video/mp4, video/*, */*'
      }
    })

    if (!response.ok) {
      throw new Error(`下载失败: ${response.status}`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)

    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    ElMessage.success('下载已开始')
  } catch (err) {
    console.error('下载失败', err)
    ElMessage.error('下载失败，请检查登录状态')
  }
}

export default {
  listAnalysis,
  getAnalysisHistory,
  getAnalysis,
  addAnalysis,
  updateAnalysis,
  delAnalysis,
  batchDelAnalysis,
  exportAnalysis,
  getVideoBlobUrl,
  downloadVideo
}