<template>
  <div class="app-container">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <!-- 视频名称 -->
      <el-form-item label="视频名称" prop="vidName">
        <el-input v-model="form.vidName" placeholder="请输入视频名称" clearable/>
      </el-form-item>

      <!-- 视频编码 -->
      <el-form-item label="视频编码" prop="vidSerial">
        <el-input v-model="form.vidSerial" placeholder="请输入视频编码" clearable/>
      </el-form-item>

      <!-- 视频类型 -->
      <el-form-item label="视频类型" prop="vidType">
        <el-select v-model="form.vidType" placeholder="请选择视频类型" clearable filterable style="width: 100%">
          <el-option label="hik" value="hik"/>
          <el-option label="rtsp" value="rtsp"/>
          <el-option label="rtmp" value="rtmp"/>
          <el-option label="file" value="file"/>
        </el-select>
      </el-form-item>

      <!-- 视频源 -->
      <el-form-item label="视频源" prop="vidUri">
        <el-input v-if="form.vidType!='file'" v-model="form.vidUri" placeholder="请输入视频源地址或海康监控点编号"
                  clearable/>
        <el-upload
            v-else
            :action="uploadUrl"
            :headers="getUploadHeaders()"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleFileChange"
            ref="uploadRef"
        >
          <el-button icon="el-icon-upload">选择文件</el-button>
        </el-upload>
        <div v-if="form.vidType === 'file' && form.vidUri" style="margin-top: 10px;">
          <el-tag type="success">文件已上传</el-tag>
        </div>
        <div v-else-if="form.vidType === 'file' && selectedFile" style="margin-top: 10px;">
          <el-tag>已选择文件: {{ selectedFile.name }}</el-tag>
        </div>
      </el-form-item>

      <!-- 应用场景下拉选择 -->
      <el-form-item label="应用场景" prop="vidScene">
        <el-select v-model="form.vidScene" placeholder="请选择应用场景" clearable filterable>
          <el-option
              v-for="scene in sceneList"
              :key="scene.sceneId"
              :label="scene.sceneName"
              :value="scene.sceneId"
          />
        </el-select>
      </el-form-item>

      <!-- 算法穿梭框 -->
      <el-form-item label="选择算法">
        <el-transfer
            v-model="selectedAlgorithms"
            :data="algorithmOptions"
            :titles="['可选算法', '已选算法']"
            :props="{
            key: 'algId',
            label: 'algName'
          }"
            filterable
            filter-placeholder="请输入算法名称"
            @change="handleAlgorithmChange"
        >
          <template #default="{ option }">
            <div class="transfer-item-with-button">
              <span class="item-label">{{ option.algName }}</span>
              <el-button
                  v-if="selectedAlgorithms.includes(option.algId)"
                  size="small"
                  type="primary"
                  link
                  @click.stop="configureAlgorithm(option.algId)"
                  class="config-btn"
              >
                配置
              </el-button>
              <span v-else class="config-placeholder"></span>
            </div>
          </template>
        </el-transfer>
      </el-form-item>

      <!-- 操作按钮 -->
      <el-form-item>
        <el-button type="primary" @click="submitForm">保存</el-button>
        <el-button @click="close">取消</el-button>
      </el-form-item>
    </el-form>

    <!-- 算法配置弹框 -->
    <el-dialog
        v-model="configDialogVisible"
        :title="`配置算法: ${currentAlgorithm?.algName || ''}`"
        width="70%"
    >
      <el-form :model="algorithmConfigForm" label-width="200px" style="margin-top: 20px;">
        <!-- 动态渲染配置字段 -->
        <template v-for="(value, key) in algorithmConfigForm" :key="key">
          <!-- ROI和direction字段特殊处理，不在这里显示 -->
          <template v-if="key !== 'roi' && key !== 'direction' && key !== 'line'">
            <!-- 数字类型字段 -->
            <el-form-item
                v-if="typeof value === 'number'"
                :label="getFieldLabel(key)"
            >
              <el-input-number
                  v-model="algorithmConfigForm[key]"
                  :min="getFieldMin(key)"
                  :max="getFieldMax(key)"
                  controls-position="right"
                  :placeholder="getFieldPlaceholder(key)"
              />
            </el-form-item>

            <!-- 字符串类型字段 -->
            <el-form-item
                v-else-if="typeof value === 'string'"
                :label="getFieldLabel(key)"
            >
              <el-input
                  v-model="algorithmConfigForm[key]"
                  :placeholder="getFieldPlaceholder(key)"
              />
            </el-form-item>

            <!-- 布尔类型字段 -->
            <el-form-item
                v-else-if="typeof value === 'boolean'"
                :label="getFieldLabel(key)"
            >
              <el-switch
                  v-model="algorithmConfigForm[key]"
              />
            </el-form-item>

            <!-- 分组选择 -->
            <el-form-item
                v-else-if="key === 'groups' && form.groups !== undefined"
                :label="getFieldLabel(key)"
            >
              <el-select
                  v-model="form.groups"
                  placeholder="请选择分组"
                  multiple
                  clearable
                  filterable
                  style="width: 100%"
              >
                <el-option
                    v-for="group in groupList"
                    :key="group.id"
                    :label="group.name"
                    :value="group.id"
                />
              </el-select>
            </el-form-item>

            <!-- 数组类型字段（除了ROI） -->
            <el-form-item
                v-else-if="Array.isArray(value)"
                :label="getFieldLabel(key)"
            >
              <el-input
                  v-model="algorithmConfigForm[key]"
                  :placeholder="getFieldPlaceholder(key)"
                  readonly
              />
            </el-form-item>
          </template>
        </template>

        <el-form-item label="ROI标记">
          <div class="video-preview-container">
            <div class="label-box">
              <video
                  ref="videoPlayer"
                  class="video-player"
                  autoplay
                  muted
                  style="width: 640px; height: 360px; background: #000;"
              ></video>
              <canvas
                  ref="labelBoard"
                  class="label-board"
                  @mousedown="handleMouseDown"
                  @mousemove="draw"
                  @mouseup="stopDrawing"
                  @mouseleave="stopDrawing"
                  @dblclick="completeDrawing"
              ></canvas>
            </div>
            <div class="roi-controls">
              <el-button
                  type="danger"
                  size="small"
                  @click="clearDrawing"
                  :disabled="roiPolygons.length === 0 && directionArrows.length === 0"
              >
                清空绘制
              </el-button>
              <el-button
                  v-if="algorithmConfigForm.hasOwnProperty('direction')"
                  type="primary"
                  size="small"
                  @click="toggleDirectionMode"
                  :class="{ 'active': isDirectionMode }"
              >
                {{ isDirectionMode ? '退出方向绘制' : '方向绘制' }}
              </el-button>
              <el-button
                  v-if="algorithmConfigForm.hasOwnProperty('line')"
                  type="success"
                  size="small"
                  @click="toggleLineMode"
                  :class="{ 'active': isLineMode }"
              >
                {{ isLineMode ? '退出车道线绘制' : '车道线绘制' }}
              </el-button>
              <span class="roi-tip">
                {{
                  isDirectionMode ? '点击两次绘制方向箭头' : isLineMode ? '点击画布添加点，双击完成当前线条绘制' : '点击视频区域添加点，双击完成绘制，至少需要3个点构成多边形'
                }}
              </span>
            </div>
            <div v-if="!flvUrl && previewLoading" class="video-placeholder">
              <el-button
                  type="primary"
                  size="small"
                  :loading="previewLoading"
                  disabled
              >
                正在启动视频流...
              </el-button>
            </div>
            <div v-else-if="flvUrl" class="video-status">
              <span class="status-text">正在播放: {{ flvUrl }}</span>
              <el-button
                  type="danger"
                  size="small"
                  @click="stopVideoPreview"
              >
                停止预览
              </el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="handleCancel">取消</el-button>
          <el-button type="primary" @click="saveAlgorithmConfig">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="VideoEdit">
