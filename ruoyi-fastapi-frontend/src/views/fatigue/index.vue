<template>
  <div class="fatigue-page">
    <section class="page-intro">
      <div class="page-intro__copy">
        <span class="page-intro__eyebrow">BEHAVIOUR SIGNAL</span>
        <h1>疲劳检测</h1>
        <p>根据眼口行为与姿态变化观察当前专注度，数据约每秒更新一次。</p>
      </div>
      <div class="page-intro__controls">
        <el-select
          v-model="cameraSource"
          class="source-select"
          aria-label="摄像头来源"
        >
          <el-option label="小智摄像头" value="xiaozhi" />
          <el-option label="本机摄像头" value="local" />
          <el-option label="海康 RTSP" value="rtsp" />
        </el-select>
        <el-select
          v-if="cameraSource === 'xiaozhi'"
          v-model="xiaozhiDevice"
          class="source-select source-select--device"
          placeholder="自动选择在线设备"
          clearable
          @visible-change="visible => visible && loadDevices()"
        >
          <el-option
            v-for="device in devices"
            :key="device.device_id"
            :label="`${device.name}${device.online ? ' · 在线' : ' · 未出图'}`"
            :value="device.device_id"
          />
        </el-select>
        <el-button :loading="resetting" @click="restartSession">
          <el-icon><Refresh /></el-icon>
          重新检测
        </el-button>
      </div>
    </section>

    <div class="connection-line">
      <span class="connection-dot" :class="{ 'is-live': videoState === 'online' }"></span>
      <span>{{ statusMessage }}</span>
      <span v-if="serviceError" class="connection-line__error">{{ serviceError }}</span>
      <router-link to="/index" class="connection-line__back">返回首页</router-link>
    </div>

    <div class="primary-grid">
      <div class="video-column">
        <main class="video-shell" aria-label="疲劳检测实时画面">
          <div
            class="video-frame"
            :style="{ aspectRatio: videoAspectRatio }"
          >
          <img
            :key="streamKey"
            :src="videoStreamUrl"
            alt="疲劳检测实时视频"
            @load="onVideoLoad"
            @error="onVideoError"
          />
          <div class="video-vignette" aria-hidden="true"></div>
          <div v-if="videoState !== 'online'" class="video-placeholder">
            <el-icon :size="34"><VideoCamera /></el-icon>
            <strong>{{ videoState === 'error' ? '视频连接失败' : '正在连接摄像头' }}</strong>
            <span>{{ videoState === 'error' ? videoError : '请稍候，画面将在连接后出现' }}</span>
          </div>
          <div class="video-signal" :class="{ 'is-active': result.face_detected }">
            <span></span>
            {{ result.face_detected ? '面部信号已锁定' : '正在搜索面部' }}
          </div>
          <button
            type="button"
            class="detection-toggle"
            :class="{ 'is-active': showBoxes }"
            :aria-pressed="showBoxes"
            @click="toggleDetectionBoxes"
          >
            <el-icon><Aim /></el-icon>
            {{ showBoxes ? '隐藏检测信息' : '显示检测信息' }}
          </button>
          <div class="video-caption">
            <span>{{ cameraLabel }}</span>
            <span>FACE SIGNAL / {{ result.face_detected ? 'TRACKED' : 'SEARCHING' }}</span>
          </div>
          </div>
          <div class="video-note">
            专注度是行为趋势提示，不替代医学疲劳评估。若长时间显示“无效”，请检查光线、面部遮挡和人物距离。
          </div>
        </main>

        <section class="frame-priority frame-priority--below">
          <div class="frame-priority__heading">
            <div>
              <span>SINGLE FRAME</span>
              <h3>单帧检测值</h3>
            </div>
            <em>实时</em>
          </div>
          <div class="frame-priority__grid">
            <div class="frame-metric">
              <span class="frame-metric__label">
                左眼闭合
                <el-tooltip
                  content="当前这一帧左眼处于闭合状态的可能性，范围是 0～1，越大表示越像闭眼。"
                  placement="top"
                >
                  <QuestionFilled class="metric-help" tabindex="0" />
                </el-tooltip>
              </span>
              <strong>{{ formatNumber(result.p_left, 3) }}</strong>
              <small>P(closed)</small>
            </div>
            <div class="frame-metric">
              <span class="frame-metric__label">
                右眼闭合
                <el-tooltip
                  content="当前这一帧右眼处于闭合状态的可能性，范围是 0～1，越大表示越像闭眼。"
                  placement="top"
                >
                  <QuestionFilled class="metric-help" tabindex="0" />
                </el-tooltip>
              </span>
              <strong>{{ formatNumber(result.p_right, 3) }}</strong>
              <small>P(closed)</small>
            </div>
            <div class="frame-metric">
              <span class="frame-metric__label">
                嘴巴张开
                <el-tooltip
                  content="当前这一帧嘴巴处于张开状态的可能性。瞬时张嘴不一定会被判定为哈欠。"
                  placement="top"
                >
                  <QuestionFilled class="metric-help" tabindex="0" />
                </el-tooltip>
              </span>
              <strong>{{ formatNumber(result.p_mouth, 3) }}</strong>
              <small>P(open)</small>
            </div>
            <div class="frame-metric">
              <span class="frame-metric__label">
                姿态置信度
                <el-tooltip
                  content="鼻子、双耳和双肩五个关键点的平均识别置信度，表示姿态检测是否可靠。"
                  placement="top"
                >
                  <QuestionFilled class="metric-help" tabindex="0" />
                </el-tooltip>
              </span>
              <strong>{{ formatNumber(result.posture_confidence, 3) }}</strong>
              <small>confidence</small>
            </div>
          </div>
        </section>
      </div>

      <aside class="focus-panel" aria-label="疲劳检测结论">
        <header class="panel-heading">
          <div>
            <span class="panel-kicker">FOCUS INDEX</span>
            <h2 class="panel-title">
              专注度
              <el-tooltip
                content="BiGRU 根据最近 30 个一秒特征综合计算的专注程度，数值越高表示越清醒、越专注。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </h2>
          </div>
          <span class="focus-tag" :class="`focus-tag--${scoreTone}`">{{ scoreStatus }}</span>
        </header>

        <div class="score-display" :class="`score-display--${scoreTone}`">
          <strong>{{ scoreText }}</strong>
          <span>0 — 1</span>
        </div>

        <div class="score-track" aria-hidden="true">
          <span :style="{ width: `${scorePercent}%` }"></span>
        </div>

        <div class="score-meta">
          <div>
            <span class="score-label">
              原始值
              <el-tooltip
                content="当前这一次 BiGRU 计算得到的原始专注度，波动通常比平滑值更明显。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ formatNumber(result.score_raw, 2) }}</strong>
          </div>
          <div>
            <span class="score-label">
              平滑值
              <el-tooltip
                content="由当前原始值和上一次结果按比例融合得到，用于减少分数跳动。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ formatNumber(result.score_ema, 2) }}</strong>
          </div>
        </div>

        <section class="warmup-card">
          <div class="warmup-card__top">
            <span class="score-label">
              特征窗口
              <el-tooltip
                content="已经收集到的有效一秒特征数量。达到 30 个后，BiGRU 才会开始产生专注度。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ result.feature_buffer || 0 }} / {{ result.feature_target || 30 }}</strong>
          </div>
          <div class="warmup-track">
            <span :style="{ width: `${featurePercent}%` }"></span>
          </div>
          <p v-if="result.score_ema == null">
            {{ warmupHint }}
          </p>
          <p v-else>已进入实时评分阶段</p>
        </section>

        <section class="counter-grid">
          <div>
            <span class="score-label">
              累计眨眼
              <el-tooltip
                content="从本次检测开始以来累计完成的眨眼次数，不是最近一分钟的次数。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ result.blink_total || 0 }}</strong>
          </div>
          <div>
            <span class="score-label">
              累计哈欠
              <el-tooltip
                content="从本次检测开始以来累计完成的哈欠次数，短时间张嘴不会直接计入。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ result.yawn_total || 0 }}</strong>
          </div>
        </section>

        <div class="score-legend">
          <span><i class="legend-dot legend-dot--red"></i>低于 0.30 疲劳</span>
          <span><i class="legend-dot legend-dot--orange"></i>0.30—0.55 困倦</span>
          <span><i class="legend-dot legend-dot--green"></i>高于 0.55 清醒</span>
        </div>
      </aside>
    </div>

    <section class="detail-deck" aria-label="疲劳检测详细指标">
      <header class="detail-deck__heading">
        <div>
          <span class="panel-kicker">MEASUREMENT DETAIL</span>
          <h2>检测数据</h2>
        </div>
        <div class="detail-deck__meta">
          <strong v-if="lastStep" class="step-index">
            STEP {{ lastStep.step_idx }} · {{ formatNumber(lastStep.timestamp_s, 1) }}s
          </strong>
          <span :class="lastStep?.valid ? 'validity-ok' : 'validity-wait'">
            {{ lastStep ? (lastStep.valid ? '当前特征有效' : '当前特征无效') : '正在蓄积特征' }}
          </span>
        </div>
      </header>

      <div class="detail-grid">
        <article class="data-card data-card--frame">
          <header class="data-card__heading">
            <div>
              <span>FRAME FLOW</span>
              <h3>画面流转</h3>
            </div>
            <span class="face-state" :class="{ 'face-state--active': result.face_detected }">
              {{ result.face_detected ? '已检测到面部' : '等待面部' }}
            </span>
          </header>

          <div class="runtime-grid">
            <div class="runtime-item">
              <span class="runtime-label">
                推理帧率
                <el-tooltip
                  content="每秒完成多少次面部、眼口和姿态推理。数值越高，画面更新越流畅。"
                  placement="top"
                >
                  <QuestionFilled class="metric-help" tabindex="0" />
                </el-tooltip>
              </span>
              <strong>{{ formatNumber(result.inference_fps, 1) }}</strong>
              <small>FPS</small>
            </div>
            <div class="runtime-item">
              <span class="runtime-label">
                平均延迟
                <el-tooltip
                  content="模型处理一帧画面所需的时间，数值越低响应越快。"
                  placement="top"
                >
                  <QuestionFilled class="metric-help" tabindex="0" />
                </el-tooltip>
              </span>
              <strong>{{ formatNumber(result.inference_latency_ms, 1) }}</strong>
              <small>ms</small>
            </div>
          </div>

          <div class="metric-list">
            <MetricRow
              label="时序运算速度"
              help="BiGRU 时序模型单次推理的理论处理速度，不是专注度分数的刷新频率。"
              :value="result.temporal_fps"
              :digits="1"
              suffix="FPS"
            />
          </div>
        
        </article>

        <article class="data-card data-card--eye">
          <header class="data-card__heading">
            <div>
              <span>60S EYE</span>
              <h3>眼部监测</h3>
            </div>
            <span class="confidence-state">近 60 秒</span>
          </header>

          <div class="metric-list">
            <MetricRow
              label="眼睛闭合占比"
              help="最近 60 秒中，眼睛闭合概率超过 0.80 的时间比例，也叫 PERCLOS。"
              :value="features.perclos"
              :digits="3"
              strong
            />
            <MetricRow
              label="眨眼频率"
              
              :value="features.blink_rate_bpm"
              :digits="2"
              suffix="次/分"
            />
            <MetricRow
              label="平均眨眼时长"
              
              :value="features.mean_blink_duration"
              :digits="3"
              suffix="秒"
            />
            <MetricRow
              label="眼闭合方差"
              help="最近 60 秒眼闭合概率的波动程度。越大表示睁闭眼变化越频繁，不代表一定更疲劳。"
              :value="features.eye_closure_variance"
              :digits="4"
            />
            <MetricRow
              label="平均眼闭合"
              help="最近 60 秒内所有有效帧的眼睛闭合概率平均值，不是闭眼时间占比。"
              :value="features.mean_p_eye"
              :digits="3"
            />
          </div>
        </article>

        <article class="data-card data-card--yawn">
          <header class="data-card__heading">
            <div>
              <span>60S YAWN</span>
              <h3>哈欠节律</h3>
            </div>
            <span class="confidence-state">近 60 秒</span>
          </header>

          <div class="metric-list">
            <MetricRow
              label="哈欠频率"
              
              :value="features.yawn_rate_per_min"
              :digits="2"
              suffix="次/分"
            />
            <MetricRow
              label="平均哈欠时长"
              
              :value="features.mean_yawn_duration"
              :digits="3"
              suffix="秒"
            />
            <MetricRow
              label="张嘴比例"
              help="最近 60 秒中张嘴概率超过 0.70 的时间比例，可能来自哈欠、说话或呼吸。"
              :value="features.mouth_open_ratio"
              :digits="3"
            />
            <MetricRow
              label="平均张嘴"
              help="最近 60 秒内所有有效帧的嘴巴张开概率平均值。"
              :value="features.mean_p_mouth"
              :digits="3"
            />
          </div>
        </article>

        <article class="data-card data-card--pose">
          <header class="data-card__heading">
            <div>
              <span>60S POSTURE</span>
              <h3>身体姿态</h3>
            </div>
            <span class="confidence-state">关键点趋势</span>
          </header>

          <div class="metric-list">
            <MetricRow
              label="头部俯仰"
              help="鼻子相对双肩中点的垂直位置，并按肩宽归一化。正值通常表示头部位置更偏下。"
              :value="features.head_pitch"
              :digits="3"
              signed
            />
            <MetricRow
              label="头部侧倾"
              help="双耳连线的倾斜角，单位为弧度。正负值表示头部向不同方向倾斜。"
              :value="features.head_roll"
              :digits="3"
              signed
            />
            <MetricRow
              label="肩部倾斜"
              help="双肩连线的倾斜角，单位为弧度，数值越大表示肩线倾斜越明显。"
              :value="features.shoulder_tilt"
              :digits="3"
              signed
            />
            <MetricRow
              label="头部尺寸比"
              help="双耳距离与肩宽的比例，可用于观察人物距离和姿态变化。"
              :value="features.head_size_ratio"
              :digits="3"
            />
            <MetricRow
              label="头部运动量"
              help="相邻画面之间鼻子的平均移动量，数值越大表示头部动作越多。"
              :value="features.head_motion_energy"
              :digits="4"
            />
            <MetricRow
              label="头部垂直漂移"
              help="最近 60 秒鼻子垂直位置的标准差，越大表示头部上下波动越明显。"
              :value="features.head_drift_y"
              :digits="4"
            />
            <MetricRow
              label="姿态漂移"
              help="最近 60 秒肩膀中点垂直位置的标准差，反映身体整体上下移动程度。"
              :value="features.posture_drift"
              :digits="4"
            />
            <MetricRow
              label="关键点可见度"
              help="五个姿态关键点的平均检测置信度。低于 0.40 时姿态特征会被视为不可靠。"
              :value="features.kpt_visibility"
              :digits="3"
            />
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Aim, QuestionFilled, Refresh, VideoCamera } from '@element-plus/icons-vue'
import { ElMessage, ElTooltip } from 'element-plus'
import request from '@/utils/request'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'

