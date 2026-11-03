import { defineStore } from 'pinia'
import { listCameras } from '@/api/camera'
import {
  CAMERA_STORAGE_KEY,
  parseCameraId,
  toCameraId
} from '@/utils/camera'

const DEVICE_CACHE_MS = 10000
let devicesRequest = null

function readInitialCameraId() {
  const queryCamera = new URLSearchParams(window.location.search).get('camera')
  if (queryCamera) {
    const selection = parseCameraId(queryCamera)
    return toCameraId(selection.source, selection.deviceId)
  }

  const stored = localStorage.getItem(CAMERA_STORAGE_KEY)
  if (!stored) return 'local'
  const selection = parseCameraId(stored)
  return toCameraId(selection.source, selection.deviceId)
}

const useCameraStore = defineStore('camera', {
  state: () => ({
    cameraId: readInitialCameraId(),
    cameraCatalog: [],
    xiaozhiDevices: [],
    devicesLoaded: false,
    loadingDevices: false,
    deviceError: '',
    lastDeviceSync: 0
  }),
  getters: {
    selection: state => parseCameraId(state.cameraId),
    source() {
      return this.selection.source
    },
    xiaozhiDeviceId() {
      return this.selection.deviceId
    },
    selectedDevice(state) {
      if (this.source !== 'xiaozhi' || !this.xiaozhiDeviceId) return null
      return state.xiaozhiDevices.find(
        device => device.device_id === this.xiaozhiDeviceId
      ) || null
    },
    selectedOnline() {
      return this.selectedDevice?.online ?? null
    },
    cameraLabel(state) {
      if (this.source === 'local') return '本机摄像头'
      if (this.source === 'rtsp') return '海康 RTSP'
      return this.selectedDevice?.name || '小智摄像头'
    },
    cameraOptions(state) {
      const configured = state.cameraCatalog.map(camera => ({
        id: camera.camera_id,
        label: camera.name,
        detail: camera.detail || (
          camera.source === 'xiaozhi'
            ? (camera.online ? '在线' : '未出图')
            : ''
        ),
        online: camera.source === 'xiaozhi'
          ? Boolean(camera.online)
          : undefined,
        source: camera.source
      }))
      const options = configured.length
        ? configured
        : [
            {
              id: 'local',
              label: '本机摄像头',
              detail: 'USB / 内置',
              source: 'local'
            },
            {
              id: 'rtsp',
              label: '海康 RTSP',
              detail: '网络视频',
              source: 'rtsp'
            }
          ]

      if (!options.some(option => option.source === 'xiaozhi')) {
        options.push({
          id: 'xiaozhi',
          label: '小智摄像头',
          detail: state.loadingDevices ? '正在查找' : '暂无设备',
          online: false,
          source: 'xiaozhi'
        })
      }
      return options
    }
  },
  actions: {
    selectCamera(cameraId, persist = true) {
      const { source, deviceId } = parseCameraId(cameraId)
      const normalizedId = toCameraId(source, deviceId)
      this.cameraId = normalizedId
      if (persist) {
        localStorage.setItem(CAMERA_STORAGE_KEY, normalizedId)
      }
      return normalizedId
    },
    async loadXiaozhiDevices(force = false, quiet = false) {
      const cacheIsFresh = (
        this.devicesLoaded
        && Date.now() - this.lastDeviceSync < DEVICE_CACHE_MS
      )
      if (!force && cacheIsFresh) return this.xiaozhiDevices
      if (devicesRequest) return devicesRequest

      this.loadingDevices = true
      this.deviceError = ''
      devicesRequest = listCameras({ silent: quiet })
        .then(response => {
          this.cameraCatalog = Array.isArray(response?.cameras)
            ? response.cameras
            : []
          this.xiaozhiDevices = this.cameraCatalog
            .filter(camera => camera.source === 'xiaozhi')
            .map(camera => ({
              device_id: camera.device_id,
              name: camera.name,
              online: Boolean(camera.online)
            }))
          this.devicesLoaded = true
          this.lastDeviceSync = Date.now()
          this.deviceError = response?.xiaozhi_error || ''

          if (this.source === 'xiaozhi') {
            const currentStillExists = this.xiaozhiDevices.some(
              device => device.device_id === this.xiaozhiDeviceId
            )
            if (!currentStillExists) {
              const nextDevice = (
                this.xiaozhiDevices.find(device => device.online)
                || this.xiaozhiDevices[0]
              )
              this.selectCamera(
                toCameraId('xiaozhi', nextDevice?.device_id || '')
              )
            }
          }
          return this.xiaozhiDevices
        })
        .catch(error => {
          this.deviceError = error?.message || '小智设备列表读取失败'
          throw error
        })
        .finally(() => {
          this.loadingDevices = false
          devicesRequest = null
        })

      return devicesRequest
    }
  }
})

export default useCameraStore