import {ref, reactive, onMounted, getCurrentInstance, watch, onUnmounted} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {getVideo, addVideo, updateVideo, startVideoStream} from '@/api/xuzhou/video'
import {listScene} from '@/api/xuzhou/scene'
import {listAlgorithm} from '@/api/xuzhou/algorithm'
import {listGroup} from '@/api/face/group'
import {getToken} from '@/utils/auth'
import flvjs from 'flv.js'

const {proxy} = getCurrentInstance()
const route = useRoute()
const router = useRouter()

const formRef = ref()
const uploadRef = ref()

const form = reactive({
  vidId: undefined,
  vidName: '',
  vidSerial: '',
  vidType: '',
  vidUri: '',
  vidScene: undefined,
  vidAlgorithm: '',
  vidAlgorithmName: '',
  groups: []
})

// 添加一个变量来存储选择的文件
const selectedFile = ref(null)

const rules = reactive({
  vidName: [{required: true, message: '视频名称不能为空', trigger: 'blur'}],
  vidSerial: [{required: true, message: '视频编码不能为空', trigger: 'blur'}],
  vidType: [{required: true, message: '视频类型不能为空', trigger: 'blur'}],
  vidUri: [{
    required: true,
    message: '视频源不能为空',
    trigger: 'blur',
    validator: (rule, value, callback) => {
      // 如果是文件类型且已选择文件，则通过验证
      if (form.vidType === 'file' && selectedFile.value) {
        callback();
      } else if (!value) {
        callback(new Error('视频源不能为空'));
      } else {
        callback();
      }
    }
  }],
  vidScene: [{required: true, message: '请选择应用场景', trigger: 'change'}],
  groups: [{required: true, message: '请选择分组', trigger: 'change'}]
})

// 场景列表
const sceneList = ref([])
// 分组列表
const groupList = ref([])
// 所有算法选项（保留原功能）
const allAlgorithmOptions = ref([])
// 当前场景对应的算法选项
const algorithmOptions = ref([])
// 已选算法
const selectedAlgorithms = ref([])
const selectedAlgorithmsConfig = ref([])

// 配置弹框相关变量
const configDialogVisible = ref(false)
const currentAlgorithm = ref(null)
const algorithmConfigForm = reactive({})

// 视频播放相关变量
const videoPlayer = ref(null)
const flvUrl = ref('')
const previewLoading = ref(false)
const flvPlayer = ref(null)

// ROI绘制相关变量
const labelBoard = ref(null)
const isDrawing = ref(false)
const points = ref([])
const roiPolygons = ref([])

// 方向绘制相关变量
const isDirectionMode = ref(false)
const directionArrows = ref([])
const directionPoints = ref([])
const directionClickCount = ref(0)

// 车道线绘制相关变量
const isLineMode = ref(false)
const currentLinePoints = ref([])
const laneLines = ref([])
const isDrawingLine = ref(false)

// ROI绘制颜色配置
const roiColors = {
  fill: 'rgba(255, 192, 203, 0.3)',      // 粉红色填充
  fillPreview: 'rgba(255, 192, 203, 0.2)', // 粉红色预览填充
  stroke: '#ff69b4',                      // 粉红色边框
  point: '#ff69b4'                        // 粉红色点
}

// 上传相关配置
const uploadUrl = ref(import.meta.env.VITE_APP_BASE_API + '/common/upload')

/** 获取上传请求头 */
function getUploadHeaders() {
  return {
    Authorization: 'Bearer ' + getToken(),
  }
}

/** 获取场景列表 */
async function getSceneList() {
  try {
    const response = await listScene({pageNum: 1, pageSize: 1000})
    sceneList.value = response.rows || []
  } catch (error) {
    console.error('获取场景列表失败:', error)
  }
}

/** 获取分组列表 */
async function getGroupList() {
  try {
    const response = await listGroup({pageNum: 1, pageSize: 1000})
    groupList.value = response.data.rows || []
  } catch (error) {
    console.error('获取分组列表失败:', error)
  }
}

/** 获取所有算法列表（保留原功能） */
async function getAllAlgorithmList() {
  try {
    const response = await listAlgorithm({pageNum: 1, pageSize: 1000})
    allAlgorithmOptions.value = response.rows || []
  } catch (error) {
    console.error('获取算法列表失败:', error)
  }
}

/** 根据场景ID获取对应的算法列表 */
async function getSceneAlgorithms(sceneId) {
  try {
    // 这里需要根据实际API接口调整
    // 假设场景对象中有 sceneAlgorithm 字段，包含该场景对应的算法列表
    const selectedScene = sceneList.value.find(scene => scene.sceneId === sceneId)
    if (selectedScene && selectedScene.sceneAlgorithm) {
      // 假设 sceneAlgorithm 是算法ID数组，需要从所有算法中过滤出对应的算法
      algorithmOptions.value = allAlgorithmOptions.value.filter(alg =>
          selectedScene.sceneAlgorithm.includes(alg.algId)
      )
    } else {
      algorithmOptions.value = []
    }
  } catch (error) {
    console.error('获取场景算法列表失败:', error)
    algorithmOptions.value = []
  }
}

/** 提交表单 */
async function submitForm() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()

    // 如果是文件类型且有选择的文件，则先上传文件
    if (form.vidType === 'file' && selectedFile.value) {
      await uploadSelectedFile()
      // 上传完成后需要再次验证，确保vidUri已设置
      if (!form.vidUri) {
        proxy.$modal.msgError('文件上传失败，请重试')
        return
      }
    }

    // 处理算法数据
    const selectedAlgIds = selectedAlgorithms.value
    const selectedAlgNames = algorithmOptions.value
        .filter(alg => selectedAlgIds.includes(alg.algId))
        .map(alg => alg.algName)

    // 构建包含配置信息的算法数据
    const algorithmDataWithConfig = selectedAlgIds.map(algId => {
      const algorithm = algorithmOptions.value.find(alg => alg.algId === algId)
      const config = selectedAlgorithmsConfig.value.find(item => item.id === algId)

      // 获取基础配置
      let algDefaultConf = config ? config.algDefaultConf : (algorithm ? algorithm.algDefaultConf : {})

      // 将groups字段添加到算法配置中
      algDefaultConf = {
        ...algDefaultConf,
        groups: form.groups || []
      }

      return {
        algId: algId,
        algName: algorithm ? algorithm.algName : '',
        algDefaultConf: algDefaultConf
      }
    })

    // 直接传递数组对象，后端会自动序列化为JSON字符串
    form.vidAlgorithm = algorithmDataWithConfig
    form.vidAlgorithmName = selectedAlgNames

    console.log('提交的算法数据:', algorithmDataWithConfig)
    console.log('序列化后的算法数据:', form.vidAlgorithm)

    if (form.vidId) {
      // 修改视频
      await updateVideo(form)
      proxy.$modal.msgSuccess('修改成功')
    } else {
      // 新增视频
      await addVideo(form)
      proxy.$modal.msgSuccess('新增成功')
    }

    close()
  } catch (error) {
    console.error('保存失败:', error)
  }
}

/** 关闭页面 */
function close() {
  router.push('/VideoStream/VideoList')
}