const cameraSource = ref('local')
const xiaozhiDevice = ref('')
const devices = ref([])
const streamKey = ref(0)
const videoState = ref('connecting')
const videoAspectRatio = ref('4 / 3')
const videoError = ref('')
const serviceError = ref('')
const resetting = ref(false)
const showBoxes = ref(false)

const emptyResult = () => ({
  ok: true,
  status: 'starting',
  message: '正在等待疲劳检测数据',
  face_detected: false,
  keypoints: [],
  boxes: {},
  inference_fps: null,
  inference_latency_ms: null,
  temporal_fps: null,
  p_left: null,
  p_right: null,
  p_mouth: null,
  posture_confidence: null,
  warmup_progress: 0,
  warmup_target: 1800,
  feature_buffer: 0,
  feature_target: 30,
  last_step: null,
  score_raw: null,
  score_ema: null,
  score_status: '预热中',
  blink_total: 0,
  yawn_total: 0
})

const result = ref(emptyResult())

const sourceQuery = computed(() => {
  const params = new URLSearchParams({ source: cameraSource.value })
  if (cameraSource.value === 'xiaozhi' && xiaozhiDevice.value) {
    params.set('device_id', xiaozhiDevice.value)
  }
  return params.toString()
})

const videoStreamUrl = computed(
  () => `${baseURL}/fatigue/feed?${sourceQuery.value}` +
    `&show_boxes=${showBoxes.value ? 1 : 0}` +
    `&stream=${streamKey.value}`
)

