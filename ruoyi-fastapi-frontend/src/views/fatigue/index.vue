<template>
  <div class="fatigue-page">
    <section class="page-intro">
      <div class="page-intro__copy">
        <span class="page-intro__eyebrow">BEHAVIOUR SIGNAL</span>
        <h1>疲劳检测</h1>
        <p>根据眼口状态与姿态变化评估当前疲劳度，数据约每秒更新一次。</p>
      </div>
      <div class="page-intro__controls">
        <CameraSwitcher />
        <el-button :loading="resetting" :disabled="!sourceQuery" @click="restartSession">
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
            v-if="videoStreamUrl"
            ref="videoImg"
            :key="`${cameraStore.cameraId}-${streamKey}`"
            :src="videoStreamUrl"
            alt="疲劳检测实时视频"
            @load="onVideoLoad"
            @error="onVideoError"
          />
          <svg
            v-if="showBoxes"
            class="detection-overlay"
            :viewBox="`0 0 ${videoSize.width} ${videoSize.height}`"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <g
              v-for="box in detectionBoxes"
              :key="box.name"
              class="detection-overlay__box"
            >
              <rect
                :x="box.x1 * videoSize.width"
                :y="box.y1 * videoSize.height"
                :width="box.width * videoSize.width"
                :height="box.height * videoSize.height"
                :stroke="box.color"
                vector-effect="non-scaling-stroke"
              />
              <text
                :x="box.x1 * videoSize.width"
                :y="box.labelY * videoSize.height"
                :fill="box.color"
              >
                {{ box.label }}
              </text>
            </g>
            <line
              v-for="(segment, index) in poseSegments"
              :key="`segment-${index}`"
              :x1="segment.x1 * videoSize.width"
              :y1="segment.y1 * videoSize.height"
              :x2="segment.x2 * videoSize.width"
              :y2="segment.y2 * videoSize.height"
              class="detection-overlay__line"
              vector-effect="non-scaling-stroke"
            />
            <circle
              v-for="(point, index) in poseKeypoints"
              :key="`point-${index}`"
              :cx="point.x * videoSize.width"
              :cy="point.y * videoSize.height"
              r="3"
              class="detection-overlay__point"
              vector-effect="non-scaling-stroke"
            />
          </svg>
          <div class="video-vignette" aria-hidden="true"></div>
          <div v-if="videoState !== 'online'" class="video-placeholder">
            <el-icon :size="34"><VideoCamera /></el-icon>
            <strong>{{ !sourceQuery ? '请选择小智设备' : videoState === 'error' ? '视频连接失败' : '正在连接摄像头' }}</strong>
            <span>{{ !sourceQuery ? '选择已接入的摄像头后开始监测' : videoState === 'error' ? videoError : '请稍候，画面将在连接后出现' }}</span>
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
            {{ showBoxes ? '隐藏检测框' : '显示检测框' }}
          </button>
          <div class="video-caption">
            <span>{{ cameraLabel }}</span>
            <span>FACE SIGNAL / {{ result.face_detected ? 'TRACKED' : 'SEARCHING' }}</span>
          </div>
          </div>
          <div class="video-note">
            疲劳度是行为趋势提示，不替代医学疲劳评估。若长时间显示“无效”，请检查光线、面部遮挡和人物距离。
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
                左眼闭合概率
              </span>
              <strong>{{ formatNumber(result.p_left, 3) }}</strong>
              <small>P(closed)</small>
            </div>
            <div class="frame-metric">
              <span class="frame-metric__label">
                右眼闭合概率
              </span>
              <strong>{{ formatNumber(result.p_right, 3) }}</strong>
              <small>P(closed)</small>
            </div>
            <div class="frame-metric">
              <span class="frame-metric__label">
                嘴巴张开概率
              </span>
              <strong>{{ formatNumber(result.p_mouth, 3) }}</strong>
              <small>P(open)</small>
            </div>
            <div class="frame-metric">
              <span class="frame-metric__label">
                姿态置信度
                <el-tooltip
                  content="表示系统对鼻子、双耳和双肩等关键点的识别可靠程度。数值越高，姿态数据越可信；数值过低时，可能受遮挡、光线或拍摄距离影响。"
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
            <span class="panel-kicker">FATIGUE INDEX</span>
            <h2 class="panel-title">
              疲劳度
              <el-tooltip
                content="表示系统根据最近约 30 秒的眨眼、哈欠和姿态给出的疲劳程度估计。数值越高，表示疲劳倾向越明显；数值越低，表示当前越清醒。"
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
                content="表示当前时刻的即时疲劳度估计。数值越高表示越疲劳，越低表示越清醒；其短期波动较明显。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ formatNumber(fatigueScoreRaw, 2) }}</strong>
          </div>
          <div>
            <span class="score-label">
              平滑值
              <el-tooltip
                content="由当前疲劳度与历史结果加权得到，用于降低分数的短期波动。数值越高表示疲劳倾向越明显，越低表示越清醒。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ formatNumber(fatigueScore, 2) }}</strong>
          </div>
        </div>

        <section class="warmup-card">
          <div class="warmup-card__top">
            <span class="score-label">
              特征窗口
              <el-tooltip
                content="表示系统已累计多少秒有效数据。达到 30 秒后开始评分；该数值仅反映准备进度。"
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
          <p v-if="fatigueScore == null">
            {{ warmupHint }}
          </p>
          <p v-else>已进入实时评分阶段</p>
        </section>

        <section class="counter-grid">
          <div>
            <span class="score-label">
              累计眨眼
              <el-tooltip
                content="表示本次检测累计完成的眨眼次数。应结合检测时长与个人平时情况解读，不宜单独作为疲劳判断依据。"
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
                content="表示本次检测累计完成的哈欠次数。数值较高通常提示困倦倾向，但仍需结合检测时长和个人情况判断。"
                placement="top"
              >
                <QuestionFilled class="metric-help" tabindex="0" />
              </el-tooltip>
            </span>
            <strong>{{ result.yawn_total || 0 }}</strong>
          </div>
        </section>

        <div class="score-legend">
          <span><i class="legend-dot legend-dot--green"></i>低于 0.45 清醒</span>
          <span><i class="legend-dot legend-dot--orange"></i>0.45—0.70 困倦</span>
          <span><i class="legend-dot legend-dot--red"></i>高于 0.70 疲劳</span>
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
                  content="表示系统每秒处理的画面帧数。数值越高，画面更新越流畅；数值过低时可能出现延迟。"
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
                  content="表示系统处理一帧画面所需的平均时间。数值越低，响应越快；数值越高，延迟越明显。"
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
              help="表示疲劳度模型每秒可完成的计算次数。数值越高，评分更新越及时；该指标不等同于画面帧率。"
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
              help="最近 60 秒中，眼睛闭合概率超过 0.80 的时间比例。数值越高，通常表示困倦倾向越明显；数值越低，表示睁眼时间占比越高。"
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
              help="表示最近 60 秒闭眼程度的波动幅度。数值越高，睁眼与闭眼的切换越频繁；数值越低，状态越稳定。该指标不能单独用于判断疲劳。"
              :value="features.eye_closure_variance"
              :digits="4"
            />
            <MetricRow
              label="平均眼闭合"
              help="表示最近 60 秒闭眼程度的平均值。数值越高，画面中的闭眼倾向越明显；数值越低，睁眼倾向越明显。"
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
              help="最近 60 秒中张嘴概率超过 0.70 的时间比例。数值越高，张口持续时间越长，可能由哈欠、说话或呼吸引起；数值越低，闭嘴时间越多。"
              :value="features.mouth_open_ratio"
              :digits="3"
            />
            <MetricRow
              label="平均张嘴"
              help="表示最近 60 秒张嘴程度的平均值。数值越高，整体张口程度越明显；数值越低，整体越接近闭嘴状态。"
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
              help="表示头部相对肩部的上下位置变化。数值越高，通常表示低头或前倾程度越明显；数值越低，越接近抬头状态。持续低垂可作为困倦线索。"
              :value="features.head_pitch"
              :digits="3"
              signed
            />
            <MetricRow
              label="头部侧倾"
              help="表示头部向左右倾斜的程度。绝对值越大，倾斜越明显；正负号仅表示倾斜方向，不代表疲劳程度。"
              :value="features.head_roll"
              :digits="3"
              signed
            />
            <MetricRow
              label="肩部倾斜"
              help="表示双肩高度不一致的程度。绝对值越大，肩线倾斜越明显；正负号仅表示倾斜方向，不直接代表疲劳。"
              :value="features.shoulder_tilt"
              :digits="3"
              signed
            />
            <MetricRow
              label="头部尺寸比"
              help="表示头部尺寸相对肩宽的比例。数值越高，通常表示人物离镜头越近；数值越低，表示距离越远。该指标不直接反映疲劳。"
              :value="features.head_size_ratio"
              :digits="3"
            />
            <MetricRow
              label="头部运动量"
              help="表示相邻画面之间头部位置的平均变化量。数值越高，头部活动越明显；数值越低，头部越稳定。该指标不能单独用于判断疲劳。"
              :value="features.head_motion_energy"
              :digits="4"
            />
            <MetricRow
              label="头部垂直漂移"
              help="表示最近 60 秒头部上下位置的波动幅度。数值越高，点头或上下移动越明显；数值越低，头部位置越稳定。"
              :value="features.head_drift_y"
              :digits="4"
            />
            <MetricRow
              label="姿态漂移"
              help="表示最近 60 秒身体上下位置的波动幅度。数值越高，身体移动越明显；数值越低，坐姿越稳定。"
              :value="features.posture_drift"
              :digits="4"
            />
            <MetricRow
              label="关键点可见度"
              help="表示系统对鼻子、双耳和双肩等关键点的识别可靠程度。数值越高，姿态数据越可信；数值过低时可能受遮挡、光线或拍摄距离影响，低于 0.40 时不宜参考。"
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
import CameraSwitcher from '@/components/CameraSwitcher/index.vue'
import useCameraStore from '@/store/modules/camera'
import { cameraQueryString } from '@/utils/camera'
import { getToken } from '@/utils/auth'