/** 配置算法 */
async function configureAlgorithm(algId) {
  const algorithm = algorithmOptions.value.find(alg => alg.algId === algId)
  if (algorithm) {
    currentAlgorithm.value = algorithm

    // 清空之前的配置表单
    Object.keys(algorithmConfigForm).forEach(key => {
      delete algorithmConfigForm[key]
    })

    // 查找现有的配置信息
    const existingConfig = selectedAlgorithmsConfig.value.find(item => item.id === algId)

    let finalConfig = null

    if (existingConfig && existingConfig.algDefaultConf) {
      try {
        // 优先使用已有的配置信息
        if (typeof existingConfig.algDefaultConf === 'string') {
          finalConfig = JSON.parse(existingConfig.algDefaultConf)
        } else {
          finalConfig = existingConfig.algDefaultConf
        }
        console.log('使用已有配置:', finalConfig)
      } catch (error) {
        console.error('解析已有配置失败，尝试使用算法默认配置:', error)
        finalConfig = null
      }
    }

    // 如果没有已有配置或解析失败，使用算法默认配置
    if (!finalConfig && algorithm.algDefaultConf) {
      try {
        if (typeof algorithm.algDefaultConf === 'string') {
          finalConfig = JSON.parse(algorithm.algDefaultConf)
        } else {
          finalConfig = algorithm.algDefaultConf
        }
        console.log('使用算法默认配置:', finalConfig)
      } catch (error) {
        console.error('解析算法默认配置失败:', error)
        finalConfig = null
      }
    }

    // 如果都没有，使用系统默认配置
    if (!finalConfig) {
      finalConfig = {
        limit: 7,
        frameSkip: 1,
        roi: [0, 0, 1, 0, 1, 1, 0, 1],
        interval: 60,
        angle: 0,
        line: []
      }
      console.log('使用系统默认配置:', finalConfig)
    }

    // 动态设置表单字段
    if (finalConfig && typeof finalConfig === 'object') {
      Object.keys(finalConfig).forEach(key => {
        algorithmConfigForm[key] = finalConfig[key]
      })
    }

    // 初始化车道线绘制相关变量，避免缓存干扰
    isLineMode.value = false
    isDrawingLine.value = false
    currentLinePoints.value = []
    laneLines.value = []

    // 打开配置弹框
    configDialogVisible.value = true

    // 在弹框打开后启动视频预览（确保视频元素已挂载）
    if (form.vidType && form.vidUri) {
      // 使用 nextTick 确保弹框和视频元素已经渲染完成
      await proxy.$nextTick()
      // 初始化canvas尺寸
      if (labelBoard.value) {
        labelBoard.value.width = 640
        labelBoard.value.height = 360
      }
      await startVideoPreview()

      // 在视频预览启动后，根据ROI配置初始化绘制
      await proxy.$nextTick()
      initRoiFromConfig()
    } else {
      // 即使没有视频源，也要初始化canvas和ROI绘制
      await proxy.$nextTick()
      if (labelBoard.value) {
        labelBoard.value.width = 640
        labelBoard.value.height = 360
        // 初始化ROI绘制
        initRoiFromConfig()
      }
      proxy.$modal.msgWarning('请先填写视频类型和视频源地址')
    }
  }
}

/** 保存算法配置 */
function saveAlgorithmConfig() {
  if (!currentAlgorithm.value) return

  const algId = currentAlgorithm.value.algId
  // 动态保存所有配置字段
  const configJson = {...algorithmConfigForm}

  const index = selectedAlgorithmsConfig.value.findIndex(item => item.id === algId)

  if (index !== -1) {
    // 更新现有配置
    selectedAlgorithmsConfig.value[index].algDefaultConf = configJson
  } else {
    // 添加新配置
    selectedAlgorithmsConfig.value.push({
      id: algId,
      algDefaultConf: configJson
    })
  }
  console.log(selectedAlgorithmsConfig.value);


  // 关闭视频预览
  stopVideoPreview()

  proxy.$modal.msgSuccess('配置保存成功')
  configDialogVisible.value = false
  console.log('更新后的算法配置列表:', selectedAlgorithmsConfig.value)
}

/** 处理算法选择变化事件 */
function handleAlgorithmChange(value, direction, movedKeys) {
  console.log('算法选择变化:', {
    value: value, // 当前已选算法ID数组
    direction: direction, // 移动方向：'left' 或 'right'
    movedKeys: movedKeys // 移动的算法ID数组
  })

  if (direction === 'right') {
    // 算法被选中（移动到右侧）
    movedKeys.forEach(algId => {
      const algorithm = algorithmOptions.value.find(alg => alg.algId === algId)
      if (algorithm) {
        proxy.$modal.msgSuccess(`已选择算法: ${algorithm.algName}`)
        console.log(selectedAlgorithms.value);

        // 将算法配置信息添加到selectedAlgorithmsConfig中
        const configItem = {
          id: algorithm.algId,
          algDefaultConf: algorithm.algDefaultConf
        }
        selectedAlgorithmsConfig.value.push(configItem)
        console.log('已添加算法配置:', configItem)
      }
    })
  } else if (direction === 'left') {
    // 算法被取消选中（移动到左侧）
    movedKeys.forEach(algId => {
      const algorithm = algorithmOptions.value.find(alg => alg.algId === algId)
      if (algorithm) {
        proxy.$modal.msgSuccess(`已取消选择算法: ${algorithm.algName}`)

        // 从selectedAlgorithmsConfig中移除对应的配置信息
        const index = selectedAlgorithmsConfig.value.findIndex(item => item.id === algId)
        if (index !== -1) {
          selectedAlgorithmsConfig.value.splice(index, 1)
          console.log('已移除算法配置:', algId)
        }
      }
    })
  }

  console.log('当前算法配置列表:', selectedAlgorithmsConfig.value)
}