const cameraLabel = computed(() => {
  if (cameraSource.value === 'local') return '本机摄像头'
  if (cameraSource.value === 'rtsp') return '海康 RTSP'
  if (!xiaozhiDevice.value) return '小智摄像头'
  const selected = devices.value.find(item => item.device_id === xiaozhiDevice.value)
  return selected?.name || '小智摄像头'
})

const lastStep = computed(() => result.value.last_step)
const features = computed(() => lastStep.value?.features || {})

const scoreTone = computed(() => {
  const score = result.value.score_ema
  if (score == null) return 'wait'
  if (score < 0.30) return 'fatigued'
  if (score < 0.55) return 'drowsy'
  return 'alert'
})

const scoreStatus = computed(() => result.value.score_status || {
  wait: '预热中',
  fatigued: '疲劳',
  drowsy: '困倦',
  alert: '清醒'
}[scoreTone.value])

const scoreText = computed(() => formatNumber(result.value.score_ema, 2, '--'))
const scorePercent = computed(() => {
  const score = Number(result.value.score_ema)
  return Number.isFinite(score) ? Math.max(0, Math.min(100, score * 100)) : 0
})
const featurePercent = computed(() => {
  const current = Number(result.value.feature_buffer) || 0
  const target = Number(result.value.feature_target) || 30
  return Math.max(0, Math.min(100, (current / target) * 100))
})
const warmupHint = computed(() => {
  const progress = Number(result.value.warmup_progress) || 0
  const target = Number(result.value.warmup_target) || 1800
  if (progress < target) {
    return `正在建立最近 60 秒行为基线（${progress}/${target} 帧）`
  }
  return '正在收集 30 个有效一秒特征，通常还需要约 30 秒'
})