const baseURL = import.meta.env.VITE_APP_BASE_API || '/dev-api'
const cameraStore = useCameraStore()
const videoImg = ref(null)

const streamKey = ref(0)
const videoState = ref('connecting')
// Use image pixels for SVG units so text and strokes cannot cover the video.
const videoSize = ref({ width: 640, height: 480 })
const videoAspectRatio = computed(() => `${videoSize.value.width} / ${videoSize.value.height}`)
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
  fatigue_score_raw: null,
  fatigue_score: null,
  fatigue_status: '预热中',
  blink_total: 0,
  yawn_total: 0
})

const result = ref(emptyResult())

const sourceQuery = computed(() => {
  if (cameraStore.source === 'xiaozhi' && !cameraStore.xiaozhiDeviceId) return ''
  return cameraQueryString(cameraStore.cameraId)
})

const videoStreamUrl = computed(() => sourceQuery.value
  ? `${baseURL}/video/feed/raw?${sourceQuery.value}&stream=${streamKey.value}`
  : '')

const cameraLabel = computed(() => cameraStore.cameraLabel)

const lastStep = computed(() => result.value.last_step)
const features = computed(() => lastStep.value?.features || {})

function toFatigueScore(value) {
  if (value == null || value === '') return null
  const score = Number(value)
  return Number.isFinite(score) ? 1 - score : null
}

