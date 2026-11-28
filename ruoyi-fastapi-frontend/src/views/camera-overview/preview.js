import { cameraQueryString, parseCameraId, toCameraId } from '@/utils/camera'

export function cameraPreviewUrl(camera, baseURL = '/dev-api', revision = 0, feed = 'raw') {
  if (!camera?.camera_id || camera.configured === false) return ''
  const { source, deviceId } = parseCameraId(camera.camera_id)
  if (toCameraId(source, deviceId) !== camera.camera_id || (source === 'xiaozhi' && !deviceId)) return ''
  const path = feed === 'fatigue' ? '/fatigue/feed' : `/video/feed/${feed === 'analysis' ? 'analysis' : 'raw'}`
  const overlay = feed === 'fatigue' ? '&show_boxes=1' : ''
  return `${baseURL.replace(/\/+$/, '')}${path}?${cameraQueryString(camera.camera_id)}${overlay}&preview=${encodeURIComponent(revision)}`
}
