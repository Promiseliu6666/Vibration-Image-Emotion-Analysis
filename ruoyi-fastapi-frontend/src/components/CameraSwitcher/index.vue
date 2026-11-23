<template>
  <div
    class="camera-switcher"
    :class="{
      'camera-switcher--compact': compact,
      'camera-switcher--error': cameraStore.source === 'xiaozhi' && cameraStore.deviceError,
      'camera-switcher--online': cameraStore.selectedOnline === true
    }"
    :title="statusTitle"
  >
    <span class="camera-switcher__signal" aria-hidden="true">
      <i></i>
    </span>
    <div class="camera-switcher__field">
      <span class="camera-switcher__label">当前摄像头</span>
      <el-select
        :model-value="cameraStore.cameraId"
        class="camera-switcher__select"
        :size="size"
        :loading="showLoading"
        aria-label="选择当前摄像头"
        @change="handleChange"
        @visible-change="handleVisibleChange"
      >
        <el-option
          v-for="option in cameraStore.cameraOptions"
          :key="option.id"
          :value="option.id"
          :label="option.label"
        >
          <span class="camera-option">
            <span class="camera-option__copy">
              <strong>{{ option.label }}</strong>
              <small>{{ option.detail }}</small>
            </span>
            <i
              v-if="option.source === 'xiaozhi'"
              class="camera-option__dot"
              :class="{ 'is-online': option.online }"
            ></i>
          </span>
        </el-option>
      </el-select>
    </div>
    <el-button
      text
      circle
      class="camera-switcher__refresh"
      :loading="showLoading"
      title="刷新摄像头列表"
      aria-label="刷新摄像头列表"
      @click="refresh()"
    >
      <el-icon v-if="!cameraStore.loadingDevices"><Refresh /></el-icon>
    </el-button>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import useCameraStore from '@/store/modules/camera'

const props = defineProps({
  size: {
    type: String,
    default: 'default'
  },
  compact: Boolean
})

const cameraStore = useCameraStore()
let refreshTimer = null

const showLoading = computed(() => (
  cameraStore.loadingDevices && !cameraStore.devicesLoaded
))

const statusTitle = computed(() => {
  if (cameraStore.source === 'xiaozhi' && cameraStore.deviceError) return cameraStore.deviceError
  if (cameraStore.selectedOnline === true) {
    return `${cameraStore.cameraLabel} · 在线`
  }
  if (cameraStore.selectedOnline === false) {
    return `${cameraStore.cameraLabel} · 未出图`
  }
  return cameraStore.cameraLabel
})

function handleChange(cameraId) {
  cameraStore.selectCamera(cameraId)
}

function handleVisibleChange(visible) {
  if (
    visible
    && Date.now() - cameraStore.lastDeviceSync > 10000
  ) {
    refresh(true)
  }
}

async function refresh(background = false) {
  try {
    await cameraStore.loadXiaozhiDevices(true, background)
  } catch {
    // The store exposes the error in the control title; the request layer
    // already displays the actionable backend message.
  }
}

onMounted(() => {
  refresh()
  refreshTimer = window.setInterval(() => {
    if (!document.hidden) refresh(true)
  }, 30000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  refreshTimer = null
})
</script>

<style scoped>
.camera-switcher {
  --camera-ink: #253b53;
  --camera-muted: #718197;
  --camera-line: #d7e1ea;
  --camera-signal: #6d8294;
  display: inline-flex;
  min-width: 252px;
  height: 50px;
  box-sizing: border-box;
  align-items: center;
  gap: 9px;
  padding: 5px 5px 5px 10px;
  color: var(--camera-ink);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(243, 247, 250, 0.92));
  border: 1px solid var(--camera-line);
  border-radius: 10px;
  box-shadow:
    0 8px 20px rgba(37, 59, 83, 0.07),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}
.camera-switcher--compact {
  height: 42px;
  min-width: 228px;
}
.camera-switcher--online {
  --camera-signal: #2e9b73;
}
.camera-switcher--error {
  --camera-signal: #bd5c50;
  --camera-line: #edc7c1;
}
.camera-switcher__signal {
  position: relative;
  display: grid;
  width: 18px;
  height: 28px;
  flex: 0 0 18px;
  place-items: center;
}
.camera-switcher__signal::before {
  position: absolute;
  width: 1px;
  height: 100%;
  content: "";
  background: linear-gradient(
    to bottom,
    transparent,
    rgba(41, 107, 158, 0.28),
    transparent
  );
}
.camera-switcher__signal i {
  z-index: 1;
  width: 8px;
  height: 8px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: var(--camera-signal);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--camera-signal) 17%, transparent);
}
.camera-switcher--online .camera-switcher__signal i {
  animation: camera-signal-pulse 2.4s ease-out infinite;
}
.camera-switcher__field {
  min-width: 0;
  flex: 1;
}
.camera-switcher__label {
  display: block;
  margin-bottom: -1px;
  color: var(--camera-muted);
  font-size: 9px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.11em;
}
.camera-switcher__select {
  width: 100%;
}
.camera-switcher__select :deep(.el-select__wrapper) {
  min-height: 24px;
  padding: 0 22px 0 0;
  background: transparent;
  box-shadow: none;
}
.camera-switcher__select :deep(.el-select__selected-item) {
  color: var(--camera-ink);
  font-size: 13px;
  font-weight: 650;
}
.camera-switcher__refresh {
  flex: 0 0 auto;
  color: #597085;
}
.camera-option {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}
.camera-option__copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.camera-option__copy strong {
  overflow: hidden;
  color: #2f455b;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
}
.camera-option__copy small {
  color: #8493a4;
  font-size: 11px;
}
.camera-option__dot {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: #b8c3ce;
}
.camera-option__dot.is-online {
  background: #2e9b73;
  box-shadow: 0 0 0 3px rgba(46, 155, 115, 0.11);
}
@keyframes camera-signal-pulse {
  0%, 45% {
    box-shadow: 0 0 0 3px rgba(46, 155, 115, 0.17);
  }
  75%, 100% {
    box-shadow: 0 0 0 7px rgba(46, 155, 115, 0);
  }
}
@media (max-width: 640px) {
  .camera-switcher {
    width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .camera-switcher--online .camera-switcher__signal i {
    animation: none;
  }
}
</style>
