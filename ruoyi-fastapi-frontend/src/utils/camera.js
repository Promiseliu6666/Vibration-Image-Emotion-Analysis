export const CAMERA_STORAGE_KEY = 'health-camera-selection'

const CAMERA_SOURCES = new Set(['local', 'rtsp', 'xiaozhi'])
const DEVICE_ID_PATTERN = /^[A-Za-z0-9:_-]{1,64}$/

export function toCameraId(source = 'local', deviceId = '') {
  const normalizedSource = CAMERA_SOURCES.has(source) ? source : 'local'
  if (normalizedSource !== 'xiaozhi') return normalizedSource

  const normalizedDeviceId = String(deviceId || '').trim()
  return DEVICE_ID_PATTERN.test(normalizedDeviceId)
    ? `xiaozhi:${normalizedDeviceId}`
    : 'xiaozhi'
}

export function parseCameraId(cameraId = 'local') {
  const value = String(cameraId || 'local').trim()
  if (value === 'local:0') return { source: 'local', deviceId: '' }
  if (value === 'rtsp:default') return { source: 'rtsp', deviceId: '' }
  if (value.startsWith('xiaozhi:')) {
    const deviceId = value.slice('xiaozhi:'.length)
    if (DEVICE_ID_PATTERN.test(deviceId)) {
      return { source: 'xiaozhi', deviceId }
    }
    return { source: 'xiaozhi', deviceId: '' }
  }
  if (value === 'xiaozhi') return { source: 'xiaozhi', deviceId: '' }
  if (value === 'rtsp') return { source: 'rtsp', deviceId: '' }
  return { source: 'local', deviceId: '' }
}

export function cameraQueryString(cameraId = 'local') {
  const { source, deviceId } = parseCameraId(cameraId)
  return new URLSearchParams({
    camera_id: toCameraId(source, deviceId)
  }).toString()
}

export function toXiaozhiDeviceId(cameraId = 'local') {
  const { source, deviceId } = parseCameraId(cameraId)
  if (source === 'local') return 'vibration-local'
  if (source === 'rtsp') return 'vibration-rtsp'
  return deviceId
}