/** 获取视频详情 */
async function getVideoDetail(vidId) {
  try {
    const response = await getVideo(vidId)
    Object.assign(form, response.data)

    console.log('从后端获取的视频数据:', response.data)

    // 先加载场景对应的算法选项
    if (form.vidScene) {
      await getSceneAlgorithms(form.vidScene)
    }

    // 处理已选算法
    if (form.vidAlgorithm) {
      try {
        let algorithmData
        // 检查是否已经是对象数组（后端已解析）
        if (Array.isArray(form.vidAlgorithm)) {
          algorithmData = form.vidAlgorithm
        } else if (typeof form.vidAlgorithm === 'string') {
          // 尝试解析JSON格式的算法数据
          algorithmData = JSON.parse(form.vidAlgorithm)
        }

        if (Array.isArray(algorithmData)) {
          // 新格式：包含配置信息的数组
          selectedAlgorithms.value = algorithmData.map(item => item.algId)
          selectedAlgorithmsConfig.value = algorithmData.map(item => ({
            id: item.algId,
            algDefaultConf: item.algDefaultConf
          }))

          // 从算法配置中提取groups数据并设置到form.groups
          if (algorithmData.length > 0 && algorithmData[0].algDefaultConf && algorithmData[0].algDefaultConf.groups) {
            form.groups = algorithmData[0].algDefaultConf.groups
            console.log('从算法配置中加载的groups数据:', form.groups)
          }

          // 如果场景算法选项中没有包含已选算法，则从所有算法中补充
          const missingAlgorithms = algorithmData.filter(item =>
              !algorithmOptions.value.some(opt => opt.algId === item.algId)
          )

          if (missingAlgorithms.length > 0) {
            // 从所有算法选项中找到缺失的算法并添加到当前选项中
            const additionalAlgorithms = allAlgorithmOptions.value.filter(alg =>
                missingAlgorithms.some(missing => missing.algId === alg.algId)
            )
            algorithmOptions.value = [...algorithmOptions.value, ...additionalAlgorithms]
          }

          console.log('从数据库加载的算法ID列表:', selectedAlgorithms.value)
          console.log('从数据库加载的算法配置列表:', selectedAlgorithmsConfig.value)
          console.log('当前算法选项列表:', algorithmOptions.value)
        } else {
          // 兼容旧格式：逗号分隔的ID字符串
          if (typeof form.vidAlgorithm === 'string') {
            selectedAlgorithms.value = form.vidAlgorithm.split(',').map(id => parseInt(id)).filter(id => !isNaN(id))

            // 为旧格式数据补充算法选项
            const missingAlgorithms = selectedAlgorithms.value.filter(algId =>
                !algorithmOptions.value.some(opt => opt.algId === algId)
            )

            if (missingAlgorithms.length > 0) {
              const additionalAlgorithms = allAlgorithmOptions.value.filter(alg =>
                  missingAlgorithms.includes(alg.algId)
              )
              algorithmOptions.value = [...algorithmOptions.value, ...additionalAlgorithms]
            }
          }
        }
      } catch (error) {
        console.error('解析算法数据失败:', error)
        // 解析失败时尝试按旧格式处理
        if (typeof form.vidAlgorithm === 'string') {
          selectedAlgorithms.value = form.vidAlgorithm.split(',').map(id => parseInt(id)).filter(id => !isNaN(id))
        }
      }
    }

    // 处理算法名称
    if (form.vidAlgorithmName) {
      try {
        let algorithmNames
        // 检查是否已经是字符串数组（后端已解析）
        if (Array.isArray(form.vidAlgorithmName)) {
          algorithmNames = form.vidAlgorithmName
        } else if (typeof form.vidAlgorithmName === 'string') {
          // 尝试解析JSON格式的算法名称数据
          algorithmNames = JSON.parse(form.vidAlgorithmName)
        }

        if (Array.isArray(algorithmNames)) {
          console.log('从数据库加载的算法名称列表:', algorithmNames)
        }
      } catch (error) {
        console.error('解析算法名称数据失败:', error)
      }
    }

    console.log('最终设置的已选算法ID列表:', selectedAlgorithms.value)
  } catch (error) {
    console.error('获取视频详情失败:', error)
  }
}

// 监听场景变化
watch(() => form.vidScene, (newSceneId) => {
  if (newSceneId) {
    getSceneAlgorithms(newSceneId)
    // 同步更新场景名称
    const selectedScene = sceneList.value.find(scene => scene.sceneId === newSceneId)
    if (selectedScene) {
      form.vidSceneName = selectedScene.sceneName
    }
  } else {
    algorithmOptions.value = []
    form.vidSceneName = ''
  }
  // 切换场景时清空已选算法和配置
  selectedAlgorithms.value = []
  selectedAlgorithmsConfig.value = []
})

// 监听视频类型变化，重置文件选择和视频源
watch(() => form.vidType, (newType, oldType) => {
  // 如果从文件类型切换到其他类型，清空已选择的文件
  if (oldType === 'file' && newType !== 'file') {
    selectedFile.value = null
  }
  // 如果切换到文件类型，清除可能存在的错误提示
  else if (newType === 'file') {
    selectedFile.value = null
    form.vidUri = ''
  }
})

// 初始化数据
onMounted(async () => {
  await getSceneList()
  await getGroupList()
  await getAllAlgorithmList()

  const vidId = route.query.vidId
  const storageKey = route.query.storageKey

  if (storageKey) {
    // 如果有存储键，从sessionStorage获取数据
    try {
      const storedData = sessionStorage.getItem(storageKey)
      if (storedData) {
        const rowData = JSON.parse(storedData)
        Object.assign(form, rowData)

        // 如果有场景ID，先加载对应的算法列表
        if (form.vidScene) {
          await getSceneAlgorithms(form.vidScene)
        }

        // 处理已选算法（在加载算法列表后）
        if (form.vidAlgorithm) {
          try {
            let algorithms = []

            // 兼容新旧数据格式
            if (typeof form.vidAlgorithm === 'string') {
              try {
                algorithms = JSON.parse(form.vidAlgorithm)
              } catch {
                algorithms = form.vidAlgorithm.split(',').map(id => parseInt(id))
              }
            } else if (Array.isArray(form.vidAlgorithm)) {
              algorithms = form.vidAlgorithm
            }

            if (algorithms.length > 0) {
              selectedAlgorithms.value = algorithms.map(alg =>
                  typeof alg === 'object' ? alg.algId : parseInt(alg)
              )

              // 初始化算法配置信息
              selectedAlgorithmsConfig.value = selectedAlgorithms.value.map(algId => {
                const algorithm = algorithmOptions.value.find(alg => alg.algId === algId)
                if (!algorithm) return null

                // 查找原始数据中是否有该算法的配置信息
                let existingConfig = null
                if (Array.isArray(algorithms)) {
                  const originalAlg = algorithms.find(alg =>
                      (typeof alg === 'object' ? alg.algId : parseInt(alg)) === algId
                  )
                  if (originalAlg && typeof originalAlg === 'object' && originalAlg.algDefaultConf) {
                    existingConfig = originalAlg.algDefaultConf
                  }
                }

                return {
                  id: algorithm.algId,
                  // 优先使用原始数据中的配置，如果没有则使用算法选项的默认配置
                  algDefaultConf: existingConfig || algorithm.algDefaultConf
                }
              }).filter(Boolean)

              // 从算法配置中提取groups数据并设置到form.groups
              if (selectedAlgorithmsConfig.value.length > 0 && selectedAlgorithmsConfig.value[0].algDefaultConf && selectedAlgorithmsConfig.value[0].algDefaultConf.groups) {
                form.groups = selectedAlgorithmsConfig.value[0].algDefaultConf.groups
                console.log('从sessionStorage算法配置中加载的groups数据:', form.groups)
              }

              console.log('从sessionStorage初始化已选算法:', selectedAlgorithms.value)
              console.log('从sessionStorage初始化算法配置列表:', selectedAlgorithmsConfig.value)
            }
          } catch (error) {
            console.error('解析已选算法数据失败:', error)
          }
        }

        // 使用后清理存储
        sessionStorage.removeItem(storageKey)
      } else {
        // 存储数据不存在，回退到API调用
        if (vidId) {
          // await getVideoDetail(vidId)
        }
      }
    } catch (error) {
      console.error('解析存储的数据失败:', error)
      // 解析失败时回退到API调用
      if (vidId) {
        // await getVideoDetail(vidId)
      }
    }
  } else if (vidId) {
    // 如果没有存储键，按原逻辑从API获取
    await getVideoDetail(vidId)
    // getVideoDetail函数中已经处理了场景算法的加载
  }
})

/** 启动视频预览 */
async function startVideoPreview() {
  if (!form.vidType || !form.vidUri) {
    proxy.$modal.msgError('请先填写视频类型和视频源地址')
    return
  }

  previewLoading.value = true
  try {
    // 调用后端API启动推流
    const response = await startVideoStream({
      vid_type: form.vidType,
      vid_uri: form.vidUri,
      flag: `preview_${Date.now()}` // 使用时间戳作为唯一标识
    })

    if (response.code === 200) {
      const url = response.data.flv_url
      flvUrl.value = url

      // 使用flv.js播放视频流
      if (flvjs.isSupported()) {
        if (flvPlayer.value) {
          flvPlayer.value.destroy()
        }

        const videoElement = videoPlayer.value
        // 确保视频元素存在
        if (!videoElement) {
          proxy.$modal.msgError('视频元素未找到，请刷新页面重试')
          return
        }

        flvPlayer.value = flvjs.createPlayer({
          type: 'flv',
          url: url
        })
        flvPlayer.value.attachMediaElement(videoElement)
        flvPlayer.value.load()
        flvPlayer.value.play()

        proxy.$modal.msgSuccess('视频预览已启动')
      } else {
        proxy.$modal.msgError('当前浏览器不支持FLV播放')
      }
    } else {
      proxy.$modal.msgError(response.msg || '启动视频预览失败')
    }
  } catch (error) {
    console.error('启动视频预览失败:', error)
    proxy.$modal.msgError('启动视频预览失败')
  } finally {
    previewLoading.value = false
  }
}