const fatigueScoreRaw = computed(() => (
  result.value.fatigue_score_raw
  ?? toFatigueScore(result.value.score_raw)
))
const fatigueScore = computed(() => (
  result.value.fatigue_score
  ?? toFatigueScore(result.value.score_ema)
))

const scoreTone = computed(() => {
  const score = fatigueScore.value
  if (score == null) return 'wait'
  if (score > 0.70) return 'fatigued'
  if (score >= 0.45) return 'drowsy'
  return 'alert'
})

const scoreStatus = computed(() => result.value.fatigue_status || {
  wait: '预热中',
  fatigued: '疲劳',
  drowsy: '困倦',
  alert: '清醒'
}[scoreTone.value])

const scoreText = computed(() => formatNumber(fatigueScore.value, 2, '--'))
const scorePercent = computed(() => {
  const score = Number(fatigueScore.value)
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
  if (!sourceQuery.value) return '等待选择小智摄像头'
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

const boxSpecs = [
  { name: 'face', label: 'face', color: '#a1e26e' },
  { name: 'left_eye', label: 'L eye', color: '#ffd17b', probability: 'p_left' },
  { name: 'right_eye', label: 'R eye', color: '#ffd17b', probability: 'p_right' },
  { name: 'mouth', label: 'mouth', color: '#ffae6a', probability: 'p_mouth' }
]

const detectionBoxes = computed(() => {
  const boxes = result.value.boxes || {}

  return boxSpecs.flatMap(spec => {
    const box = boxes[spec.name]
    if (!box) return []

    const coords = ['x1', 'y1', 'x2', 'y2'].map(key => Number(box[key]))
    if (!coords.every(Number.isFinite)) return []

    const [rawX1, rawY1, rawX2, rawY2] = coords
    const x1 = Math.max(0, Math.min(1, rawX1, rawX2))
    const y1 = Math.max(0, Math.min(1, rawY1, rawY2))
    const x2 = Math.min(1, Math.max(0, rawX1, rawX2))
    const y2 = Math.min(1, Math.max(0, rawY1, rawY2))
    if (x2 <= x1 || y2 <= y1) return []

    const probability = spec.probability
      ? Number(result.value[spec.probability])
      : null
    const isAlert = (
      spec.name === 'mouth'
        ? result.value.is_yawning
        : ['left_eye', 'right_eye'].includes(spec.name)
          && result.value.is_blinking
    )

    return [{
      ...spec,
      x1,
      y1,
      x2,
      y2,
      width: x2 - x1,
      height: y2 - y1,
      labelY: Math.max(0.026, y1 - 0.012),
      color: isAlert ? '#ff665f' : spec.color,
      label: Number.isFinite(probability)
        ? `${spec.label} ${probability.toFixed(2)}`
        : spec.label
    }]
  })
})

const poseKeypointSlots = computed(() => (
  (result.value.keypoints || []).map(point => {
    if (point?.x == null || point?.y == null) return null
    const x = Number(point.x)
    const y = Number(point.y)
    const visible = (
      Number.isFinite(x)
      && Number.isFinite(y)
      && x >= 0
      && x <= 1
      && y >= 0
      && y <= 1
    )
    return visible ? { x, y } : null
  })
))

const poseKeypoints = computed(() => (
  poseKeypointSlots.value.filter(Boolean)
))

const poseSegments = computed(() => {
  const points = poseKeypointSlots.value
  return [[0, 1], [0, 2], [0, 3], [0, 4], [3, 4]]
    .filter(([start, end]) => points[start] && points[end])
    .map(([start, end]) => ({
      x1: points[start].x,
      y1: points[start].y,
      x2: points[end].x,
      y2: points[end].y
    }))
})

function toggleDetectionBoxes() {
  showBoxes.value = !showBoxes.value
}

const authHeaders = () => ({ Authorization: `Bearer ${getToken() || ''}` })

async function requestFatigue(action, query, signal, method = 'GET') {
  const response = await fetch(`${baseURL}/fatigue/${action}?${query}`, {
    method, signal, headers: authHeaders(), cache: 'no-store'
  })
  const data = await response.json().catch(() => null)
  if (!response.ok || !data || data.ok === false) {
    throw new Error(data?.detail || data?.message || data?.msg || '疲劳检测服务返回异常')
  }
  return data
}

let pollTimer = null
let pollController = null
let resetController = null

function stopPolling() {
  clearTimeout(pollTimer)
  pollController?.abort()
  pollController = null
}

function startPolling() {
  stopPolling()
  const query = sourceQuery.value
  if (!query || resetting.value || document.hidden) return
  const controller = new AbortController()
  pollController = controller

  async function poll() {
    try {
      const data = await requestFatigue('results', query, controller.signal)
      if (controller.signal.aborted || query !== sourceQuery.value) return
      result.value = { ...emptyResult(), ...data }
      serviceError.value = ''
    } catch (error) {
      if (!controller.signal.aborted && query === sourceQuery.value) {
        result.value = emptyResult()
        serviceError.value = error.message
      }
    } finally {
      if (!controller.signal.aborted) pollTimer = setTimeout(poll, 1200)
    }
  }

  poll()
}

async function restartSession() {
  const query = sourceQuery.value
  if (!query || resetting.value) return
  stopPolling()
  const controller = new AbortController()
  resetController = controller
  resetting.value = true
  serviceError.value = ''
  try {
    await requestFatigue('reset', query, controller.signal, 'POST')
    if (controller.signal.aborted || query !== sourceQuery.value) return
    result.value = emptyResult()
    videoState.value = 'connecting'
    streamKey.value += 1
    ElMessage.success('已重新开始疲劳检测')
  } catch (error) {
    if (!controller.signal.aborted && query === sourceQuery.value) {
      serviceError.value = error.message
    }
  } finally {
    if (resetController === controller) {
      resetController = null
      resetting.value = false
      startPolling()
    }
  }
}

function onVideoLoad(event) {
  const image = event.currentTarget
  if (image !== videoImg.value) return
  videoState.value = 'online'
  videoError.value = ''
  if (image.naturalWidth && image.naturalHeight) {
    videoSize.value = { width: image.naturalWidth, height: image.naturalHeight }
  }
}

function onVideoError(event) {
  if (event.currentTarget !== videoImg.value) return
  videoState.value = 'error'
  videoError.value = '请检查摄像头连接，或在设备管理中启动小智摄像头采集'
}

function handleVisibilityChange() {
  if (document.hidden) stopPolling()
  else startPolling()
}

watch(sourceQuery, () => {
  resetController?.abort()
  resetController = null
  resetting.value = false
  result.value = emptyResult()
  serviceError.value = ''
  videoState.value = 'connecting'
  streamKey.value += 1
  startPolling()
})

onMounted(() => {
  startPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  resetController?.abort()
  resetController = null
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
.detection-overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}
.detection-overlay__box rect {
  fill: none;
  stroke-width: 2px;
  transition:
    x 120ms linear,
    y 120ms linear,
    width 120ms linear,
    height 120ms linear;
}
.detection-overlay__box text {
  font-size: 12px;
  font-weight: 700;
  paint-order: stroke;
  stroke: rgba(12, 16, 22, 0.9);
  stroke-width: 3px;
  stroke-linejoin: round;
}
.detection-overlay__line {
  stroke: #69d2ff;
  stroke-width: 2px;
}
.detection-overlay__point {
  fill: #69d2ff;
  stroke: rgba(12, 16, 22, 0.85);
  stroke-width: 1px;
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