const statusMessage = computed(() => {
  if (videoState.value === 'error') return '摄像头画面暂不可用'
  if (serviceError.value) return '视频已连接，等待疲劳检测服务'
  return result.value.message || '正在连接疲劳检测服务'
})

const MetricRow = (props) => h(
  'div',
  { class: ['metric-row', { 'metric-row--strong': props.strong }] },
  [
    h('span', { class: 'metric-label' }, [
      h('span', props.label),
      props.help
        ? h(
            ElTooltip,
            {
              content: props.help,
              placement: 'top',
              effect: 'dark',
              popperClass: 'fatigue-metric-tooltip'
            },
            {
              default: () => h(QuestionFilled, {
                class: 'metric-help',
                tabindex: '0',
                'aria-label': props.help
              })
            }
          )
        : null
    ]),
    h(
      'strong',
      formatNumber(props.value, props.digits ?? 2, '--', props.signed) +
        (props.suffix ? ` ${props.suffix}` : '')
    )
  ]
)
MetricRow.props = {
  label: String,
  value: [Number, String],
  digits: Number,
  suffix: String,
  strong: Boolean,
  signed: Boolean,
  help: String
}

function formatNumber(value, digits = 2, fallback = '--', signed = false) {
  if (value == null || value === '') return fallback
  const number = Number(value)
  if (!Number.isFinite(number)) return fallback
  const text = number.toFixed(digits)
  return signed && number >= 0 ? `+${text}` : text
}