/** 停止视频预览 */
function stopVideoPreview() {
  if (flvPlayer.value) {
    flvPlayer.value.pause()
    flvPlayer.value.destroy()
    flvPlayer.value = null
  }
  flvUrl.value = ''
  proxy.$modal.msgSuccess('视频预览已停止')
}

/** 处理取消按钮点击 */
function handleCancel() {
  // 关闭视频预览
  stopVideoPreview()
  // 关闭弹框
  configDialogVisible.value = false
}

// 双击检测相关变量
let lastClickTime = 0
let clickTimeout = null

/** 处理鼠标按下事件 */
function handleMouseDown(event) {
  if (!labelBoard.value) return

  const rect = labelBoard.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  // 左键点击
  if (event.button === 0) {
    const currentTime = Date.now()
    const timeDiff = currentTime - lastClickTime

    // 检测双击（300ms内的两次点击）
    if (timeDiff < 300 && isLineMode.value && isDrawingLine.value) {
      // 双击完成车道线绘制
      if (clickTimeout) {
        clearTimeout(clickTimeout)
        clickTimeout = null
      }
      completeLaneLine()
      return
    }

    lastClickTime = currentTime

    // 延迟处理单击，避免双击时触发单击
    if (clickTimeout) {
      clearTimeout(clickTimeout)
    }

    clickTimeout = setTimeout(() => {
      if (isDirectionMode.value) {
        // 方向绘制模式
        handleDirectionClick(x, y)
      } else if (isLineMode.value) {
        // 车道线绘制模式
        handleLineClick(x, y)
      } else {
        // ROI绘制模式
        // 添加点到points数组
        points.value.push({x, y})

        // 绘制
        const ctx = labelBoard.value.getContext('2d')
        ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

        // 绘制所有已存在的多边形
        roiPolygons.value.forEach(polygon => {
          drawPolygon(ctx, polygon, roiColors.fill)
        })

        // 绘制所有方向箭头
        directionArrows.value.forEach(arrow => {
          drawArrow(ctx, arrow.start, arrow.end)
        })


        // 绘制当前点
        drawPoints(ctx, points.value)

        // 如果点数足够，绘制预览区域
        if (points.value.length >= 3) {
          drawPolygon(ctx, points.value, roiColors.fillPreview)
        }
      }
      clickTimeout = null
    }, 100) // 100ms延迟处理单击
  }
}

/** 完成绘制 */
function completeDrawing() {
  if (!labelBoard.value || points.value.length < 3) return

  // 完成一个多边形，添加到roiPolygons
  roiPolygons.value.push([...points.value])

  // 更新ROI配置
  updateRoiConfig()

  // 清空当前点
  points.value = []

  // 重新绘制
  const ctx = labelBoard.value.getContext('2d')
  ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

  // 绘制所有多边形
  roiPolygons.value.forEach(polygon => {
    drawPolygon(ctx, polygon, roiColors.fill)
  })

  proxy.$modal.msgSuccess('区域绘制完成')
}

/** 绘制 */
function draw(event) {
  if (!labelBoard.value) return

  const rect = labelBoard.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  // 绘制
  const ctx = labelBoard.value.getContext('2d')
  ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

  // 绘制所有已存在的多边形
  roiPolygons.value.forEach(polygon => {
    drawPolygon(ctx, polygon, roiColors.fill)
  })

  // 绘制所有方向箭头
  directionArrows.value.forEach(arrow => {
    drawArrow(ctx, arrow.start, arrow.end)
  })

  // 绘制所有车道线
  laneLines.value.forEach(line => {
    drawLaneLine(line)
  })

  if (isDirectionMode.value) {
    // 方向绘制模式
    if (directionPoints.value.length === 1) {
      // 绘制起点
      ctx.beginPath()
      ctx.arc(directionPoints.value[0].x, directionPoints.value[0].y, 4, 0, Math.PI * 2)
      ctx.fillStyle = '#409eff'
      ctx.fill()

      // 绘制预览箭头
      drawArrowPreview(ctx, directionPoints.value[0], {x, y})
    }
  } else if (isLineMode.value) {
    // 车道线绘制模式
    if (isDrawingLine.value && currentLinePoints.value.length > 0) {
      // 绘制当前正在绘制的线条
      drawCurrentLine()

      // 绘制预览线段（从最后一个点到鼠标位置）
      ctx.beginPath()
      ctx.moveTo(currentLinePoints.value[currentLinePoints.value.length - 1].x, currentLinePoints.value[currentLinePoints.value.length - 1].y)
      ctx.lineTo(x, y)
      ctx.strokeStyle = '#00ff00'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      ctx.stroke()
      ctx.setLineDash([])
    }
  } else {
    // ROI绘制模式
    // 绘制当前点
    drawPoints(ctx, points.value)

    // 如果鼠标移动且有至少1个点，绘制预览线
    if (points.value.length >= 1) {
      ctx.beginPath()
      ctx.moveTo(points.value[points.value.length - 1].x, points.value[points.value.length - 1].y)
      ctx.lineTo(x, y)
      ctx.strokeStyle = roiColors.stroke
      ctx.lineWidth = 1
      ctx.stroke()
    }

    // 如果点数足够，绘制预览区域
    if (points.value.length >= 2) {
      const previewPoints = [...points.value, {x, y}]
      drawPolygon(ctx, previewPoints, roiColors.fillPreview, false)
    }
  }
}

/** 停止绘制 */
function stopDrawing() {
  // 不需要做特殊处理，点击事件已经在startDrawing中处理
}

/** 绘制点 */
function drawPoints(ctx, points) {
  points.forEach((point, index) => {
    ctx.beginPath()
    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2)
    ctx.fillStyle = roiColors.point
    ctx.fill()

    // 绘制点编号
    ctx.fillStyle = '#ffffff'
    ctx.font = '12px Arial'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText((index + 1).toString(), point.x, point.y)
  })
}

/** 绘制多边形 */
function drawPolygon(ctx, polygon, fillStyle) {
  if (polygon.length < 3) return

  ctx.beginPath()
  ctx.moveTo(polygon[0].x, polygon[0].y)
  for (let i = 1; i < polygon.length; i++) {
    ctx.lineTo(polygon[i].x, polygon[i].y)
  }
  ctx.closePath()

  ctx.fillStyle = fillStyle
  ctx.fill()
  ctx.strokeStyle = roiColors.stroke
  ctx.lineWidth = 2
  ctx.stroke()
}

/** 更新ROI配置 */
function updateRoiConfig() {
  if (roiPolygons.value.length === 0 || !labelBoard.value) {
    algorithmConfigForm.roi = [0, 0, 1, 0, 1, 1, 0, 1]
    return
  }

  // 只取第一个多边形的坐标（可以根据需要扩展为支持多个多边形）
  const polygon = roiPolygons.value[0]
  const roiPoints = []

  polygon.forEach(point => {
    // 转换为相对坐标（0-1范围）
    const relX = point.x / labelBoard.value.width
    const relY = point.y / labelBoard.value.height
    roiPoints.push(relX, relY)
  })

  algorithmConfigForm.roi = roiPoints
}

