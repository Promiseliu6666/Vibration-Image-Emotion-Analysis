import axios from 'axios'
import { getToken } from '@/utils/auth'
const client = axios.create({ baseURL: import.meta.env.VITE_APP_BASE_API, timeout: 12000 })
client.interceptors.request.use(config => { const token = getToken(); if (token) config.headers.Authorization = `Bearer ${token}`; return config })
async function call(config) {
  try {
    const response = await client(config)
    if (config.responseType === 'blob') {
      if (!response.headers['content-type']?.startsWith('image/jpeg')) { const data = JSON.parse(await response.data.text()); throw new Error(data.msg || '登录已失效，请重新登录') }
      return response
    }
    const payload = response.data
    if (payload.code && payload.code !== 200) throw new Error(payload.msg || '请求未完成')
    return payload.data ?? payload
  } catch (error) {
    let detail = error.response?.data
    if (detail instanceof Blob) { try { detail = JSON.parse(await detail.text()) } catch { detail = null } }
    const message = typeof detail?.detail === 'string' ? detail.detail : detail?.msg
    throw new Error(message || (error.response?.status === 401 ? '登录已失效，请重新登录' : error.code === 'ECONNABORTED' ? '服务响应超时，请稍后重试' : error.message === 'Network Error' ? '休息室服务未连接，请启动后台服务' : error.message || '请求未完成'))
  }
}
export const restCatalog = () => call({ url: '/interaction/rest/catalog' })
export const restState = () => call({ url: '/interaction/rest/state' })
export const startRest = data => call({ url: '/interaction/rest/sessions', method: 'post', data })
export const restAction = (id, data) => call({ url: `/interaction/rest/sessions/${encodeURIComponent(id)}/action`, method: 'post', data })
export const restDevices = () => call({ url: '/video/xiaozhi/devices' })
export async function restFrame(source, signal) { const r = await call({ url: '/interaction/rest/frame', params: { source }, responseType: 'blob', signal, timeout: 9000 }); return { blob: r.data, sequence: r.headers['x-frame-sequence'], capturedAt: Number(r.headers['x-frame-captured-at'] || 0) } }