function toggleDetectionBoxes() {
  showBoxes.value = !showBoxes.value
  streamKey.value += 1
}

async function loadDevices() {
  try {
    const data = await request({
      url: '/video/xiaozhi/devices',
      method: 'get',
      timeout: 20000
    })
    devices.value = data.devices || []
    if (cameraSource.value === 'xiaozhi' && !xiaozhiDevice.value) {
      const online = devices.value.find(device => device.online)
      if (online) xiaozhiDevice.value = online.device_id
    }
  } catch {
    devices.value = []
  }
}

async function fetchResults() {
  try {
    const response = await fetch(
      `${baseURL}/fatigue/results?${sourceQuery.value}&_=${Date.now()}`
    )
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || data.message || '疲劳检测服务返回异常')
    }
    result.value = { ...emptyResult(), ...data }
    serviceError.value = data.ok === false ? data.message : ''
  } catch (error) {
    serviceError.value = error.message || '无法连接疲劳检测服务'
  }
}

async function resetRemoteSession() {
  try {
    const response = await fetch(
      `${baseURL}/fatigue/reset?${sourceQuery.value}`,
      { method: 'POST' }
    )
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      throw new Error(data.detail || data.message || '重置失败')
    }
  } catch (error) {
    serviceError.value = error.message || '无法连接疲劳检测服务'
  }
}

async function restartSession() {
  resetting.value = true
  stopPolling()
  result.value = emptyResult()
  serviceError.value = ''
  streamKey.value += 1
  try {
    await resetRemoteSession()
    startPolling()
    ElMessage.success('已重新开始疲劳检测')
  } finally {
    resetting.value = false
  }
}

function onVideoLoad(event) {
  videoState.value = 'online'
  videoError.value = ''
  const image = event?.currentTarget
  if (image?.naturalWidth && image?.naturalHeight) {
    videoAspectRatio.value = `${image.naturalWidth} / ${image.naturalHeight}`
  }
}

function onVideoError() {
  videoState.value = 'error'
  videoError.value = '请检查摄像头连接，或在设备管理中启动小智摄像头采集'
}

let pollTimer = null
let deviceTimer = null
let sourceWatchReady = false