/** 根据ROI配置初始化绘制 */
function initRoiFromConfig() {
  if (!labelBoard.value) {
    return
  }

  // 每次都先清空现有绘制，确保ROI独立性
  roiPolygons.value = []
  points.value = []
  directionArrows.value = []
  directionPoints.value = []
  directionClickCount.value = 0
  const ctx = labelBoard.value.getContext('2d')
  ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

  // 初始化ROI配置
  if (algorithmConfigForm.roi && algorithmConfigForm.roi.length >= 6) {
    // 检查是否为默认值（全屏矩形），如果是则不绘制
    const defaultRoi = [0, 0, 1, 0, 1, 1, 0, 1]
    const isDefaultRoi = algorithmConfigForm.roi.length === defaultRoi.length &&
        algorithmConfigForm.roi.every((val, index) => Math.abs(val - defaultRoi[index]) < 0.001)

    if (!isDefaultRoi) {
      // 将相对坐标转换为绝对坐标
      const polygon = []
      for (let i = 0; i < algorithmConfigForm.roi.length; i += 2) {
        if (i + 1 < algorithmConfigForm.roi.length) {
          const x = algorithmConfigForm.roi[i] * labelBoard.value.width
          const y = algorithmConfigForm.roi[i + 1] * labelBoard.value.height
          polygon.push({x, y})
        }
      }

      if (polygon.length >= 3) {
        // 添加当前算法的ROI多边形
        roiPolygons.value.push(polygon)

        // 绘制到canvas
        drawPolygon(ctx, polygon, roiColors.fill)

        console.log('已根据当前算法ROI配置初始化绘制区域:', polygon)
      }
    }
  }

  // 初始化direction配置
  if (algorithmConfigForm.hasOwnProperty('direction') &&
      algorithmConfigForm.direction &&
      algorithmConfigForm.direction.length >= 4) {

    // 将相对坐标转换为绝对坐标并创建箭头
    for (let i = 0; i < algorithmConfigForm.direction.length; i += 4) {
      if (i + 3 < algorithmConfigForm.direction.length) {
        const startX = algorithmConfigForm.direction[i] * labelBoard.value.width
        const startY = algorithmConfigForm.direction[i + 1] * labelBoard.value.height
        const endX = algorithmConfigForm.direction[i + 2] * labelBoard.value.width
        const endY = algorithmConfigForm.direction[i + 3] * labelBoard.value.height

        const arrow = {
          start: {x: startX, y: startY},
          end: {x: endX, y: endY}
        }

        directionArrows.value.push(arrow)

        // 绘制箭头
        drawArrow(ctx, arrow.start, arrow.end)
      }
    }

    if (directionArrows.value.length > 0) {
      console.log('已根据当前算法direction配置初始化方向箭头:', directionArrows.value)
    }
  }

  // 初始化车道线配置
  if (algorithmConfigForm.hasOwnProperty('line') &&
      algorithmConfigForm.line &&
      algorithmConfigForm.line.length > 0) {

    // 清空现有车道线
    laneLines.value = []

    // 将相对坐标转换为绝对坐标并创建车道线
    algorithmConfigForm.line.forEach(lineData => {
      if (lineData && lineData.length >= 2) {
        const absolutePoints = lineData.map(point => ({
          x: point[0] * labelBoard.value.width,
          y: point[1] * labelBoard.value.height
        }))

        laneLines.value.push(absolutePoints)

        // 绘制车道线
        drawLaneLine(absolutePoints)
      }
    })

    if (laneLines.value.length > 0) {
      console.log('已根据当前算法line配置初始化车道线:', laneLines.value)
    }
  }
}

/** 清空所有绘制 */
function clearDrawing() {
  if (!labelBoard.value) return

  const ctx = labelBoard.value.getContext('2d')
  ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

  points.value = []
  roiPolygons.value = []
  directionArrows.value = []
  directionPoints.value = []
  directionClickCount.value = 0
  algorithmConfigForm.roi = [0, 0, 1, 0, 1, 1, 0, 1]

  // 清空direction配置
  if (algorithmConfigForm.hasOwnProperty('direction')) {
    algorithmConfigForm.direction = []
  }

  // 清空车道线配置
  if (algorithmConfigForm.hasOwnProperty('line')) {
    algorithmConfigForm.line = []
  }
  laneLines.value = []
  currentLinePoints.value = []
  isDrawingLine.value = false

  proxy.$modal.msgSuccess('已清空所有绘制区域')
}

/** 切换方向绘制模式 */
function toggleDirectionMode() {
  isDirectionMode.value = !isDirectionMode.value
  directionPoints.value = []
  directionClickCount.value = 0

  if (isDirectionMode.value) {
    // 开始绘制方向时自动删除历史方向
    directionArrows.value = []
    if (algorithmConfigForm.hasOwnProperty('direction')) {
      algorithmConfigForm.direction = []
    }
    // 重新绘制画布
    redrawCanvas()
    proxy.$modal.msgInfo('已进入方向绘制模式，请点击两次绘制方向箭头')
  } else {
    proxy.$modal.msgInfo('已退出方向绘制模式')
  }
}

/** 处理方向绘制点击 */
function handleDirectionClick(x, y) {
  directionClickCount.value++

  if (directionClickCount.value === 1) {
    // 第一次点击，记录起点
    directionPoints.value = [{x, y}]

    // 重新绘制所有内容
    const ctx = labelBoard.value.getContext('2d')
    ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

    // 绘制所有已存在的多边形
    roiPolygons.value.forEach(polygon => {
      drawPolygon(ctx, polygon, roiColors.fill)
    })

    // 绘制所有方向箭头
    directionArrows.value.forEach(arrow => {
      drawArrow(ctx, arrow.start, arrow.end)
    })

    // 绘制起点
    ctx.beginPath()
    ctx.arc(x, y, 4, 0, Math.PI * 2)
    ctx.fillStyle = '#409eff'
    ctx.fill()

  } else if (directionClickCount.value === 2) {
    // 第二次点击，记录终点并绘制箭头
    const startPoint = directionPoints.value[0]
    const endPoint = {x, y}

    // 添加到箭头数组
    directionArrows.value.push({
      start: startPoint,
      end: endPoint
    })

    // 更新direction配置
    updateDirectionConfig()

    // 重新绘制所有内容
    const ctx = labelBoard.value.getContext('2d')
    ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

    // 绘制所有已存在的多边形
    roiPolygons.value.forEach(polygon => {
      drawPolygon(ctx, polygon, roiColors.fill)
    })

    // 绘制所有方向箭头
    directionArrows.value.forEach(arrow => {
      drawArrow(ctx, arrow.start, arrow.end)
    })

    // 重置计数器和点数组
    directionClickCount.value = 0
    directionPoints.value = []

    // 绘制完成后自动退出方向绘制模式
    isDirectionMode.value = false

    // 重新绘制所有内容
    redrawCanvas()

    proxy.$modal.msgSuccess('方向箭头绘制完成，已自动退出方向绘制模式')
  }
}

