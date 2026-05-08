import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import Cookies from 'js-cookie'

const API_BASE = import.meta.env.VITE_APP_BASE_API || ''

const getToken = () =>
  Cookies.get('Admin-Token') ||
  localStorage.getItem('Admin-Token') ||
  localStorage.getItem('token') ||
  localStorage.getItem('access_token') ||
  ''

export async function chatWithAgentStream({
  conversation_id,
  message = '',
  image = null,
  audio = null,
  user_id = 'user_001',
  model = 'qwen3-omni-flash'
}) {
  const token = getToken()
  if (!token) {
    ElMessage.error('请先登录系统')
    throw new Error('Token is empty')
  }

  const formData = new FormData()
  formData.append('conversation_id', conversation_id)
  formData.append('user_id', user_id)
  formData.append('message', message)
  formData.append('model', model)
  if (image) formData.append('image', image)
  if (audio) formData.append('audio', audio)

  const response = await fetch(`${API_BASE}/agent/chat`, {
    method: 'POST',
    body: formData,
    credentials: 'include',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'text/event-stream'
    },
    cache: 'no-cache'
  })

  if (!response.ok) {
    if (response.status === 401) ElMessage.error('登录已过期，请重新登录')
    throw new Error(`请求失败: ${response.status}`)
  }
  if (!response.body) {
    throw new Error('服务端未返回流式响应体')
  }
  return response
}

export function chatWithAgent(data) {
  return request({ url: '/agent/chat', method: 'post', data, timeout: 300000 })
}

export function getAgentHistory(conversationId, limit = 100) {
  return request({
    url: `/agent/history/${conversationId}`,
    method: 'get',
    params: { limit }
  })
}

export function getAgentConversations(params = {}) {
  return request({
    url: '/agent/conversations',
    method: 'get',
    params
  })
}

export function deleteAgentConversation(conversationId) {
  return request({ url: `/agent/conversation/${conversationId}`, method: 'delete' })
}

export default {
  chatWithAgentStream,
  chatWithAgent,
  getAgentHistory,
  getAgentConversations,
  deleteAgentConversation
}