function startPolling() {
  stopPolling()
  fetchResults()
  pollTimer = setInterval(fetchResults, 800)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleVisibilityChange() {
  if (document.hidden) {
    stopPolling()
  } else {
    startPolling()
  }
}

watch([cameraSource, xiaozhiDevice], async () => {
  if (!sourceWatchReady) return
  stopPolling()
  result.value = emptyResult()
  serviceError.value = ''
  videoState.value = 'connecting'
  streamKey.value += 1
  await resetRemoteSession()
  startPolling()
})

onMounted(async () => {
  await loadDevices()
  sourceWatchReady = true
  startPolling()
  deviceTimer = setInterval(() => {
    if (cameraSource.value === 'xiaozhi') loadDevices()
  }, 5000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  clearInterval(deviceTimer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.fatigue-page {
  min-height: 100%;
  padding: 24px;
  color: #172033;
  background:
    radial-gradient(circle at 5% 0%, rgba(56, 111, 164, 0.11), transparent 28%),
    #eef2f6;
}
.page-intro {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 14px;
}
.page-intro__eyebrow,
.panel-kicker {
  color: #667085;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
}
.page-intro h1 {
  margin: 4px 0 6px;
  color: #111827;
  font-size: 30px;
  line-height: 1.15;
}
.page-intro p {
  margin: 0;
  color: #667085;
  font-size: 14px;
}
.page-intro__controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.source-select {
  width: 150px;
}
.source-select--device {
  width: 220px;
}
.connection-line {
  display: flex;
  min-height: 38px;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 0 4px;
  color: #667085;
  font-size: 13px;
}
.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #98a2b3;
}
.connection-dot.is-live {
  background: #2f9e73;
  box-shadow: 0 0 0 4px rgba(47, 158, 115, 0.12);
}
.connection-line__error {
  color: #b54708;
}
.connection-line__back {
  margin-left: auto;
  color: #335c99;
  text-decoration: none;
}
.primary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(310px, 360px);
  gap: 16px;
  align-items: start;
}
.video-column {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
}
.focus-panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  color: #eef2f7;
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.04), transparent 38%),
    #243244;
  box-shadow: 0 18px 38px rgba(23, 32, 51, 0.18);
}
.focus-panel {
  padding: 22px;
}
.panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 15px;
}
.panel-heading h2 {
  margin: 3px 0 0;
  color: #fff;
  font-size: 20px;
  line-height: 1.2;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 5px;
}
.frame-priority {
  padding: 14px;
  background: #f9fbfc;
  border: 1px solid #dde5ec;
  border-radius: 12px;
  box-shadow: 0 8px 22px rgba(32, 48, 70, 0.06);
}
.frame-priority__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.frame-priority__heading span {
  display: block;
  margin-bottom: 2px;
  color: #7e8da0;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
}
.frame-priority__heading h3 {
  margin: 0;
  color: #253247;
  font-size: 14px;
  line-height: 1.3;
}
.frame-priority__heading em {
  padding: 3px 7px;
  color: #24745c;
  font-size: 9px;
  font-style: normal;
  background: #e7f5ef;
  border-radius: 20px;
}
.frame-priority__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.frame-metric {
  min-width: 0;
  padding: 9px;
  background: #fff;
  border: 1px solid #e4eaf0;
  border-radius: 8px;
}
.frame-metric__label {
  display: flex;
  min-height: 15px;
  align-items: center;
  gap: 4px;
  color: #64748b;
  font-size: 10.5px;
  white-space: nowrap;
}
.frame-metric strong {
  display: inline-block;
  margin-top: 7px;
  color: #b9680d;
  font-size: 24px;
  font-weight: 650;
  line-height: 1;
  letter-spacing: -0.035em;
  font-variant-numeric: tabular-nums;
}
.frame-metric small {
  display: block;
  margin-top: 4px;
  color: #94a3b8;
  font-size: 9px;
}
.runtime-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 15px;
}
.runtime-item {
  padding: 11px 12px;
  background: #f2f5f8;
  border: 1px solid #e8edf2;
  border-radius: 8px;
}
.runtime-item span,
.score-meta span,
.warmup-card__top span,
.counter-grid span {
  display: block;
  color: #64748b;
  font-size: 11px;
}
.runtime-item strong {
  margin-right: 3px;
  color: #1f2937;
  font-size: 20px;
  font-variant-numeric: tabular-nums;
}
.runtime-item small {
  color: #94a3b8;
  font-size: 10px;
}
.validity-ok,
.validity-wait {
  margin-bottom: 8px;
  padding: 2px 6px;
  font-size: 10px;
  border-radius: 10px;
}
.validity-ok {
  color: #24745c;
  background: #e7f5ef;
}
.validity-wait {
  color: #64748b;
  background: #eef2f6;
}
:global(.metric-row) {
  display: flex;
  min-height: 31px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #64748b;
  font-size: 12px;
  border-bottom: 1px solid #f1f4f7;
}
:global(.metric-row strong) {
  color: #263244;
  font-size: 12.5px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
:global(.metric-row--strong strong) {
  color: #b9680d;
}
.video-shell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  background: #151b24;
  border: 1px solid #25303d;
  border-radius: 16px;
  box-shadow: 0 18px 38px rgba(23, 32, 51, 0.16);
}
.video-frame {
  position: relative;
  width: 100%;
  min-height: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 35%, #293241, #14181e 68%);
}
.video-frame img {
  position: relative;
  z-index: 0;
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
  object-fit: cover;
}
.video-placeholder {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 9px;
  padding: 24px;
  color: #9da7b6;
  text-align: center;
}
.video-placeholder strong {
  color: #e7ebf1;
  font-size: 15px;
}
.video-placeholder span {
  max-width: 340px;
  font-size: 12px;
  line-height: 1.6;
}
.video-vignette {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(180deg, transparent 70%, rgba(6, 10, 16, 0.66));
}
.video-signal {
  position: absolute;
  z-index: 4;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 9px;
  color: #d5dbe4;
  font-size: 11px;
  background: rgba(14, 20, 28, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  backdrop-filter: blur(6px);
}
.video-signal span {
  width: 6px;
  height: 6px;
  background: #e7a740;
  border-radius: 50%;
}
.video-signal.is-active span {
  background: #7fe3b3;
  box-shadow: 0 0 0 4px rgba(127, 227, 179, 0.12);
}
.detection-toggle {
  position: absolute;
  z-index: 4;
  top: 16px;
  right: 16px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  color: #e5eaf1;
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  background: rgba(14, 20, 28, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 20px;
  backdrop-filter: blur(6px);
  transition:
    color 160ms ease,
    background-color 160ms ease,
    border-color 160ms ease;
}
.detection-toggle:hover {
  border-color: rgba(255, 210, 122, 0.56);
}
.detection-toggle.is-active {
  color: #202a38;
  background: #ffd27a;
  border-color: #ffd27a;
}
.detection-toggle:focus-visible {
  outline: 3px solid rgba(255, 210, 122, 0.36);
  outline-offset: 2px;
}
.video-caption {
  position: absolute;
  z-index: 4;
  right: 16px;
  bottom: 14px;
  left: 16px;
  display: flex;
  justify-content: space-between;
  color: rgba(255, 255, 255, 0.78);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.12em;
}
.video-note {
  padding: 12px 16px;
  color: #98a2b3;
  font-size: 11px;
  line-height: 1.6;
  background: #20252d;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.detail-deck {
  margin-top: 16px;
  padding: 20px;
  background: #f9fbfc;
  border: 1px solid #dde5ec;
  border-radius: 16px;
  box-shadow: 0 12px 28px rgba(32, 48, 70, 0.07);
}
.detail-deck__heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 15px;
}
.detail-deck__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-deck__heading h2 {
  margin: 3px 0 0;
  color: #1d2939;
  font-size: 20px;
  line-height: 1.25;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  align-items: stretch;
}
.data-card {
  --card-accent: #4d79a8;
  position: relative;
  min-width: 0;
  min-height: 100%;
  padding: 16px;
  background: #fff;
  border: 1px solid #e5ebf1;
  border-radius: 11px;
  overflow: hidden;
}
.data-card::before {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 3px;
  background: var(--card-accent);
  content: "";
}
.data-card--eye {
  --card-accent: #b07824;
}
.data-card--yawn {
  --card-accent: #b65c48;
}
.data-card--pose {
  --card-accent: #3f826d;
}
.data-card__heading {
  display: flex;
  min-height: 39px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.data-card__heading > div > span {
  display: block;
  margin-bottom: 3px;
  color: var(--card-accent);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
}
.data-card__heading h3 {
  margin: 0;
  color: #253247;
  font-size: 15px;
  line-height: 1.3;
}
.data-card__note {
  margin: 12px 0 0;
  padding-top: 11px;
  color: #8b98a8;
  font-size: 10.5px;
  line-height: 1.65;
  border-top: 1px solid #f1f4f7;
}
.face-state,
.confidence-state,
.step-index {
  padding: 4px 7px;
  color: #8a5a1e;
  font-size: 10px;
  font-weight: 600;
  background: #fff4e4;
  border-radius: 20px;
}
.face-state--active {
  color: #24745c;
  background: #e7f5ef;
}
.confidence-state,
.step-index {
  color: #667085;
  background: #f1f4f8;
  white-space: nowrap;
}
:global(.metric-label) {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
:global(.metric-help) {
  width: 0.82em;
  height: 0.82em;
  flex: 0 0 0.82em;
  color: #9aa6b5;
  cursor: help;
  opacity: 0.72;
  outline: none;
  transition:
    color 140ms ease,
    opacity 140ms ease,
    transform 140ms ease;
}
:global(.metric-help:hover),
:global(.metric-help:focus-visible) {
  color: var(--card-accent, #4d79a8);
  opacity: 1;
  transform: translateY(-1px);
}
:global(.data-card .metric-help) {
  width: 0.82em;
  height: 0.82em;
  flex-basis: 0.82em;
  opacity: 0.58;
}
.focus-panel .metric-help {
  color: #7e8da2;
}
.focus-panel .metric-help:hover,
.focus-panel .metric-help:focus-visible {
  color: #ffd27a;
}
.runtime-label {
  display: flex !important;
  align-items: center;
  gap: 5px;
}
.score-label {
  display: flex !important;
  align-items: center;
  gap: 4px;
}
:global(.fatigue-metric-tooltip.el-popper) {
  max-width: 280px;
  font-size: 12px;
  line-height: 1.65;
}
.focus-tag {
  padding: 4px 9px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 20px;
}
.focus-tag--wait {
  color: #c8d0dc;
  background: rgba(200, 208, 220, 0.1);
}
.focus-tag--alert {
  color: #83e7b5;
  background: rgba(131, 231, 181, 0.11);
}
.focus-tag--drowsy {
  color: #ffc266;
  background: rgba(255, 194, 102, 0.11);
}
.focus-tag--fatigued {
  color: #ff8b86;
  background: rgba(255, 139, 134, 0.11);
}
.score-display {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin: 12px 0 8px;
}
.score-display strong {
  color: #dce2ea;
  font-size: 58px;
  font-weight: 650;
  line-height: 1;
  letter-spacing: -0.06em;
  font-variant-numeric: tabular-nums;
}
.score-display span {
  padding-bottom: 5px;
  color: #7e8999;
  font-size: 10px;
}
.score-display--alert strong {
  color: #83e7b5;
}
.score-display--drowsy strong {
  color: #ffc266;
}
.score-display--fatigued strong {
  color: #ff8b86;
}
.score-track,
.warmup-track {
  overflow: hidden;
  background: rgba(255, 255, 255, 0.09);
  border-radius: 20px;
}
.score-track {
  height: 7px;
}
.warmup-track {
  height: 5px;
}
.score-track span,
.warmup-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  transition: width 320ms ease;
}
.score-track span {
  background: #83e7b5;
}
.score-display--drowsy + .score-track span {
  background: #ffc266;
}
.score-display--fatigued + .score-track span {
  background: #ff8b86;
}
.score-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 14px;
}
.score-meta > div {
  padding: 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}
.score-meta strong {
  display: block;
  margin-top: 3px;
  color: #eef2f7;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}
.warmup-card {
  margin-top: 18px;
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.09);
}
.warmup-card__top {
  display: flex;
  justify-content: space-between;
}
.warmup-card__top strong {
  color: #e6ebf2;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.warmup-track {
  margin: 9px 0;
}
.warmup-track span {
  background: #8ea6c7;
}
.warmup-card p {
  margin: 0;
  color: #939dad;
  font-size: 11px;
  line-height: 1.65;
}
.counter-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 18px;
}
.counter-grid > div {
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}
.counter-grid strong {
  display: block;
  margin-top: 4px;
  color: #fff;
  font-size: 25px;
  font-variant-numeric: tabular-nums;
}
.score-legend {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: auto;
  padding-top: 18px;
  color: #929cab;
  font-size: 10.5px;
}
.legend-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  border-radius: 50%;
}
.legend-dot--red {
  background: #ff8b86;
}
.legend-dot--orange {
  background: #ffc266;
}
.legend-dot--green {
  background: #83e7b5;
}
@media (max-width: 1280px) {
  .primary-grid {
    grid-template-columns: minmax(0, 1fr) 310px;
  }
  .detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .frame-priority__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 980px) {
  .primary-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 760px) {
  .fatigue-page {
    padding: 14px;
  }
  .page-intro,
  .page-intro__controls {
    align-items: stretch;
    flex-direction: column;
  }
  .page-intro h1 {
    font-size: 26px;
  }
  .source-select,
  .source-select--device {
    width: 100%;
  }
  .detail-grid {
    grid-template-columns: 1fr;
  }
  .video-caption {
    letter-spacing: 0.06em;
  }
  .connection-line {
    flex-wrap: wrap;
  }
  .connection-line__back {
    width: 100%;
    margin: 2px 0 0 16px;
  }
  .detail-deck {
    padding: 15px;
  }
  .detail-deck__heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
  .detail-deck__meta {
    flex-wrap: wrap;
  }
}
@media (max-width: 560px) {
  .frame-priority__grid {
    grid-template-columns: 1fr;
  }
  .score-display strong {
    font-size: 50px;
  }
  .video-signal {
    top: 10px;
    left: 10px;
  }
  .detection-toggle {
    top: 10px;
    right: 10px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .score-track span,
  .warmup-track span {
    transition: none;
  }
}
</style>