/** 绘制箭头 */
function drawArrow(ctx, start, end) {
  const headLength = 15 // 箭头头部长度
  const headAngle = Math.PI / 6 // 箭头头部角度

  // 计算箭头角度
  const angle = Math.atan2(end.y - start.y, end.x - start.x)

  // 绘制箭头主体
  ctx.beginPath()
  ctx.moveTo(start.x, start.y)
  ctx.lineTo(end.x, end.y)
  ctx.strokeStyle = '#409eff'
  ctx.lineWidth = 3
  ctx.stroke()

  // 绘制箭头头部
  ctx.beginPath()
  ctx.moveTo(end.x, end.y)
  ctx.lineTo(
      end.x - headLength * Math.cos(angle - headAngle),
      end.y - headLength * Math.sin(angle - headAngle)
  )
  ctx.moveTo(end.x, end.y)
  ctx.lineTo(
      end.x - headLength * Math.cos(angle + headAngle),
      end.y - headLength * Math.sin(angle + headAngle)
  )
  ctx.strokeStyle = '#409eff'
  ctx.lineWidth = 3
  ctx.stroke()
}

/** 绘制预览箭头 */
function drawArrowPreview(ctx, start, end) {
  const headLength = 15 // 箭头头部长度
  const headAngle = Math.PI / 6 // 箭头头部角度

  // 计算箭头角度
  const angle = Math.atan2(end.y - start.y, end.x - start.x)

  // 绘制箭头主体（虚线）
  ctx.beginPath()
  ctx.setLineDash([5, 5]) // 设置虚线
  ctx.moveTo(start.x, start.y)
  ctx.lineTo(end.x, end.y)
  ctx.strokeStyle = '#409eff'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.setLineDash([]) // 重置虚线

  // 绘制箭头头部
  ctx.beginPath()
  ctx.moveTo(end.x, end.y)
  ctx.lineTo(
      end.x - headLength * Math.cos(angle - headAngle),
      end.y - headLength * Math.sin(angle - headAngle)
  )
  ctx.moveTo(end.x, end.y)
  ctx.lineTo(
      end.x - headLength * Math.cos(angle + headAngle),
      end.y - headLength * Math.sin(angle + headAngle)
  )
  ctx.strokeStyle = '#409eff'
  ctx.lineWidth = 2
  ctx.stroke()
}

/** 更新direction配置 */
function updateDirectionConfig() {
  if (!algorithmConfigForm.hasOwnProperty('direction') || !labelBoard.value) {
    return
  }

  const directionData = []

  directionArrows.value.forEach(arrow => {
    // 转换为相对坐标（0-1范围）
    const startX = arrow.start.x / labelBoard.value.width
    const startY = arrow.start.y / labelBoard.value.height
    const endX = arrow.end.x / labelBoard.value.width
    const endY = arrow.end.y / labelBoard.value.height

    directionData.push(startX, startY, endX, endY)
  })

  algorithmConfigForm.direction = directionData
}

/** 重新绘制画布 */
function redrawCanvas() {
  if (!labelBoard.value) return

  const ctx = labelBoard.value.getContext('2d')
  ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)

  // 绘制所有已存在的多边形
  roiPolygons.value.forEach(polygon => {
    drawPolygon(ctx, polygon, roiColors.fill)
  })

  // 绘制所有方向箭头
  directionArrows.value.forEach(arrow => {
    drawArrow(ctx, arrow.start, arrow.end)
  })

  // 绘制所有车道线
  laneLines.value.forEach(line => {
    drawLaneLine(line)
  })
}

/** 切换车道线绘制模式 */
function toggleLineMode() {
  isLineMode.value = !isLineMode.value

  if (isLineMode.value) {
    // 进入车道线绘制模式时，退出其他模式
    isDirectionMode.value = false

    // 清空当前绘制状态
    currentLinePoints.value = []
    isDrawingLine.value = false

    proxy.$modal.msgInfo('已进入车道线绘制模式，点击画布添加点，双击完成当前线条绘制')
  } else {
    // 退出车道线绘制模式
    if (isDrawingLine.value && currentLinePoints.value.length > 0) {
      // 如果正在绘制，完成当前线条
      completeLaneLine()
    }
    proxy.$modal.msgInfo('已退出车道线绘制模式')
  }
}

/** 处理车道线绘制点击 */
function handleLineClick(x, y) {
  // 添加点到当前线条
  currentLinePoints.value.push({x, y})
  isDrawingLine.value = true

  // 重新绘制画布
  redrawCanvas()

  // 绘制当前正在绘制的线条
  if (currentLinePoints.value.length > 1) {
    drawCurrentLine()
  }

  // 绘制当前点
  const ctx = labelBoard.value.getContext('2d')
  ctx.beginPath()
  ctx.arc(x, y, 4, 0, 2 * Math.PI)
  ctx.fillStyle = '#00ff00'
  ctx.fill()
}

/** 绘制当前正在绘制的线条 */
function drawCurrentLine() {
  const canvas = labelBoard.value
  if (!canvas || currentLinePoints.value.length < 2) return

  const ctx = canvas.getContext('2d')
  ctx.beginPath()
  ctx.moveTo(currentLinePoints.value[0].x, currentLinePoints.value[0].y)

  for (let i = 1; i < currentLinePoints.value.length; i++) {
    ctx.lineTo(currentLinePoints.value[i].x, currentLinePoints.value[i].y)
  }

  ctx.strokeStyle = '#00ff00'
  ctx.lineWidth = 3
  ctx.stroke()
}

/** 绘制车道线 */
function drawLaneLine(linePoints) {
  const canvas = labelBoard.value
  if (!canvas || !linePoints || linePoints.length < 2) return

  const ctx = canvas.getContext('2d')
  ctx.beginPath()
  ctx.moveTo(linePoints[0].x, linePoints[0].y)

  for (let i = 1; i < linePoints.length; i++) {
    ctx.lineTo(linePoints[i].x, linePoints[i].y)
  }

  ctx.strokeStyle = '#ffff00'
  ctx.lineWidth = 3
  ctx.stroke()

  // 绘制线条上的点
  linePoints.forEach(point => {
    ctx.beginPath()
    ctx.arc(point.x, point.y, 3, 0, 2 * Math.PI)
    ctx.fillStyle = '#ffff00'
    ctx.fill()
  })
}

/** 完成当前车道线绘制 */
function completeLaneLine() {
  if (currentLinePoints.value.length >= 2) {
    // 将当前线条添加到车道线数组
    laneLines.value.push([...currentLinePoints.value])

    // 更新配置
    updateLineConfig()

    proxy.$modal.msgSuccess(`车道线绘制完成，共${currentLinePoints.value.length}个点`)
  }

  // 清空当前绘制状态
  currentLinePoints.value = []
  isDrawingLine.value = false

  // 重新绘制画布
  redrawCanvas()
}

/** 更新车道线配置 */
function updateLineConfig() {
  const canvas = labelBoard.value
  if (!canvas) return

  // 将像素坐标转换为相对坐标
  const relativeLines = laneLines.value.map(line =>
      line.map(point => [
        point.x / canvas.width,
        point.y / canvas.height
      ])
  )

  algorithmConfigForm.line = relativeLines
  console.log('更新车道线配置:', relativeLines)
}

/** 上传前检查 */
function beforeUpload(file) {
  console.log(file)
  // 检查文件类型
  const allowedTypes = ['video/x-msvideo', 'video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/mkv']
  const maxSize = 100 * 1024 * 1024 // 100MB

  if (!allowedTypes.includes(file.type)) {
    proxy.$modal.msgError('请上传视频文件格式 (mp4, avi, mov, wmv, flv, mkv)')
    return false
  }

  if (file.size > maxSize) {
    proxy.$modal.msgError('文件大小不能超过100MB')
    return false
  }

  return true
}

/** 处理文件选择变化 */
function handleFileChange(file, fileList) {
  if (fileList.length > 0) {
    const selected = fileList[0].raw
    // 检查文件是否合法
    if (beforeUpload(selected)) {
      selectedFile.value = selected
    } else {
      // 文件不合法，清空已选择的文件
      selectedFile.value = null
      form.vidUri = ''
      // 清空上传组件中的文件列表
      if (uploadRef.value) {
        uploadRef.value.clearFiles()
      }
    }
  } else {
    selectedFile.value = null
    form.vidUri = ''
  }
}

/** 上传选定的文件 */
function uploadSelectedFile() {
  return new Promise((resolve, reject) => {
    if (!selectedFile.value) {
      resolve()
      return
    }

    const formData = new FormData()
    formData.append('file', selectedFile.value)

    // 创建XMLHttpRequest对象
    const xhr = new XMLHttpRequest()

    // 设置请求完成的回调
    xhr.onload = function () {
      if (xhr.status === 200) {
        try {
          const response = JSON.parse(xhr.responseText)
          if (response.code === 200) {
            form.vidUri = response.path
            proxy.$modal.msgSuccess('文件上传成功')
            resolve()
          } else {
            proxy.$modal.msgError(response.msg || '上传失败')
            reject(new Error(response.msg || '上传失败'))
          }
        } catch (e) {
          proxy.$modal.msgError('上传失败')
          reject(e)
        }
      } else {
        proxy.$modal.msgError('上传失败')
        reject(new Error('上传失败'))
      }
    }

    xhr.onerror = function () {
      proxy.$modal.msgError('上传失败')
      reject(new Error('上传失败'))
    }

    // 发送请求
    xhr.open('POST', uploadUrl.value, true)
    xhr.setRequestHeader('Authorization', 'Bearer ' + getToken())
    xhr.send(formData)
  })
}

/** 上传成功处理 */
function handleUploadSuccess(response, file, fileList) {
  if (response.code === 200) {
    // 将返回的文件路径设置为视频源
    form.vidUri = response.path
    console.log(form.vidUri)
    proxy.$modal.msgSuccess('文件上传成功')
  } else {
    proxy.$modal.msgError(response.msg || '上传失败')
  }
}

/** 上传失败处理 */
function handleUploadError(error, file, fileList) {
  proxy.$modal.msgError('文件上传失败')
  console.error('上传失败:', error)
}

/** 获取字段标签 */
function getFieldLabel(key) {
  const labelMap = {
    limit: '最小推送间隔（秒）',
    frameSkip: '跳帧',
    interval: '预警时间（秒）',
    count: '数量上限',
    threshold: '阈值',
    confidence: '置信度',
    minSize: '最小尺寸',
    maxSize: '最大尺寸',
    sensitivity: '敏感度',
    duration: '持续时间（秒）',
    speed: '速度阈值',
    area: '区域面积',
    ratio: '比例',
    enabled: '启用',
    debug: '调试模式',
    direction: '方向标记',
    angle: '角度（度）',
    line: '车道线',
    groups: '分组'
  }
  return labelMap[key] || key
}

/** 获取字段最小值 */
function getFieldMin(key) {
  const minMap = {
    limit: 1,
    frameSkip: 1,
    interval: 1,
    count: 1,
    threshold: 0,
    confidence: 0,
    minSize: 1,
    maxSize: 1,
    sensitivity: 0,
    duration: 1,
    speed: 0,
    area: 0,
    ratio: 0
  }
  return minMap[key] || 0
}

/** 获取字段最大值 */
function getFieldMax(key) {
  const maxMap = {
    limit: 100,
    frameSkip: 50,
    interval: 3600,
    count: 100,
    threshold: 1,
    confidence: 1,
    minSize: 1000,
    maxSize: 10000,
    sensitivity: 10,
    duration: 3600,
    speed: 1000,
    area: 10000,
    ratio: 10
  }
  return maxMap[key] || 100
}

/** 获取字段占位符 */
function getFieldPlaceholder(key) {
  const placeholderMap = {
    limit: '请输入时间间隔',
    frameSkip: '请输入跳帧数量',
    interval: '请输入预警时间',
    count: '请输入数量上限',
    threshold: '请输入阈值',
    confidence: '请输入置信度',
    minSize: '请输入最小尺寸',
    maxSize: '请输入最大尺寸',
    sensitivity: '请输入敏感度',
    duration: '请输入持续时间',
    speed: '请输入速度阈值',
    area: '请输入区域面积',
    ratio: '请输入比例',
    enabled: '',
    debug: ''
  }
  return placeholderMap[key] || `请输入${key}`
}

// 组件卸载时清理资源
onUnmounted(() => {
  if (flvPlayer.value) {
    flvPlayer.value.destroy()
  }
})

// 监听弹框关闭事件，清理视频资源和ROI绘制
watch(configDialogVisible, (newVal) => {
  if (!newVal) {
    // 清理视频资源
    if (flvPlayer.value) {
      flvPlayer.value.destroy()
      flvPlayer.value = null
      flvUrl.value = ''
    }

    // 清空ROI绘制，确保算法间ROI独立性
    if (labelBoard.value) {
      const ctx = labelBoard.value.getContext('2d')
      ctx.clearRect(0, 0, labelBoard.value.width, labelBoard.value.height)
      roiPolygons.value = []
      points.value = []
    }
  }
})
</script>

<style scoped>
.app-container {
  padding: 20px;
}

.el-transfer {
  width: 100%;
}

:deep(.el-transfer-panel) {
  width: 40%;
}

.transfer-footer {
  padding: 10px;
  border-top: 1px solid #ebeef5;
}

.config-btn {
  margin: 2px;
  padding: 4px 8px;
  font-size: 12px;
}

:deep(.el-transfer__buttons) {
  padding: 10px;
}

:deep(.el-transfer-panel__list) {
  padding-bottom: 50px;
}

.transfer-item-with-button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  min-height: 32px; /* 确保所有行高度一致 */
}

.item-label {
  flex: 1;
  margin-right: 8px;
  min-width: 0; /* 防止文本溢出 */
}

.config-btn {
  flex-shrink: 0;
  margin: 0;
  padding: 4px 8px;
  font-size: 12px;
  visibility: visible; /* 确保配置按钮始终可见 */
}

.config-placeholder {
  width: 40px; /* 与配置按钮相同的宽度 */
  height: 24px; /* 与配置按钮相同的高度 */
  flex-shrink: 0;
}

:deep(.el-checkbox) {
  margin-right: 0px;
}

:deep(.el-transfer-panel__item .el-checkbox__input) {
  top: 16px;
}

.roi-coordinates {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.roi-row {
  display: flex;
  gap: 8px;
}

.roi-row .el-input-number {
  width: 100px;
}

/* 视频预览样式 */
.video-preview-container {
  position: relative;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background: #f5f7fa;
}

.label-box {
  position: relative;
  width: 640px;
  height: 360px;
}

.label-board {
  position: absolute;
  top: 0;
  left: 0;
  width: 640px;
  height: 360px;
}

.video-player {
  margin-bottom: 10px;
  position: absolute;
  top: 0;
  left: 0;
}

.video-placeholder {
  text-align: center;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 4px;
}

.video-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: #e1f3d8;
  border-radius: 4px;
  margin-top: 10px;
}

.status-text {
  font-size: 12px;
  color: #67c23a;
  flex: 1;
  margin-right: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ROI控制样式 */
.roi-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 8px;
  background: #f9f9f9;
  border-radius: 4px;
}

.roi-tip {
  font-size: 12px;
  color: #909399;
  flex: 1;
}

/* 方向绘制按钮激活状态 */
.roi-controls .el-button.active {
  background-color: #67c23a;
  border-color: #67c23a;
  color: #fff;
}

.roi-controls .el-button.active:hover {
  background-color: #85ce61;
  border-color: #85ce61;
}
</style>
